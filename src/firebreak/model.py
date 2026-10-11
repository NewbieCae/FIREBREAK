"""Firebreak data model.

A Record is a business event recorded in the ledger (Ledger) of a single
company. Dependencies between records of the same ledger are expressed
by `inputs`; exchanges between companies only travel through opaque
tokens (`token`) and signed alerts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Status = Literal["ok", "quarantined", "released"]


@dataclass
class Company:
    id: str
    name: str
    role: str
    gs1_prefix: str = ""  # GS1 company prefix: links EPCIS GLN/SGLN to the company


@dataclass
class Record:
    id: str  # globally unique, e.g. "fab-0042"
    company: str  # company that owns the ledger
    origin: str  # company that issued the data
    kind: str  # purchase_order, asn, quality_cert, invoice, payment…
    ts: datetime
    label: str  # human-readable label
    inputs: list[str] = field(default_factory=list)  # record ids from the SAME ledger
    gate: bool = False  # irreversible action: payment, shipment, production start
    verified: bool = False  # confirmed by a trusted source
    payload: dict = field(default_factory=dict)
    token: str | None = None  # opaque cross-company reference (received records)
    status: Status = "ok"
    taint_path: list[str] | None = None  # explainable evidence: from the seed to this record


def payment_amount(record: Record) -> float:
    """Amount counted for a record: payments only.

    Invoice/ASN amounts do not count here: counting every document that
    carries an amount would count the same euros several times
    (issued invoice + received copy + payment)."""
    if record.kind != "payment":
        return 0.0
    amount = record.payload.get("amount", 0)
    return amount if isinstance(amount, (int, float)) else 0
