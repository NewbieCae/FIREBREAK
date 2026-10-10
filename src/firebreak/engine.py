"""Moteur de contamination (taint) d'un registre Firebreak.

Règles :
- seeds = records dont l'origine est une entreprise déclarée compromise
  (et ts >= since), ou dont le `token` figure dans une alerte vérifiée
  (et pas encore levée par une alerte « release » vérifiée) ;
- une seule déclaration par source : on garde l'heure la plus ancienne ;
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

from .audit import AuditLog
from .model import Record

RULE_SOURCE = "source_compromise"
RULE_ALERT = "alerte_verifiee"
RULE_DEPENDENCY = "dependance"


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
        self.seed_rules: dict[str, str] = {}
        self.audit = AuditLog(company_id)

    def add(self, record: Record) -> Record:
        if record.company != self.company_id:
            raise ValueError(
                f"record {record.id} appartient à {record.company}, pas à {self.company_id}"
            )
        if record.id in self.records:
            raise ValueError(f"record déjà présent: {record.id}")
        self.records[record.id] = record
        self.graph.add_node(record.id)
        for parent in record.inputs:
            self.graph.add_edge(parent, record.id)
        return record

    def declaration(self, source: str) -> Declaration | None:
        return next((d for d in self.declarations if d.source == source), None)

    def declare_compromised(self, source: str, since: datetime) -> Declaration:
        """Une déclaration par source ; à heure différente, la plus ancienne
        l'emporte. Renvoie la déclaration en vigueur."""
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

    def _seeds(self) -> dict[str, str]:
        """Seeds -> règle qui les a déclenchés."""
        seeds: dict[str, str] = {}
        for r in self.records.values():
            if r.token is not None and r.token in self.alert_tokens:
                seeds[r.id] = RULE_ALERT
                continue
            for decl in self.declarations:
                if r.origin == decl.source and r.ts >= decl.since:
                    seeds[r.id] = RULE_SOURCE
                    break
        return seeds

    def recompute(self) -> tuple[list[str], list[str]]:
        """Recalcule la contamination depuis zéro. Déterministe et idempotent.

        Renvoie (nouvellement en quarantaine, sortis de quarantaine sans
        remédiation), dans l'ordre d'insertion des records."""
        before = {rid: r.status for rid, r in self.records.items()}
        for r in self.records.values():
            r.taint_path = None
            if r.status != "released":
                r.status = "ok"

        seeds = self._seeds()
        self.seed_rules = seeds
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

        entered = [rid for rid, r in self.records.items()
                   if r.status == "quarantined" and before[rid] != "quarantined"]
        cleared = [rid for rid, r in self.records.items()
                   if r.status == "ok" and before[rid] == "quarantined"]
        return entered, cleared

    def quarantine_rule(self, record_id: str) -> str:
        """Règle déterministe qui a mis ce record en quarantaine."""
        return self.seed_rules.get(record_id, RULE_DEPENDENCY)

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
