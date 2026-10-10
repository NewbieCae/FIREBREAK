"""Moteur de contamination (taint) d'un registre Firebreak.

Règles :
- seeds = records dont l'origine est une entreprise déclarée compromise
  (et ts >= since), ou dont le `token` figure dans une alerte vérifiée ;
- propagation BFS le long des dépendances (input -> record dérivé) ;
- un record `verified` ou `released` n'est jamais contaminé et stoppe
  la propagation à travers lui ;
- chaque record contaminé garde `taint_path` (chemin seed -> lui-même),
  qui sert de preuve explicable.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

import networkx as nx

from .model import Record


@dataclass
class Declaration:
    source: str
    since: datetime


class Ledger:
    """Registre d'une entreprise : ses records + le graphe de dépendances.

    Un Ledger ne lit jamais les records d'un autre Ledger : l'information
    inter-entreprises n'arrive que par `register_alert_tokens`.
    """

    def __init__(self, company_id: str) -> None:
        self.company_id = company_id
        self.records: dict[str, Record] = {}
        self.graph = nx.DiGraph()
        self.declarations: list[Declaration] = []
        self.alert_tokens: set[str] = set()

    def add(self, record: Record) -> Record:
        assert record.company == self.company_id
        self.records[record.id] = record
        self.graph.add_node(record.id)
        for parent in record.inputs:
            self.graph.add_edge(parent, record.id)
        return record

    def declare_compromised(self, source: str, since: datetime) -> None:
        decl = Declaration(source=source, since=since)
        if decl not in self.declarations:
            self.declarations.append(decl)

    def register_alert_tokens(self, tokens: list[str]) -> None:
        self.alert_tokens.update(tokens)

    def _seeds(self) -> set[str]:
        seeds: set[str] = set()
        for r in self.records.values():
            if r.token is not None and r.token in self.alert_tokens:
                seeds.add(r.id)
                continue
            for decl in self.declarations:
                if r.origin == decl.source and r.ts >= decl.since:
                    seeds.add(r.id)
                    break
        return seeds

    def recompute(self) -> None:
        """Recalcule la contamination depuis zéro. Déterministe et idempotent."""
        for r in self.records.values():
            r.taint_path = None
            if r.status != "released":
                r.status = "ok"

        seeds = self._seeds()
        parent: dict[str, str | None] = {}
        queue: deque[str] = deque()

        for rid in self.records:  # ordre d'insertion : déterministe
            if rid in seeds:
                parent.setdefault(rid, None)
                queue.append(rid)

        tainted: set[str] = set()
        while queue:
            rid = queue.popleft()
            if rid in tainted:
                continue
            record = self.records[rid]
            if record.verified or record.status == "released":
                continue  # jamais contaminé, stoppe la propagation
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

    def counters(self) -> dict:
        total = len(self.records)
        quarantined = sum(1 for r in self.records.values() if r.status == "quarantined")
        released = sum(1 for r in self.records.values() if r.status == "released")
        gates_blocked = sum(
            1 for r in self.records.values() if r.status == "quarantined" and r.gate
        )
        return {
            "total": total,
            "quarantined": quarantined,
            "ok": total - quarantined - released,
            "released": released,
            "gates_blocked": gates_blocked,
        }
