"""Taint engine for a Firebreak ledger.

Rules:
- seeds = records whose origin is a company declared compromised
  (and ts >= since), or whose `token` appears in a verified alert
  (and not yet lifted by a verified "release" alert), or records declared
  suspect one by one (defective lot: isolate that lot, not the supplier);
- one declaration per source: the earliest time wins;
- BFS propagation along dependencies (input -> derived record);
- a `verified` or `released` record is never tainted and stops
  propagation through it, unless it is itself declared suspect
  (a defect found afterwards overrides a past check);
- each tainted record keeps `taint_path` (path seed -> itself),
  which serves as explainable evidence.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

import networkx as nx

from .audit import AuditLog
from .model import Record, payment_amount

RULE_SOURCE = "source_compromise"
RULE_ALERT = "alerte_verifiee"
RULE_DEPENDENCY = "dependance"
RULE_SUSPECT = "lot_suspect"


@dataclass
class Declaration:
    source: str
    since: datetime


class Ledger:
    """A company's ledger: its records + the dependency graph.

    A Ledger never reads another Ledger's records: cross-company
    information only arrives through `register_alert_tokens`.
    """

    def __init__(self, company_id: str) -> None:
        self.company_id = company_id
        self.records: dict[str, Record] = {}
        self.graph = nx.DiGraph()
        self.declarations: list[Declaration] = []
        self.alert_tokens: set[str] = set()
        self.seed_rules: dict[str, str] = {}
        self.suspects: dict[str, str] = {}  # record_id -> reason (lot declared suspect)
        self.audit = AuditLog(company_id)

    def add(self, record: Record) -> Record:
        if record.company != self.company_id:
            raise ValueError(
                f"record {record.id} belongs to {record.company}, not to {self.company_id}"
            )
        if record.id in self.records:
            raise ValueError(f"record already present: {record.id}")
        self.records[record.id] = record
        self.graph.add_node(record.id)
        for parent in record.inputs:
            self.graph.add_edge(parent, record.id)
        return record

    def declaration(self, source: str) -> Declaration | None:
        return next((d for d in self.declarations if d.source == source), None)

    def declare_compromised(self, source: str, since: datetime) -> Declaration:
        """One declaration per source; if times differ, the earliest wins.
        Returns the declaration in force."""
        decl = self.declaration(source)
        if decl is None:
            decl = Declaration(source=source, since=since)
            self.declarations.append(decl)
        elif since < decl.since:
            decl.since = since
        return decl

    def withdraw_declaration(self, source: str) -> Declaration | None:
        decl = self.declaration(source)
        if decl is not None:
            self.declarations.remove(decl)
        return decl

    def register_alert_tokens(self, tokens: list[str]) -> None:
        self.alert_tokens.update(tokens)

    def release_alert_tokens(self, tokens: list[str]) -> None:
        self.alert_tokens.difference_update(tokens)

    def mark_suspect(self, record_ids: list[str], reason: str) -> None:
        """Declares specific records (a lot) suspect, without touching the rest
        of what their sender sent."""
        for rid in record_ids:
            if rid not in self.records:
                raise KeyError(rid)
        for rid in record_ids:
            self.suspects[rid] = reason
            if self.records[rid].status == "released":
                self.records[rid].status = "ok"  # a defect found afterwards reopens the case

    def clear_suspect(self, record_ids: list[str]) -> None:
        for rid in record_ids:
            self.suspects.pop(rid, None)

    def _seeds(self) -> dict[str, str]:
        """Seeds -> rule that triggered them."""
        seeds: dict[str, str] = {}
        for r in self.records.values():
            if r.id in self.suspects:
                seeds[r.id] = RULE_SUSPECT
                continue
            if r.token is not None and r.token in self.alert_tokens:
                seeds[r.id] = RULE_ALERT
                continue
            for decl in self.declarations:
                if r.origin == decl.source and r.ts >= decl.since:
                    seeds[r.id] = RULE_SOURCE
                    break
        return seeds

    def recompute(self) -> tuple[list[str], list[str]]:
        """Recomputes taint from scratch. Deterministic and idempotent.

        Returns (newly quarantined, cleared from quarantine without
        remediation), in record insertion order."""
        before = {rid: r.status for rid, r in self.records.items()}
        for r in self.records.values():
            r.taint_path = None
            if r.status != "released":
                r.status = "ok"

        seeds = self._seeds()
        self.seed_rules = seeds
        parent: dict[str, str | None] = {}
        queue: deque[str] = deque()

        for rid in self.records:  # insertion order: deterministic
            if rid in seeds:
                parent.setdefault(rid, None)
                queue.append(rid)

        tainted: set[str] = set()
        while queue:
            rid = queue.popleft()
            if rid in tainted:
                continue
            record = self.records[rid]
            explicit = rid in self.suspects  # human declaration: overrides a past check
            if not explicit and (record.verified or record.status == "released"):
                continue  # never tainted, stops propagation
            tainted.add(rid)
            p = parent.get(rid)
            if p is None:
                record.taint_path = [rid]
            else:
                record.taint_path = (self.records[p].taint_path or [p]) + [rid]
            for succ in self.graph.successors(rid):
                if succ not in parent:
                    parent[succ] = rid
                    queue.append(succ)

        for rid in tainted:
            self.records[rid].status = "quarantined"

        entered = [rid for rid, r in self.records.items()
                   if r.status == "quarantined" and before[rid] != "quarantined"]
        cleared = [rid for rid, r in self.records.items()
                   if r.status == "ok" and before[rid] == "quarantined"]
        return entered, cleared

    def quarantine_rule(self, record_id: str) -> str:
        """Deterministic rule that quarantined this record."""
        return self.seed_rules.get(record_id, RULE_DEPENDENCY)

    def counters(self) -> dict:
        total = len(self.records)
        quarantined = sum(1 for r in self.records.values() if r.status == "quarantined")
        released = sum(1 for r in self.records.values() if r.status == "released")
        gates_blocked = sum(
            1 for r in self.records.values() if r.status == "quarantined" and r.gate
        )
        amount_blocked = sum(
            payment_amount(r)
            for r in self.records.values() if r.status == "quarantined"
        )
        amount_flowing = sum(
            payment_amount(r)
            for r in self.records.values() if r.status != "quarantined"
        )
        return {
            "total": total,
            "quarantined": quarantined,
            "ok": total - quarantined - released,
            "released": released,
            "gates_blocked": gates_blocked,
            "amount_blocked": amount_blocked,
            "amount_flowing": amount_flowing,
        }
