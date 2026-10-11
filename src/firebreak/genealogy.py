"""Généalogie des lots, à la manière d'un TransformationEvent EPCIS.

Une transformation consomme des lots (bobines reçues, lots intermédiaires)
et produit un lot : le record produit a pour `inputs` les records des lots
consommés et porte `payload = {"lot": <produit>, "input_lots": [...]}`.
La contamination suit donc la généalogie sans règle spéciale : un lot
fabriqué avec un lot contaminé est contaminé, les autres continuent.
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
    """Records d'un registre qui portent ce lot, dans l'ordre d'insertion."""
    return [rid for rid, r in ledger.records.items() if lot_of(r) == lot]


def lot_genealogy(ledger: Ledger, lot: str) -> dict:
    """Lots en amont (consommés, directement ou non) et en aval (fabriqués
    avec ce lot) dans le registre d'une entreprise."""
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
