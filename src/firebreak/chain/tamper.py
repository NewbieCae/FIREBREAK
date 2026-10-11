"""Demo: rewrite an audit journal and recompute every hash.

The local verification still passes; only the on-chain anchor reveals the fraud.
"""

from __future__ import annotations

from datetime import datetime

from ..audit import AuditLog


def rewrite_journal(sim, company: str, drop_event: str) -> int:
    """Removes the first `drop_event` entry from `company`'s journal and
    rebuilds a consistent chain. Returns the removed index."""
    ledger = sim.ledgers[company]
    entries = ledger.audit.entries()
    drop = next((i for i, e in enumerate(entries) if e["event"] == drop_event), None)
    if drop is None:
        raise ValueError(f"no \"{drop_event}\" entry in {company}'s journal")
    rebuilt = AuditLog(company)
    for i, e in enumerate(entries):
        if i != drop:
            rebuilt.append(datetime.fromisoformat(e["ts"]), e["event"], e["actor"],
                           e["details"])
    ledger.audit = rebuilt
    return drop
