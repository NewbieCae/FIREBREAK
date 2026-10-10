"""Démo : réécrire un journal d'audit en recalculant tous les hash.

La vérification locale reste intègre ; seul l'ancrage on-chain révèle la fraude.
"""

from __future__ import annotations

from datetime import datetime

from ..audit import AuditLog


def rewrite_journal(sim, company: str, drop_event: str) -> int:
    """Supprime la première entrée `drop_event` du journal de `company` et
    reconstruit une chaîne cohérente. Renvoie l'index supprimé."""
    ledger = sim.ledgers[company]
    entries = ledger.audit.entries()
    drop = next((i for i, e in enumerate(entries) if e["event"] == drop_event), None)
    if drop is None:
        raise ValueError(f"aucune entrée « {drop_event} » dans le journal de {company}")
    rebuilt = AuditLog(company)
    for i, e in enumerate(entries):
        if i != drop:
            rebuilt.append(datetime.fromisoformat(e["ts"]), e["event"], e["actor"],
                           e["details"])
    ledger.audit = rebuilt
    return drop
