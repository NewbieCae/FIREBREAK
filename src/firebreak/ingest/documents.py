"""Lecture de documents fournisseurs → record proposé.

Un PDF ou un mail (bon de commande, avis d'expédition, facture, changement
de RIB) devient une *proposition* de record. Rien n'entre dans le registre
sans confirmation explicite ; une fois confirmé, le record passe par les
règles du graphe comme n'importe quel autre (l'IA ne décide d'aucun blocage).

- `MockExtractor` : expressions régulières, déterministe, hors ligne ;
- `BedrockExtractor` : AWS Bedrock, repli sur le mock si erreur ou si la
  réponse contient une valeur absente du document (RIB ou référence inventés).
"""

from __future__ import annotations

import email
import email.policy
import io
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from ..ai import BedrockConverser, BedrockError, Source, ai_mode

log = logging.getLogger("firebreak.ingest")

KINDS = ("purchase_order", "asn", "invoice", "bank_details_change")
MAX_DOCUMENT_BYTES = 2_000_000
MAX_PROMPT_CHARS = 12_000


class DocumentError(ValueError):
    """Document illisible ou vide."""


@dataclass(frozen=True)
class Party:
    id: str
    name: str


# -- texte brut ------------------------------------------------------------------


def document_text(data: bytes) -> str:
    """Texte d'un PDF, d'un mail RFC 822 (.eml) ou d'un texte brut UTF-8."""
    if not data or not data.strip():
        raise DocumentError("document vide")
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentError("document trop volumineux (2 Mo max)")
    if data.lstrip()[:5] == b"%PDF-":
        return _pdf_text(data)
    text = data.decode("utf-8", errors="replace")
    if re.match(r"^(From|De|Subject|Objet|To|À|Date)\s*:", text, re.IGNORECASE) and \
            re.search(r"^(Subject|Objet)\s*:", text, re.IGNORECASE | re.MULTILINE):
        return _mail_text(data) or text
    return text


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, KeyError, TypeError) as exc:
        raise DocumentError("PDF illisible") from exc
    if not text.strip():
        raise DocumentError("PDF sans texte extractible (scan ?)")
    return text


def _mail_text(data: bytes) -> str:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    head = [f"De : {msg.get('From', '')}", f"Objet : {msg.get('Subject', '')}",
            f"Date : {msg.get('Date', '')}"]
    body = msg.get_body(preferencelist=("plain",))
    content = body.get_content() if body is not None else ""
    return "\n".join(head) + "\n\n" + content


# -- extraction par expressions régulières -----------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("’", "'")
    return re.sub(r"[\s\-_.@]+", " ", text)


KIND_KEYWORDS = {
    "invoice": ("facture", "net a payer", "montant ttc"),
    "asn": ("avis d'expedition", "advance shipping notice", "asn", "bon de livraison"),
    "purchase_order": ("bon de commande", "commande n", "purchase order"),
    "bank_details_change": ("changement de rib", "changement de coordonnees bancaires",
                            "nouvelles coordonnees bancaires", "nouveau rib"),
}
RIB_CHANGE_KEYWORDS = KIND_KEYWORDS["bank_details_change"] + (
    "coordonnees bancaires ont change", "rib a change", "nouvel iban")

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){4,7}(?: ?[A-Z0-9]{1,3})?\b")
REF_RE = re.compile(r"\b(?:BC|F|CQ|LOT|ASN|BL)-\d{3,}\b")
AMOUNT_RE = re.compile(
    r"(?:montant|total(?:\s+ttc)?|net\s+[àa]\s+payer)[^\d\n]{0,25}"
    r"(\d{1,3}(?:[ \u00a0\u202f.]\d{3})*(?:,\d{2})?|\d+(?:[.,]\d{2})?)\s*(?:€|eur)",
    re.IGNORECASE,
)
DATE_FR_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")
DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def normalize_iban(raw: str) -> str:
    compact = re.sub(r"\s+", "", raw).upper()
    return " ".join(compact[i:i + 4] for i in range(0, len(compact), 4))


def _amount(text: str) -> int | float | None:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    raw = re.sub(r"[ \u00a0\u202f]", "", m.group(1))
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    value = float(raw)
    return int(value) if value.is_integer() else value


def _dates(text: str) -> list[str]:
    found: list[str] = []
    for m in DATE_FR_RE.finditer(text):
        d, mo, y = (int(g) for g in m.groups())
        _add_date(found, y, mo, d)
    for m in DATE_ISO_RE.finditer(text):
        y, mo, d = (int(g) for g in m.groups())
        _add_date(found, y, mo, d)
    return found


def _add_date(found: list[str], y: int, mo: int, d: int) -> None:
    try:
        iso = date(y, mo, d).isoformat()
    except ValueError:
        return
    if iso not in found:
        found.append(iso)


