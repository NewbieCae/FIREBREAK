"""Import GS1 EPCIS 2.0 (JSON / JSON-LD) → records d'un registre Firebreak.

Sous-ensemble géré (le reste est ignoré et signalé, jamais deviné) :
- document : `type: "EPCISDocument"`, événements dans `epcisBody.eventList` ;
- événements : ObjectEvent, AggregationEvent, TransformationEvent
  (AssociationEvent, TransactionEvent et `errorDeclaration` sont ignorés) ;
- champs lus : eventTime, eventID, bizStep, action, disposition, bizLocation,
  readPoint, sourceList, destinationList, epcList, quantityList, parentID,
  childEPCs, childQuantityList, inputEPCList, outputEPCList,
  inputQuantityList, outputQuantityList.

Règles de conversion (déterministes) :
- un événement = un record, dans l'ordre de eventTime ;
- `origin` = entreprise propriétaire du lieu (bizLocation, sinon readPoint),
  reconnue par son préfixe entreprise GS1 ; sans lieu : l'entreprise qui
  importe ; lieu inconnu : événement ignoré ;
- `inputs` = dernier record qui a produit chacun des objets consommés
  (EPC ou classe de lot), y compris les records déjà importés ;
- objets consommés / produits : ObjectEvent epcList+quantityList (les
  mêmes) ; AggregationEvent enfants (+ parent) → parent et enfants ;
  TransformationEvent input* → output* (généalogie des lots) ;
- `gate` : expédition (bizStep shipping) ou transformation faites par
  l'entreprise elle-même ;
- `verified` : contrôle (bizStep inspecting) conforme fait par l'entreprise
  elle-même ;
- une expédition d'un partenaire devient un `asn` dans le registre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from ..model import Company, Record
from ..simulation import to_scenario_time

SUPPORTED = ("ObjectEvent", "AggregationEvent", "TransformationEvent")
MAX_EVENTS = 1000

KIND_BY_BIZSTEP = {
    "shipping": "shipment",
    "receiving": "goods_receipt",
    "accepting": "goods_receipt",
    "inspecting": "quality_check",
    "storing": "stock_entry",
    "packing": "packing",
    "unpacking": "unpacking",
    "commissioning": "commissioning",
}

DISPOSITIONS_FR = {
    "conformant": "conforme",
    "non_conformant": "non conforme",
    "in_transit": "en transit",
    "in_progress": "en cours",
}


class EpcisError(ValueError):
    pass


@dataclass
class EpcisImport:
    records: list[Record] = field(default_factory=list)
    ignored: list[dict] = field(default_factory=list)
    events: int = 0


def cbv_term(value: str | None) -> str | None:
    """« urn:epcglobal:cbv:bizstep:shipping », « https://ref.gs1.org/cbv/BizStep-shipping »
    ou « shipping » → « shipping »."""
    if not value:
        return None
    term = re.split(r"[:/]", value)[-1]
    return term.split("-", 1)[1] if term.startswith(("BizStep-", "Disp-")) else term


def lot_of(identifier: str) -> str | None:
    """Lot d'une classe LGTIN (URN ou GS1 Digital Link /10/)."""
    if identifier.startswith("urn:epc:class:lgtin:"):
        return identifier.rsplit(".", 1)[-1]
    m = re.search(r"/10/([^/?#]+)", identifier)
    return m.group(1) if m else None


def short_name(identifier: str) -> str:
    tail = re.split(r"[:/.]", identifier.rstrip("/"))[-1]
    if identifier.startswith("urn:epc:id:sscc:") or "/00/" in identifier:
        return f"palette {tail}"
    return lot_of(identifier) or tail


def _gs1_digits(identifier: str) -> str | None:
    if identifier.startswith("urn:epc:id:"):
        return identifier.rsplit(":", 1)[-1].split(".", 1)[0]
    m = re.search(r"/(?:414|417)/(\d+)", identifier)
    return m.group(1) if m else None


def owner_of(identifier: str, companies: list[Company]) -> str | None:
    digits = _gs1_digits(identifier)
    if not digits:
        return None
    matches = [c for c in companies if c.gs1_prefix and digits.startswith(c.gs1_prefix)]
    return max(matches, key=lambda c: len(c.gs1_prefix)).id if matches else None


def _location(event: dict) -> str | None:
    for key in ("bizLocation", "readPoint"):
        loc = event.get(key)
        if isinstance(loc, dict) and isinstance(loc.get("id"), str):
            return loc["id"]
        if isinstance(loc, str):
            return loc
    return None


def _ids(event: dict, list_key: str, qty_key: str) -> list[str]:
    out = [e for e in event.get(list_key) or [] if isinstance(e, str)]
    out += [q["epcClass"] for q in event.get(qty_key) or []
            if isinstance(q, dict) and isinstance(q.get("epcClass"), str)]
    return out


def _objects(event: dict) -> tuple[list[str], list[str]]:
    """(objets consommés, objets produits) de l'événement."""
    etype = event["type"]
    if etype == "TransformationEvent":
        return (_ids(event, "inputEPCList", "inputQuantityList"),
                _ids(event, "outputEPCList", "outputQuantityList"))
    if etype == "AggregationEvent":
        children = _ids(event, "childEPCs", "childQuantityList")
        parent = [event["parentID"]] if isinstance(event.get("parentID"), str) else []
        return children + parent, parent + children
    objs = _ids(event, "epcList", "quantityList")
    return objs, ([] if event.get("action") == "DELETE" else objs)


