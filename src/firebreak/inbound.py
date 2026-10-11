"""Contrôle des entrées en stock : note de confiance d'un lot reçu.

À la réception d'une livraison, on croise ce que l'entreprise sait déjà
(référentiel : fiches fournisseurs, pièces et nomenclatures, commandes en
cours) avec ce qui arrive (avis d'expédition, certificat, factures reçues,
alertes en cours). Chaque contrôle est déterministe, pondéré et expliqué ;
la note part de 100 et chaque contrôle en échec retire sa pénalité.

Les règles proposent, l'humain décide : sous le seuil, la réception est mise
en attente (si le lot a déjà été contrôlé physiquement, seulement s'il est
suspect) (elle et tout ce qui en dépend), et un humain l'accepte ou la
refuse. L'explication en français est générée à partir des contrôles ; une
IA peut la reformuler, jamais changer la note ni la décision.

Les données de réception sont lues dans les payloads (`bc`, `part`, `qty`,
`lot` de la réception, `lot_no` des avis d'expédition et certificats — `lot`
y est réservé aux porteurs de lot de la généalogie —, `cert_no`, `grade`, `rib`) et, à défaut, dans les libellés
(« BC-1008 », « CQ-2003 »), pour fonctionner sur des données incomplètes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Ledger
    from .model import Record

TRUST_THRESHOLD = 80   # en dessous : mise en attente + décision humaine
SUSPECT_THRESHOLD = 60  # en dessous : bande « suspect »
RECEIPT_KINDS = {"goods_receipt"}

_BC_RE = re.compile(r"\bBC-[A-Z0-9]+\b")
_CERT_RE = re.compile(r"\bCQ-\d+\b")


@dataclass(frozen=True)
class SupplierProfile:
    id: str
    name: str
    rib: str
    cert_pattern: str  # regex des numéros de certificat attendus
    lot_pattern: str   # regex des numéros de lot attendus
    lead_tolerance: timedelta = timedelta(hours=4)


@dataclass(frozen=True)
class PurchaseOrder:
    bc: str
    supplier: str
    part: str
    qty: float
    grade: str
    due: datetime
    status: str = "open"  # open | closed


@dataclass
class Referentiel:
    """Données de référence d'une entreprise (son ERP, en simplifié)."""

    suppliers: dict[str, SupplierProfile] = field(default_factory=dict)
    parts: dict[str, list[str]] = field(default_factory=dict)  # référence -> produits qui l'utilisent (nomenclature)
    orders: dict[str, PurchaseOrder] = field(default_factory=dict)


def default_referentiels() -> dict[str, Referentiel]:
    """Référentiel du fabricant pour la journée de démo du 10/10/2026 :
    commandes BC-1001 à BC-1008 (bobines du matin et livraison de 14 h 45),
    BC-1009 (facture du scénario rib) et BC-1010 (bobine COIL-210 attendue l'après-midi), toutes chez Aciers
    Durand. Une commande absente (ex. BC-9999) est une commande inconnue."""
    from .scenario import RIB_OK  # import local : scenario importe simulation

    day = datetime(2026, 10, 10)
    supplier = SupplierProfile(
        id="fournisseur", name="Aciers Durand", rib=RIB_OK,
        cert_pattern=r"^CQ-2\d{3}$", lot_pattern=r"^COIL-\d{3}$",
    )
    part = "BOBINE-S235-2MM"
    orders = {}
    for i in range(1, 8):  # livraisons du matin, ASN entre 08:40 et 11:40
        due = day.replace(hour=8, minute=30) + timedelta(minutes=30 * (i - 1) + 40)
        orders[f"BC-{1000 + i}"] = PurchaseOrder(f"BC-{1000 + i}", "fournisseur", part, 12, "S235", due)
    orders["BC-1008"] = PurchaseOrder("BC-1008", "fournisseur", part, 12, "S235", day.replace(hour=15))
    orders["BC-1009"] = PurchaseOrder("BC-1009", "fournisseur", part, 12, "S235", day.replace(hour=16))
    orders["BC-1010"] = PurchaseOrder("BC-1010", "fournisseur", part, 12, "S235", day.replace(hour=14, minute=40))
    fabricant = Referentiel(
        suppliers={"fournisseur": supplier},
        parts={part: ["SUPPORT-CHANTIER", "ASM-950"]},
        orders=orders,
    )
    return {"fabricant": fabricant}


@dataclass
class Check:
    id: str
    label: str
    ok: bool
    penalty: int
    detail: str

    def as_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "ok": self.ok,
                "penalty": self.penalty if not self.ok else 0, "detail": self.detail}


def _first(records: list[Record], kind: str) -> Record | None:
    return next((r for r in records if r.kind == kind), None)


def _from_label(record: Record | None, regex: re.Pattern) -> str | None:
    if record is None:
        return None
    m = regex.search(record.label)
    return m.group(0) if m else None