def _ribs(text: str) -> tuple[str | None, str | None]:
    """(rib retenu, rib précédent). Le RIB annoncé comme nouveau est retenu."""
    matches = [(m.start(), normalize_iban(m.group(0))) for m in IBAN_RE.finditer(text)]
    distinct: list[tuple[int, str]] = []
    for pos, iban in matches:
        if iban not in (i for _, i in distinct):
            distinct.append((pos, iban))
    if not distinct:
        return None, None
    if len(distinct) == 1:
        return distinct[0][1], None
    for pos, iban in distinct:
        before = _norm(text[max(0, pos - 80):pos])
        if any(k in before for k in ("nouveau", "nouvel", "nouvelles", "desormais")):
            others = [i for _, i in distinct if i != iban]
            return iban, others[0]
    return distinct[-1][1], distinct[0][1]


def _kind(text: str) -> tuple[str | None, bool]:
    """(kind, détecté dans l'en-tête). L'en-tête (objet, titre) pèse triple."""
    norm, head = _norm(text), _norm(text[:300])
    scores = {}
    for kind, words in KIND_KEYWORDS.items():
        score = 0
        for w in words:
            pattern = rf"\b{re.escape(w)}\b"
            score += len(re.findall(pattern, norm)) + 3 * len(re.findall(pattern, head))
        scores[kind] = score
    best = max(KINDS, key=lambda k: scores[k])
    if scores[best] == 0:
        return None, False
    in_head = any(re.search(rf"\b{re.escape(w)}\b", head) for w in KIND_KEYWORDS[best])
    return best, in_head


def _origin(text: str, parties: list[Party], company: str) -> str | None:
    norm = _norm(text)
    best: tuple[int, str] | None = None
    for p in parties:
        if p.id == company:
            continue
        pos = norm.find(_norm(p.name))
        if pos >= 0 and (best is None or pos < best[0]):
            best = (pos, p.id)
    return best[1] if best else None


EXPECTED_FIELDS = {
    "invoice": ("origin", "amount", "rib", "references", "dates"),
    "asn": ("origin", "references", "dates"),
    "purchase_order": ("origin", "references", "dates"),
    "bank_details_change": ("origin", "rib"),
}


def _label(kind: str | None, payload: dict) -> str:
    refs = payload.get("references", [])

    def first(prefix: str) -> str | None:
        return next((r for r in refs if r.startswith(prefix + "-")), None)

    if kind == "invoice":
        label = "Facture reçue " + (first("F") or "sans numéro")
        if payload.get("bank_details_change"):
            label += " — nouveau RIB"
        return label
    if kind == "asn":
        return "ASN reçu — " + (first("BC") or first("ASN") or "sans référence")
    if kind == "purchase_order":
        return "Bon de commande reçu " + (first("BC") or "sans numéro")
    if kind == "bank_details_change":
        return "Changement de RIB reçu"
    return "Document fournisseur non classé"


def _finish(kind: str | None, origin: str | None, payload: dict,
            known_ribs: set[str], kind_in_head: bool) -> tuple[dict, float, list[str]]:
    """Complète le payload (changement de RIB), calcule confiance et manques."""
    rib = payload.get("rib")
    if rib and known_ribs and rib not in known_ribs:
        payload["bank_details_change"] = True
        payload["rib_unknown_for_origin"] = True
    if kind == "bank_details_change":
        payload["bank_details_change"] = True
    found = {
        "origin": origin is not None,
        "amount": payload.get("amount") is not None,
        "rib": bool(rib),
        "references": bool(payload.get("references")),
        "dates": bool(payload.get("dates")),
    }
    if kind is None:
        return payload, 0.1, ["kind"] + [k for k, ok in found.items() if not ok]
    expected = EXPECTED_FIELDS[kind]
    missing = [f for f in expected if not found[f]]
    ratio = (len(expected) - len(missing)) / len(expected)
    # heuristique bornée à 0,9 : une regex ne garantit jamais l'exactitude
    confidence = round(0.15 + 0.6 * ratio + (0.15 if kind_in_head else 0.05), 2)
    return payload, confidence, missing


class MockExtractor:
    source: Source = "mock"

    def extract(self, text: str, company: str, parties: list[Party],
                known_ribs: dict[str, set[str]] | None = None) -> dict:
        kind, in_head = _kind(text)
        origin = _origin(text, parties, company)
        rib, previous = _ribs(text)
        payload: dict = {}
        amount = _amount(text)
        if amount is not None:
            payload["amount"] = amount
        if rib:
            payload["rib"] = rib
        if previous:
            payload["previous_rib"] = previous
        norm = _norm(text)
        if any(k in norm for k in RIB_CHANGE_KEYWORDS):
            payload["bank_details_change"] = True
        payload["references"] = list(dict.fromkeys(REF_RE.findall(text)))
        payload["dates"] = _dates(text)
        ribs = (known_ribs or {}).get(origin or "", set())
        payload, confidence, missing = _finish(kind, origin, payload, ribs, in_head)
        return {
            "kind": kind,
            "label": _label(kind, payload),
            "origin": origin,
            "payload": payload,
            "confidence": confidence,
            "missing": missing,
            "source": self.source,
        }


