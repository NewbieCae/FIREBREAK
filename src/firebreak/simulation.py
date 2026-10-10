"""Simulation Firebreak : registres + fédération, propagation à point fixe."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .audit import Actor
from .engine import Ledger
from .federation import Alert, Federation
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
        scenario: dict | None = None,
    ) -> None:
        self.scenario = scenario
        self.companies = companies
        self.ledgers = ledgers
        self.federation = federation
        self.clock = datetime(2026, 10, 10, 15, 0, 0)  # heure du scénario

    # -- propagation ------------------------------------------------------

    def _recompute_all(self) -> None:
        for cid, ledger in self.ledgers.items():
            entered, cleared = ledger.recompute()
            for rid in entered:
                r = ledger.records[rid]
                ledger.audit.append(self.clock, "quarantine", "règle", {
                    "record": rid,
                    "rule": ledger.quarantine_rule(rid),
                    "taint_path": list(r.taint_path or []),
                    "gate": r.gate,
                })
            for rid in cleared:
                ledger.audit.append(self.clock, "release", "règle", {
                    "record": rid,
                    "reason": "ne dépend plus d'aucune donnée suspecte",
                })

    def run(self) -> None:
        """Recompute tous les registres puis alertes (contamination et
        levée), jusqu'à point fixe.

        Chaque lien bascule au plus une fois par sens (signalé / levé) par
        tour : sur une chaîne sans cycle, le point fixe est atteint en
        ≤ 2 × len(links) + 1 tours. Au-delà, on lève une erreur plutôt que
        de renvoyer un état non stabilisé."""
        for _ in range(2 * len(self.federation.links) + 2):
            self._recompute_all()
            alerts = self.federation.emit_alerts(self.ledgers, self.clock)
            if not alerts:
                return
            for alert in alerts:
                self.ledgers[alert.sender].audit.append(
                    self.clock, "alert_sent", "règle", self._alert_details(alert))
            self.clock += timedelta(minutes=1)
            for alert in alerts:
                self._deliver(alert)
        raise RuntimeError("propagation non stabilisée")

    def _deliver(self, alert: Alert) -> bool:
        ok = self.federation.deliver(alert, self.ledgers)
        recipient = self.ledgers.get(alert.recipient)
        if recipient is not None:
            recipient.audit.append(self.clock, "alert_received", "règle", {
                **self._alert_details(alert),
                "verified": ok,
                "outcome": "appliquée" if ok else "rejetée : signature invalide",
            })
        return ok

    @staticmethod
    def _alert_details(alert: Alert) -> dict:
        return {
            "type": alert.type,
            "from": alert.sender,
            "to": alert.recipient,
            "tokens": sorted(alert.tokens),
            "issued_at": alert.issued_at.isoformat(),
            "signature": alert.signature,
        }

    def _declaring_ledgers(self, company: str) -> list[str]:
        """L'entreprise compromise et ses partenaires directs (ceux qui ont
        reçu ses données)."""
        partners = {
            link.recipient
            for link in self.federation.links
            if link.sender == company
        }
        return [company] + sorted(partners - {company})

    def declare_compromise(self, company: str, since: datetime) -> None:
        """L'entreprise compromise se déclare elle-même et ses partenaires
        directs la déclarent aussi. Redéclarer la même source garde l'heure
        la plus ancienne."""
        since = to_scenario_time(since)
        for cid in self._declaring_ledgers(company):
            ledger = self.ledgers[cid]
            decl = ledger.declare_compromised(company, since)
            ledger.audit.append(self.clock, "declaration", "humain", {
                "source": company,
                "since": since.isoformat(),
                "effective_since": decl.since.isoformat(),
            })
        self.run()

    def withdraw_compromise(self, company: str) -> None:
        """Retire la déclaration (fausse alerte) partout où elle est
        enregistrée, puis recalcule : les levées partent en cascade."""
        withdrawn = False
        for cid, ledger in self.ledgers.items():
            decl = ledger.withdraw_declaration(company)
            if decl is None:
                continue
            withdrawn = True
            ledger.audit.append(self.clock, "declaration_withdrawn", "humain", {
                "source": company,
                "since": decl.since.isoformat(),
            })
        if not withdrawn:
            raise ValueError(f"aucune déclaration active pour {company}")
        self.run()

    def remediate(self, record_id: str, action: str, actor: Actor = "humain") -> Record:
        if action not in REMEDIATION_ACTIONS:
            raise ValueError(f"action inconnue: {action}")
        record = self.find_record(record_id)
        if record is None:
            raise KeyError(record_id)
        if record.status != "quarantined":
            raise ValueError("record non mis en quarantaine")
        record.status = "released"
        self.ledgers[record.company].audit.append(self.clock, "remediation", actor, {
            "record": record_id,
            "action": action,
            "taint_path": list(record.taint_path or []),
        })
        self.run()  # recompute complet : libère les descendants qui ne
        # dépendaient que de ce record, puis levées signées vers l'aval
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

    # -- audit ------------------------------------------------------------

    def audit_verify(self, company: str | None = None) -> dict:
        ids = [company] if company is not None else list(self.ledgers)
        journals = []
        for cid in ids:
            audit = self.ledgers[cid].audit
            broken = audit.verify()
            journals.append({
                "company": cid,
                "ok": broken is None,
                "entries": len(audit),
                "first_broken_index": broken,
                "head": audit.head,
            })
        first = next((j for j in journals if not j["ok"]), None)
        return {
            "ok": first is None,
            "first_broken": (
                {"company": first["company"], "index": first["first_broken_index"]}
                if first else None
            ),
            "journals": journals,
        }

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
                "type": a.type,
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
            "scenario": self.scenario,
        }