def _value(key: str, *records: Record | None):
    for r in records:
        if r is not None and r.payload.get(key) not in (None, ""):
            return r.payload[key]
    return None


def band_of(score: int) -> str:
    if score >= TRUST_THRESHOLD:
        return "confiance"
    if score >= SUSPECT_THRESHOLD:
        return "doute"
    return "suspect"


def evaluate_receipt(ledger: Ledger, receipt_id: str, ref: Referentiel | None) -> dict:
    """Note de confiance d'une réception. Lecture seule, déterministe."""
    receipt = ledger.records[receipt_id]
    if receipt.kind not in RECEIPT_KINDS:
        raise ValueError(f"{receipt_id} n'est pas une réception de marchandise")
    inputs = [ledger.records[i] for i in receipt.inputs if i in ledger.records]
    asn = _first(inputs, "asn")
    cert = _first(inputs, "quality_cert")
    supplier_id = next((r.origin for r in (asn, cert) if r is not None and r.origin != ledger.company_id),
                       receipt.origin)
    ref = ref or Referentiel()
    profile = ref.suppliers.get(supplier_id)

    bc = _value("bc", receipt, asn) or _from_label(asn, _BC_RE) or _from_label(receipt, _BC_RE)
    lot = _value("lot", receipt) or _value("lot_no", asn) or _value("lot", asn)
    if cert is None and lot is not None:
        # Certificat non rattaché à la réception : on cherche celui que le
        # même fournisseur a envoyé pour ce lot.
        cert = next((r for r in ledger.records.values()
                     if r.kind == "quality_cert" and r.origin == supplier_id
                     and lot in (r.payload.get("lot_no"), r.payload.get("lot"))), None)
    part = _value("part", receipt, asn, cert)
    qty = _value("qty", receipt, asn)
    cert_no = _value("cert_no", cert) or _from_label(cert, _CERT_RE)
    cert_lot = _value("lot_no", cert) or _value("lot", cert)
    grade = _value("grade", cert)
    po = ref.orders.get(bc) if bc else None

    checks: list[Check] = []

    # 1. Commande
    if not ref.orders:
        checks.append(Check("order", "Commande", True, 0, "référentiel des commandes indisponible"))
    elif bc is None:
        checks.append(Check("order", "Commande", False, 30, "aucun numéro de commande sur l'avis d'expédition"))
    elif po is None:
        checks.append(Check("order", "Commande", False, 40, f"commande {bc} inconnue de l'ERP"))
    elif po.supplier != supplier_id:
        checks.append(Check("order", "Commande", False, 30,
                            f"commande {bc} passée chez {po.supplier}, livrée par {supplier_id}"))
    elif po.status != "open":
        checks.append(Check("order", "Commande", False, 20, f"commande {bc} déjà soldée"))
    else:
        checks.append(Check("order", "Commande", True, 0, f"commande {bc} ouverte chez ce fournisseur"))

    # 2. Pièce et nomenclature
    if part is None:
        checks.append(Check("part", "Référence et nomenclature", True, 0, "référence non transmise"))
    elif po is not None and part != po.part:
        checks.append(Check("part", "Référence et nomenclature", False, 25,
                            f"pièce {part} livrée, {po.part} commandée"))
    elif ref.parts and part not in ref.parts:
        checks.append(Check("part", "Référence et nomenclature", False, 10,
                            f"pièce {part} absente des nomenclatures"))
    else:
        checks.append(Check("part", "Référence et nomenclature", True, 0, f"{part} prévue en nomenclature"))

    # 3. Quantité
    if qty is None or po is None:
        checks.append(Check("qty", "Quantité", True, 0, "quantité non comparable"))
    elif float(qty) > po.qty * 1.10:
        checks.append(Check("qty", "Quantité", False, 15, f"{qty} livrées pour {po.qty:g} commandées"))
    else:
        checks.append(Check("qty", "Quantité", True, 0, f"{qty} pour {po.qty:g} commandées"))

    # 4. Délai
    if po is None:
        checks.append(Check("date", "Date de livraison", True, 0, "pas de date attendue"))
    else:
        tol = profile.lead_tolerance if profile else timedelta(hours=4)
        gap = receipt.ts - po.due
        if abs(gap) > tol:
            sens = "en avance" if gap < timedelta(0) else "en retard"
            checks.append(Check("date", "Date de livraison", False, 10,
                                f"{sens} de {abs(gap) // timedelta(minutes=1)} min sur la date prévue"))
        else:
            checks.append(Check("date", "Date de livraison", True, 0, "dans la fenêtre prévue"))

    # 5. Certificat présent et cohérent
    if cert is None:
        checks.append(Check("cert", "Certificat matière", False, 20, "aucun certificat reçu pour ce lot"))
    else:
        problems, penalty = [], 0
        if cert_lot and lot and cert_lot != lot:
            problems.append(f"certificat pour {cert_lot}, lot reçu {lot}")
            penalty += 20
        if grade and po is not None and grade != po.grade:
            problems.append(f"nuance {grade} certifiée, {po.grade} commandée")
            penalty += 30  # matière non conforme : écart grave
        if problems:
            checks.append(Check("cert", "Certificat matière", False, min(penalty, 40),
                                " ; ".join(problems)))
        else:
            checks.append(Check("cert", "Certificat matière", True, 0, "certificat reçu et cohérent"))

    # 6. Numéro de certificat
    if cert_no is None or profile is None:
        checks.append(Check("cert_no", "Numéro de certificat", True, 0, "non vérifiable"))
    elif not re.match(profile.cert_pattern, cert_no):
        checks.append(Check("cert_no", "Numéro de certificat", False, 15,
                            f"{cert_no} hors de la séquence habituelle du fournisseur"))
    else:
        checks.append(Check("cert_no", "Numéro de certificat", True, 0, f"{cert_no} conforme"))

    # 7. Lot : format et doublon
    if lot is None:
        checks.append(Check("lot", "Numéro de lot", False, 10, "aucun numéro de lot"))
    else:
        dup = [r.id for r in ledger.records.values()
               if r.id != receipt.id and r.kind in RECEIPT_KINDS and r.payload.get("lot") == lot
               and r.ts < receipt.ts]
        if dup:
            checks.append(Check("lot", "Numéro de lot", False, 30, f"lot {lot} déjà réceptionné ({dup[0]})"))
        elif profile is not None and not re.match(profile.lot_pattern, lot):
            checks.append(Check("lot", "Numéro de lot", False, 10, f"format de lot {lot} inhabituel"))
        else:
            checks.append(Check("lot", "Numéro de lot", True, 0, f"lot {lot} jamais reçu"))

    # 8. Coordonnées bancaires du fournisseur (reçues avant la livraison)
    if profile is None:
        checks.append(Check("rib", "Coordonnées bancaires", True, 0, "fiche fournisseur absente"))
    else:
        changed = [r for r in ledger.records.values()
                   if r.origin == supplier_id and r.ts <= receipt.ts
                   and r.payload.get("rib") not in (None, profile.rib)]
        if changed:
            checks.append(Check("rib", "Coordonnées bancaires", False, 15,
                                "RIB différent de la fiche fournisseur reçu aujourd'hui"))
        else:
            checks.append(Check("rib", "Coordonnées bancaires", True, 0, "RIB conforme à la fiche"))

    # 9. Alertes en cours
    flagged = ledger.declaration(supplier_id) is not None or any(
        r.status == "quarantined" for r in inputs)
    if flagged:
        checks.append(Check("alerts", "Alertes en cours", False, 40,
                            "fournisseur déclaré compromis ou données d'entrée en quarantaine"))
    else:
        checks.append(Check("alerts", "Alertes en cours", True, 0, "aucune alerte sur ce fournisseur"))

    score = max(0, 100 - sum(c.penalty for c in checks if not c.ok))
    band = band_of(score)
    failed = [c for c in checks if not c.ok]
    # Un contrôle physique déjà fait à réception compte : en zone de doute, on
    # signale sans bloquer ; on ne met en attente que si le lot est suspect.
    physically_checked = bool(receipt.verified)
    hold = score < SUSPECT_THRESHOLD if physically_checked else score < TRUST_THRESHOLD
    return {
        "receipt": receipt_id,
        "label": receipt.label,
        "supplier": supplier_id,
        "lot": lot,
        "order": bc,
        "score": score,
        "band": band,
        "hold": hold,
        "physically_checked": physically_checked,
        "checks": [c.as_dict() for c in checks],
        "explanation": explain(receipt.label, supplier_id, score, band, failed, hold,
                               physically_checked),
    }


def explain(label: str, supplier: str, score: int, band: str, failed: list[Check],
            hold: bool | None = None, physically_checked: bool = False) -> str:
    """Explication déterministe en français (une IA peut la reformuler)."""
    if hold is None:
        hold = score < TRUST_THRESHOLD
    if not failed:
        return f"« {label} » : {score}/100, aucun écart avec ce que l'on sait du fournisseur {supplier}."
    reasons = " ; ".join(c.detail for c in sorted(failed, key=lambda c: -c.penalty))
    if hold:
        action = "mise en attente : un humain doit accepter ou refuser le lot avant toute utilisation"
    elif physically_checked:
        action = "à surveiller (lot déjà contrôlé physiquement à réception, pas de mise en attente)"
    else:
        action = "à surveiller"
    return f"« {label} » : {score}/100 ({band}). {reasons}. Proposition : {action}."