def _parties(event: dict, key: str) -> list[str]:
    return [p["source" if key == "sourceList" else "destination"]
            for p in event.get(key) or []
            if isinstance(p, dict) and isinstance(
                p.get("source" if key == "sourceList" else "destination"), str)]


def _label(kind: str, event: dict, consumed: list[str], produced: list[str],
           origin_name: str, disposition: str | None) -> str:
    names = lambda ids: " + ".join(dict.fromkeys(short_name(i) for i in ids)) or "?"  # noqa: E731
    if kind == "production_lot":
        return f"Transformation {names(consumed)} → {names(produced)}"
    if kind == "packing":
        parent = event.get("parentID")
        children = [i for i in consumed if i != parent]
        return f"Palettisation {names(children)} → {short_name(parent) if parent else '?'}"
    objs = names(produced or consumed)
    if kind == "asn":
        return f"Avis d'expédition {origin_name} — {objs}"
    if kind == "shipment":
        return f"Expédition {objs}"
    if kind == "goods_receipt":
        return f"Réception {objs}"
    if kind == "quality_check":
        verdict = DISPOSITIONS_FR.get(disposition or "", disposition or "sans verdict")
        return f"Contrôle qualité {objs} ({verdict})"
    if kind == "stock_entry":
        return f"Mise en stock {objs}"
    return f"Événement EPCIS {cbv_term(event.get('bizStep')) or event['type']} — {objs}"


def parse_epcis(doc: object, company: str, companies: list[Company],
                existing: dict[str, Record], id_prefix: str,
                taken_ids: set[str] | None = None) -> EpcisImport:
    """Convertit un document EPCIS en records pour le registre `company`.
    `existing` = records déjà dans ce registre ; `taken_ids` = identifiants
    déjà pris dans toute la simulation. Ne modifie rien : l'appelant ajoute
    les records au registre."""
    taken = set(existing) | (taken_ids or set())
    if not isinstance(doc, dict) or doc.get("type") != "EPCISDocument":
        raise EpcisError("document EPCIS attendu (type: EPCISDocument)")
    body = doc.get("epcisBody")
    events = body.get("eventList") if isinstance(body, dict) else None
    if not isinstance(events, list):
        raise EpcisError("epcisBody.eventList manquant")
    if len(events) > MAX_EVENTS:
        raise EpcisError(f"trop d'événements ({len(events)} > {MAX_EVENTS})")

    names = {c.id: c.name for c in companies}
    result = EpcisImport(events=len(events))
    last: dict[str, str] = {}  # objet EPC -> dernier record qui l'a produit
    for r in existing.values():
        for obj in r.payload.get("epc_outputs", []):
            last[obj] = r.id

    parsed: list[tuple[datetime, int, dict]] = []
    for index, event in enumerate(events):
        etype = event.get("type") if isinstance(event, dict) else None
        if etype not in SUPPORTED:
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "type d'événement non géré"})
            continue
        if event.get("errorDeclaration"):
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "déclaration d'erreur (errorDeclaration)"})
            continue
        try:
            ts = to_scenario_time(datetime.fromisoformat(event["eventTime"]))
        except (KeyError, TypeError, ValueError):
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "eventTime absent ou invalide"})
            continue
        parsed.append((ts, index, event))
    parsed.sort(key=lambda p: (p[0], p[1]))

    n = 0
    for ts, index, event in parsed:
        etype = event["type"]
        location = _location(event)
        origin = owner_of(location, companies) if location else company
        if origin is None:
            result.ignored.append({"index": index, "type": etype,
                                   "reason": f"lieu GLN inconnu : {location}"})
            continue
        consumed, produced = _objects(event)
        if not consumed and not produced:
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "aucun objet (EPC ou lot)"})
            continue
        biz_step = cbv_term(event.get("bizStep"))
        disposition = cbv_term(event.get("disposition"))
        own = origin == company
        if etype == "TransformationEvent":
            kind = "production_lot"
        elif biz_step == "shipping" and not own:
            kind = "asn"
        else:
            kind = KIND_BY_BIZSTEP.get(biz_step or "", "epcis_event")

        n += 1
        while f"{id_prefix}-epcis-{n:02d}" in taken:
            n += 1
        rid = f"{id_prefix}-epcis-{n:02d}"
        inputs = list(dict.fromkeys(last[o] for o in consumed if o in last))
        payload: dict = {
            "epcis": {
                "event_id": event.get("eventID"),
                "type": etype,
                "biz_step": biz_step,
                "action": event.get("action"),
                "disposition": disposition,
                "biz_location": location,
                "sources": _parties(event, "sourceList"),
                "destinations": _parties(event, "destinationList"),
            },
            "epc_inputs": consumed,
            "epc_outputs": produced,
        }
        lots = [lot for o in produced if (lot := lot_of(o))]
        if lots:
            payload["lot"] = lots[0]
        if etype == "TransformationEvent":
            payload["input_lots"] = [lot for o in consumed if (lot := lot_of(o))]
        record = Record(
            id=rid, company=company, origin=origin, kind=kind, ts=ts,
            label=_label(kind, event, consumed, produced, names.get(origin, origin),
                         disposition),
            inputs=inputs,
            gate=own and (kind == "production_lot" or biz_step == "shipping"),
            verified=own and biz_step == "inspecting" and disposition == "conformant",
            payload=payload,
        )
        result.records.append(record)
        taken.add(rid)
        for obj in produced:
            last[obj] = rid
    return result