# -- Bedrock ---------------------------------------------------------------------

EXTRACT_SYSTEM = (
    "Tu extrais les données d'un document fournisseur pour FIREBREAK. Tu ne décides "
    "de rien : ta sortie est une proposition qu'un humain confirmera. N'invente "
    "aucune valeur : tout RIB, référence ou date doit figurer dans le document. "
    "Réponds par un seul objet JSON, sans texte autour : {\"kind\": un de "
    + ", ".join(KINDS) + " ou null, \"origin\": id de l'entreprise émettrice parmi "
    "la liste fournie ou null, \"payload\": {\"amount\": nombre ou null, \"rib\": "
    "IBAN ou null, \"previous_rib\": IBAN ou null, \"bank_details_change\": booléen, "
    "\"references\": [chaînes], \"dates\": [AAAA-MM-JJ]}, \"confidence\": 0 à 1}"
)


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", s).upper()


def validate_extraction(data: dict, text: str, parties: list[Party], company: str) -> dict:
    kind = data.get("kind")
    if kind is not None and kind not in KINDS:
        raise BedrockError(f"type de document hors liste: {kind!r}")
    origin = data.get("origin")
    if origin is not None and origin not in {p.id for p in parties if p.id != company}:
        raise BedrockError(f"émetteur inconnu: {origin!r}")
    raw = data.get("payload")
    if not isinstance(raw, dict):
        raise BedrockError("payload absent")
    compact_text = _compact(text)
    payload: dict = {}
    amount = raw.get("amount")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            raise BedrockError("montant invalide")
        payload["amount"] = int(amount) if float(amount).is_integer() else amount
    for key in ("rib", "previous_rib"):
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not IBAN_RE.fullmatch(normalize_iban(value)):
            raise BedrockError(f"{key} invalide")
        if _compact(value) not in compact_text:
            raise BedrockError(f"{key} absent du document")
        payload[key] = normalize_iban(value)
    if raw.get("bank_details_change") is True:
        payload["bank_details_change"] = True
    refs = raw.get("references") or []
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        raise BedrockError("références invalides")
    for r in refs:
        if _compact(r) not in compact_text:
            raise BedrockError(f"référence absente du document: {r!r}")
    payload["references"] = list(dict.fromkeys(r.strip() for r in refs))
    dates = raw.get("dates") or []
    if not isinstance(dates, list) or not all(
            isinstance(d, str) and DATE_ISO_RE.fullmatch(d) for d in dates):
        raise BedrockError("dates invalides")
    payload["dates"] = list(dict.fromkeys(dates))
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
            or not 0 <= confidence <= 1:
        raise BedrockError("confiance invalide")
    return {"kind": kind, "origin": origin, "payload": payload,
            "confidence": round(float(confidence), 2)}


class BedrockExtractor:
    source: Source = "bedrock"

    def __init__(self, converser: BedrockConverser | None = None,
                 fallback: MockExtractor | None = None) -> None:
        self.converser = converser or BedrockConverser()
        self.fallback = fallback or MockExtractor()

    def extract(self, text: str, company: str, parties: list[Party],
                known_ribs: dict[str, set[str]] | None = None) -> dict:
        prompt = json.dumps({
            "destinataire": company,
            "entreprises": [{"id": p.id, "nom": p.name} for p in parties if p.id != company],
            "document": text[:MAX_PROMPT_CHARS],
        }, ensure_ascii=False, indent=1)
        try:
            data = self.converser.ask_json(EXTRACT_SYSTEM, prompt)
            result = validate_extraction(data, text, parties, company)
        except BedrockError as exc:
            log.warning("Bedrock indisponible, repli sur le mock : %s", exc)
            return self.fallback.extract(text, company, parties, known_ribs)
        kind, origin = result["kind"], result["origin"]
        ribs = (known_ribs or {}).get(origin or "", set())
        payload, _, missing = _finish(kind, origin, result["payload"], ribs, True)
        return {
            "kind": kind,
            "label": _label(kind, payload),
            "origin": origin,
            "payload": payload,
            "confidence": result["confidence"],
            "missing": missing,
            "source": self.source,
        }


def get_extractor() -> MockExtractor | BedrockExtractor:
    """FIREBREAK_AI=bedrock → BedrockExtractor (repli mock intégré) ; sinon mock."""
    if ai_mode() == "bedrock":
        return BedrockExtractor()
    return MockExtractor()
