"""Simulation Firebreak : registres + fédération, propagation à point fixe."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .engine import Ledger
from .federation import Federation
from .model import Company, Record

REMEDIATION_ACTIONS = {"revalidate", "human_approval", "trusted_source"}
SCENARIO_TZ = ZoneInfo("Europe/Paris")


def to_scenario_time(dt: datetime) -> datetime:
    """Les horodatages du scénario sont naïfs, en heure de Paris. Une date
    avec fuseau (ex. « …Z ») est convertie, sinon la comparaison échoue."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(SCENARIO_TZ).replace(tzinfo=None)


def serialize_record(r: Record) -> dict:
    return {
        "id": r.id,
        "company": r.company,
        "origin": r.origin,
        "kind": r.kind,
        "ts": r.ts.isoformat(),
        "label": r.label,
        "inputs": list(r.inputs),
        "gate": r.gate,
        "verified": r.verified,
        "payload": dict(r.payload),
        "token": r.token,
        "status": r.status,
        "taint_path": list(r.taint_path) if r.taint_path is not None else None,
    }


class Simulation:
    def __init__(
        self,
        companies: list[Company],
        ledgers: dict[str, Ledger],
        federation: Federation,
    ) -> None:
        self.companies = companies
        self.ledgers = ledgers
        self.federation = federation
        self._alert_time = datetime(2026, 10, 10, 15, 0, 0)

    # -- propagation ------------------------------------------------------

    def run(self) -> None:
        """Recompute tous les registres puis alertes, jusqu'à point fixe.

        Chaque tour qui émet au moins une alerte consomme au moins un lien
        non encore alerté : le point fixe est atteint en ≤ len(links) + 1 tours."""
        for _ in range(len(self.federation.links) + 1):
            for ledger in self.ledgers.values():
                ledger.recompute()
            alerts = self.federation.emit_alerts(self.ledgers, self._alert_time)
            if not alerts:
                break
            self._alert_time += timedelta(minutes=1)
            for alert in alerts:
                self.federation.deliver(alert, self.ledgers)

    def declare_compromise(self, company: str, since: datetime) -> None:
        """L'entreprise compromise se déclare elle-même et ses partenaires
        directs (ceux qui ont reçu ses données) la déclarent aussi."""
        since = to_scenario_time(since)
        self.ledgers[company].declare_compromised(company, since)
        partners = {
            link.recipient
            for link in self.federation.links
            if link.sender == company
        }
        for partner in sorted(partners):
            self.ledgers[partner].declare_compromised(company, since)
        self.run()

    def remediate(self, record_id: str, action: str) -> Record:
        if action not in REMEDIATION_ACTIONS:
            raise ValueError(f"action inconnue: {action}")
        record = self.find_record(record_id)
        if record is None:
            raise KeyError(record_id)
        if record.status != "quarantined":
            raise ValueError("record non mis en quarantaine")
        record.status = "released"
        self.run()  # recompute complet : libère les descendants qui ne
        # dépendaient que de ce record, refait tourner la fédération
        return record

    # -- accès ------------------------------------------------------------

    def find_record(self, record_id: str) -> Record | None:
        for ledger in self.ledgers.values():
            if record_id in ledger.records:
                return ledger.records[record_id]
        return None

    def path_records(self, record: Record) -> list[Record]:
        ledger = self.ledgers[record.company]
        return [
            ledger.records[rid]
            for rid in (record.taint_path or [])
            if rid in ledger.records
        ]

    # -- état sérialisable ------------------------------------------------

    def state(self) -> dict:
        records = [
            serialize_record(r)
            for ledger in self.ledgers.values()
            for r in ledger.records.values()
        ]
        edges = []
        for ledger in self.ledgers.values():
            for src, dst in ledger.graph.edges():
                edges.append({"source": src, "target": dst, "cross": False})
        for link in self.federation.links:
            edges.append(
                {
                    "source": link.sender_record,
                    "target": link.recipient_record,
                    "cross": True,
                }
            )
        per_company = {cid: led.counters() for cid, led in self.ledgers.items()}
        global_counters = {
            key: sum(c[key] for c in per_company.values())
            for key in ("total", "quarantined", "ok", "released", "gates_blocked")
        }
        alerts = [
            {
                "from": a.sender,
                "to": a.recipient,
                "tokens_count": len(a.tokens),
                "verified": a.verified,
                "issued_at": a.issued_at.isoformat(),
            }
            for a in self.federation.alerts
        ]
        declarations = [
            {
                "ledger": cid,
                "source": d.source,
                "since": d.since.isoformat(),
            }
            for cid, led in self.ledgers.items()
            for d in led.declarations
        ]
        return {
            "companies": [vars(c) for c in self.companies],
            "records": records,
            "edges": edges,
            "counters": {"global": global_counters, "per_company": per_company},
            "alerts": alerts,
            "declarations": declarations,
        }
