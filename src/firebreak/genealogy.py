"""Lot genealogy, in the style of an EPCIS TransformationEvent.

A transformation consumes lots (received coils, intermediate lots)
and produces a lot: the produced record has the consumed lots' records
as `inputs` and carries `payload = {"lot": <produced>, "input_lots": [...]}`.
Taint therefore follows the genealogy with no special rule: a lot made
from a tainted lot is tainted, the others keep going.
"""

from __future__ import annotations

import networkx as nx

from .engine import Ledger
from .model import Record


def lot_of(record: Record) -> str | None:
    return record.payload.get("lot")


def transformation_payload(consumed: list[Record], output_lot: str,
                           extra: dict | None = None) -> dict:
    input_lots = [lot for r in consumed if (lot := lot_of(r)) is not None]
    return {**(extra or {}), "lot": output_lot, "input_lots": input_lots}


def records_of_lot(ledger: Ledger, lot: str) -> list[str]:
    """Records of a ledger that carry this lot, in insertion order."""
    return [rid for rid, r in ledger.records.items() if lot_of(r) == lot]


def lot_genealogy(ledger: Ledger, lot: str) -> dict:
    """Upstream lots (consumed, directly or not) and downstream lots (made
    with this lot) in a company's ledger."""
    carriers = records_of_lot(ledger, lot)
    if not carriers:
        raise KeyError(lot)
    up: set[str] = set()
    down: set[str] = set()
    for rid in carriers:
        up |= nx.ancestors(ledger.graph, rid)
        down |= nx.descendants(ledger.graph, rid)

    def lots(ids: set[str]) -> list[str]:
        found = {lot_of(ledger.records[i]) for i in ids if i in ledger.records}
        return sorted(x for x in found if x is not None and x != lot)

    return {"lot": lot, "records": carriers, "ancestors": lots(up),
            "descendants": lots(down)}
