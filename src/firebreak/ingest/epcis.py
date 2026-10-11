"""GS1 EPCIS 2.0 import (JSON / JSON-LD) → records of a Firebreak ledger.

Supported subset (the rest is ignored and reported, never guessed):
- document: `type: "EPCISDocument"`, events in `epcisBody.eventList`;
- events: ObjectEvent, AggregationEvent, TransformationEvent
  (AssociationEvent, TransactionEvent and `errorDeclaration` are ignored);
- fields read: eventTime, eventID, bizStep, action, disposition, bizLocation,
  readPoint, sourceList, destinationList, epcList, quantityList, parentID,
  childEPCs, childQuantityList, inputEPCList, outputEPCList,
  inputQuantityList, outputQuantityList.

Conversion rules (deterministic):
- one event = one record, in eventTime order;
- `origin` = company that owns the location (bizLocation, else readPoint),
  recognized by its GS1 company prefix; no location: the importing
  company; unknown location: event ignored;
- `inputs` = last record that produced each of the consumed objects
  (EPC or lot class), including records already imported;
- consumed / produced objects: ObjectEvent epcList+quantityList (the
  same); AggregationEvent children (+ parent) → parent and children;
  TransformationEvent input* → output* (lot genealogy);
- `gate`: shipment (bizStep shipping) or transformation done by the
  company itself;
- `verified`: conformant inspection (bizStep inspecting) done by the
  company itself;
- a partner's shipment becomes an `asn` in the ledger.
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
    "conformant": "conformant",
    "non_conformant": "non-conformant",
    "in_transit": "in transit",
    "in_progress": "in progress",
}


class EpcisError(ValueError):
    pass


@dataclass
class EpcisImport:
    records: list[Record] = field(default_factory=list)
    ignored: list[dict] = field(default_factory=list)
    events: int = 0


def cbv_term(value: str | None) -> str | None:
    """"urn:epcglobal:cbv:bizstep:shipping", "https://ref.gs1.org/cbv/BizStep-shipping"
    or "shipping" → "shipping"."""
    if not value:
        return None
    term = re.split(r"[:/]", value)[-1]
    return term.split("-", 1)[1] if term.startswith(("BizStep-", "Disp-")) else term


def lot_of(identifier: str) -> str | None:
    """Lot of an LGTIN class (URN or GS1 Digital Link /10/)."""
    if identifier.startswith("urn:epc:class:lgtin:"):
        return identifier.rsplit(".", 1)[-1]
    m = re.search(r"/10/([^/?#]+)", identifier)
    return m.group(1) if m else None


def short_name(identifier: str) -> str:
    tail = re.split(r"[:/.]", identifier.rstrip("/"))[-1]
    if identifier.startswith("urn:epc:id:sscc:") or "/00/" in identifier:
        return f"pallet {tail}"
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
    """(consumed objects, produced objects) of the event."""
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
        return f"Palletization {names(children)} → {short_name(parent) if parent else '?'}"
    objs = names(produced or consumed)
    if kind == "asn":
        return f"Shipping notice {origin_name} — {objs}"
    if kind == "shipment":
        return f"Shipment {objs}"
    if kind == "goods_receipt":
        return f"Receipt {objs}"
    if kind == "quality_check":
        verdict = DISPOSITIONS_FR.get(disposition or "", disposition or "no verdict")
        return f"Quality check {objs} ({verdict})"
    if kind == "stock_entry":
        return f"Stock entry {objs}"
    return f"EPCIS event {cbv_term(event.get('bizStep')) or event['type']} — {objs}"


def parse_epcis(doc: object, company: str, companies: list[Company],
                existing: dict[str, Record], id_prefix: str,
                taken_ids: set[str] | None = None) -> EpcisImport:
    """Converts an EPCIS document into records for the `company` ledger.
    `existing` = records already in this ledger; `taken_ids` = identifiers
    already taken across the whole simulation. Changes nothing: the caller
    adds the records to the ledger."""
    taken = set(existing) | (taken_ids or set())
    if not isinstance(doc, dict) or doc.get("type") != "EPCISDocument":
        raise EpcisError("EPCIS document expected (type: EPCISDocument)")
    body = doc.get("epcisBody")
    events = body.get("eventList") if isinstance(body, dict) else None
    if not isinstance(events, list):
        raise EpcisError("epcisBody.eventList missing")
    if len(events) > MAX_EVENTS:
        raise EpcisError(f"too many events ({len(events)} > {MAX_EVENTS})")

    names = {c.id: c.name for c in companies}
    result = EpcisImport(events=len(events))
    last: dict[str, str] = {}  # EPC object -> last record that produced it
    for r in existing.values():
        for obj in r.payload.get("epc_outputs", []):
            last[obj] = r.id

    parsed: list[tuple[datetime, int, dict]] = []
    for index, event in enumerate(events):
        etype = event.get("type") if isinstance(event, dict) else None
        if etype not in SUPPORTED:
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "unsupported event type"})
            continue
        if event.get("errorDeclaration"):
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "error declaration (errorDeclaration)"})
            continue
        try:
            ts = to_scenario_time(datetime.fromisoformat(event["eventTime"]))
        except (KeyError, TypeError, ValueError):
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "eventTime missing or invalid"})
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
                                   "reason": f"unknown GLN location: {location}"})
            continue
        consumed, produced = _objects(event)
        if not consumed and not produced:
            result.ignored.append({"index": index, "type": etype,
                                   "reason": "no object (EPC or lot)"})
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
