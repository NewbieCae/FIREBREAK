"""Firebreak simulation: ledgers + federation, fixed-point propagation."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import networkx as nx

from .audit import Actor
from .engine import Ledger
from .federation import Alert, Federation, QualityReport
from .genealogy import lot_of, records_of_lot
from .model import Company, Record, payment_amount

REMEDIATION_ACTIONS = {"revalidate", "human_approval", "trusted_source"}
INBOUND_HOLD_REASON = "awaiting goods-receipt validation"
SCENARIO_TZ = ZoneInfo("Europe/Paris")


def to_scenario_time(dt: datetime) -> datetime:
    """Scenario timestamps are naive, in Paris time. A timezone-aware date
    (e.g. "...Z") is converted, otherwise the comparison fails."""
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
        self.clock = datetime(2026, 10, 10, 15, 0, 0)  # scenario time
        self.timeline: list[dict] = []  # steps of the last action

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
                    "reason": "no longer depends on any suspect data",
                })

    def run(self) -> None:
        """Recomputes all ledgers then alerts (taint and release), until a
        fixed point.

        Each link flips at most once per direction (reported / released) per
        round: on an acyclic chain, the fixed point is reached in
        <= 2 x len(links) + 1 rounds. Beyond that, raise an error rather than
        return a non-stabilized state."""
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
        raise RuntimeError("propagation did not stabilize")

    def _deliver(self, alert: Alert) -> bool:
        ok = self.federation.deliver(alert, self.ledgers)
        recipient = self.ledgers.get(alert.recipient)
        if recipient is not None:
            recipient.audit.append(self.clock, "alert_received", "règle", {
                **self._alert_details(alert),
                "verified": ok,
                "outcome": "applied" if ok else "rejected: invalid signature",
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
        """The compromised company and its direct partners (those that
        received its data)."""
        partners = {
            link.recipient
            for link in self.federation.links
            if link.sender == company
        }
        return [company] + sorted(partners - {company})

    def declare_compromise(self, company: str, since: datetime) -> None:
        """The compromised company declares itself and its direct partners
        declare it too. Re-declaring the same source keeps the earliest
        time."""
        since = to_scenario_time(since)
        marks = self.audit_marks()
        for cid in self._declaring_ledgers(company):
            ledger = self.ledgers[cid]
            decl = ledger.declare_compromised(company, since)
            ledger.audit.append(self.clock, "declaration", "humain", {
                "source": company,
                "since": since.isoformat(),
                "effective_since": decl.since.isoformat(),
            })
        self.run()
        self.timeline = self.collect_timeline(marks)

    def withdraw_compromise(self, company: str) -> None:
        """Withdraws the declaration (false alarm) everywhere it is
        recorded, then recomputes: releases cascade downstream."""
        withdrawn = False
        marks = self.audit_marks()
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
            raise ValueError(f"no active declaration for {company}")
        self.run()
        self.timeline = self.collect_timeline(marks)

    def remediate(self, record_id: str, action: str, actor: Actor = "humain") -> Record:
        if action not in REMEDIATION_ACTIONS:
            raise ValueError(f"unknown action: {action}")
        record = self.find_record(record_id)
        if record is None:
            raise KeyError(record_id)
        if record.status != "quarantined":
            raise ValueError("record not quarantined")
        marks = self.audit_marks()
        record.status = "released"
        self.ledgers[record.company].audit.append(self.clock, "remediation", actor, {
            "record": record_id,
            "action": action,
            "taint_path": list(record.taint_path or []),
        })
        self.run()  # full recompute: frees the descendants that only
        # depended on this record, then signed releases downstream
        self.timeline = self.collect_timeline(marks)
        return record

    # -- quality: suspect lot, recall, upstream report ---------------------

    def _lot_records(self, company: str, lot: str) -> list[str]:
        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        ids = records_of_lot(ledger, lot)
        if not ids:
            raise KeyError(lot)
        return ids

    def _ref_records(self, company: str, ref: str) -> list[str]:
        """`ref` = id of a record in the ledger, or a lot number."""
        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        if ref in ledger.records:
            return [ref]
        return self._lot_records(company, ref)

    def declare_lot_suspect(self, company: str, lot: str, reason: str,
                            actor: Actor = "humain") -> list[str]:
        """Isolates a specific lot in `company`'s ledger: that lot and
        everything depending on it, at the company and then at its customers
        (signed alerts). Its supplier is not declared compromised: its other
        lots, invoices and payments keep flowing."""
        ids = self._ref_records(company, lot)  # lot number or record id
        marks = self.audit_marks()
        ledger = self.ledgers[company]
        ledger.mark_suspect(ids, reason)
        ledger.audit.append(self.clock, "lot_suspect", actor, {
            "lot": lot, "records": ids, "reason": reason,
        })
        self.run()
        self.timeline = self.collect_timeline(marks)
        return ids

    def withdraw_lot_suspect(self, company: str, lot: str,
                             actor: Actor = "humain") -> list[str]:
        """Lifts the suspicion (conclusive analysis): releases cascade downstream."""
        ids = self._ref_records(company, lot)  # lot number or record id
        ledger = self.ledgers[company]
        active = [rid for rid in ids if rid in ledger.suspects]
        if not active:
            raise ValueError(f"lot {lot} is not declared suspect at {company}")
        marks = self.audit_marks()
        ledger.clear_suspect(active)
        ledger.audit.append(self.clock, "lot_suspect_withdrawn", actor, {
            "lot": lot, "records": active,
        })
        self.run()
        self.timeline = self.collect_timeline(marks)
        return active

    def recall_analysis(self, company: str, ref: str) -> dict:
        """Defect found late on a product (record or lot): walks up its
        genealogy in `company`'s ledger and lists the possible causes
        (consumed lots, data received from partners), each with the scope
        that blaming it would isolate. Read-only: the quality analyst picks
        the cause and declares the lot suspect."""
        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        targets = self._ref_records(company, ref)
        ancestors: set[str] = set()
        for rid in targets:
            ancestors |= nx.ancestors(ledger.graph, rid)
        sends: dict[str, set[str]] = {}
        for link in self.federation.links:
            if link.sender == company:
                sends.setdefault(link.sender_record, set()).add(link.recipient)
        candidates = []
        for rid in sorted(ancestors, key=lambda i: (ledger.records[i].ts, i)):
            r = ledger.records[rid]
            received = r.token is not None and r.origin != company
            if lot_of(r) is None and not received:
                continue  # internal step without a lot: not a cause to point at
            scope = {rid} | nx.descendants(ledger.graph, rid)
            candidates.append({
                "record": rid, "label": r.label, "kind": r.kind, "lot": lot_of(r),
                "origin": r.origin, "received": received, "verified": r.verified,
                "impact_records": len(scope),
                "impact_gates": sum(1 for i in scope if ledger.records[i].gate),
                "impact_partners": sorted({p for i in scope for p in sends.get(i, ())}),
            })
        first = ledger.records[targets[0]]
        return {
            "company": company,
            "target": {"ref": ref, "records": targets, "label": first.label,
                       "lot": lot_of(first)},
            "candidates": candidates,
        }

    def report_upstream(self, company: str, ref: str, reason: str,
                        actor: Actor = "humain") -> list[dict]:
        """Signed quality report to the origin of the received data used for
        `ref` (lot or record; one report per partner). Quarantines nothing
        at their end: they decide case by case (`decide_report`). Each link
        in the chain can in turn report further upstream."""
        ledger = self.ledgers[company] if company in self.ledgers else None
        if ledger is None:
            raise KeyError(company)
        carriers = self._ref_records(company, ref)
        lot = ref
        scope: set[str] = set(carriers)
        for rid in carriers:
            scope |= nx.ancestors(ledger.graph, rid)
        by_origin: dict[str, list[str]] = {}
        for rid in sorted(scope):
            r = ledger.records[rid]
            if r.token is not None and r.origin != company:
                by_origin.setdefault(r.origin, []).append(r.token)
        if not by_origin:
            raise ValueError(f"{ref} does not depend on any data received from a partner")
        marks = self.audit_marks()
        out = []
        for origin, tokens in sorted(by_origin.items()):
            report = self.federation.make_report(company, origin, tokens, reason, self.clock)
            ledger.audit.append(self.clock, "quality_report_sent", actor, {
                **self._report_details(report), "ref": lot,
            })
            self.clock += timedelta(minutes=1)
            self.federation.receive_report(report)
            self.ledgers[origin].audit.append(self.clock, "quality_report_received", "règle", {
                **self._report_details(report), "verified": report.verified,
                "records": list(report.records),
            })
            out.append(self._report_view(report))
        self.timeline = self.collect_timeline(marks)
        return out

    def reports(self, company: str | None = None) -> list[dict]:
        return [self._report_view(r) for r in self.federation.reports
                if company is None or company in (r.sender, r.recipient)]

    def decide_report(self, company: str, report_id: str, decision: str,
                      actor: Actor = "humain") -> dict:
        """The supplier decides: `confirm` declares its questioned records
        suspect (then alerts every customer depending on them), `reject`
        closes the report without blocking anything."""
        report = next((r for r in self.federation.reports if r.id == report_id), None)
        if report is None or report.recipient != company:
            raise KeyError(report_id)
        if report.status != "pending":
            raise ValueError(f"report {report_id} already handled ({report.status})")
        if decision not in ("confirm", "reject"):
            raise ValueError(f"unknown decision: {decision}")
        if decision == "confirm" and not report.verified:
            raise ValueError("invalid signature: cannot confirm this report")
        marks = self.audit_marks()
        ledger = self.ledgers[company]
        report.status = "confirmed" if decision == "confirm" else "rejected"
        ledger.audit.append(self.clock, "quality_report_decided", actor, {
            "id": report.id, "from": report.sender, "decision": decision,
            "records": list(report.records),
        })
        if decision == "confirm":
            ledger.mark_suspect(report.records,
                                f"report {report.id} from {report.sender}: {report.reason}")
            self.run()
        self.timeline = self.collect_timeline(marks)
        return self._report_view(report)

    @staticmethod
    def _report_details(report: QualityReport) -> dict:
        return {
            "id": report.id, "from": report.sender, "to": report.recipient,
            "tokens": list(report.tokens), "reason": report.reason,
            "issued_at": report.issued_at.isoformat(), "signature": report.signature,
        }

    @staticmethod
    def _report_view(report: QualityReport) -> dict:
        return {
            "id": report.id, "from": report.sender, "to": report.recipient,
            "reason": report.reason, "tokens_count": len(report.tokens),
            "records": list(report.records), "verified": report.verified,
            "status": report.status, "issued_at": report.issued_at.isoformat(),
        }

    # -- inbound stock control --------------------------------------------

    def _referentiel(self, company: str):
        from .inbound import default_referentiels

        if not hasattr(self, "referentiels"):
            self.referentiels = default_referentiels()
        return self.referentiels.get(company)

    def inbound_check(self, company: str, receipt_id: str) -> dict:
        """Trust score of a goods receipt (read-only)."""
        from .inbound import evaluate_receipt

        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        if receipt_id not in ledger.records:
            raise KeyError(receipt_id)
        result = evaluate_receipt(ledger, receipt_id, self._referentiel(company))
        result["status"] = self._inbound_status(company, receipt_id)
        return result

    def _inbound_status(self, company: str, receipt_id: str) -> str:
        ledger = self.ledgers[company]
        decided = {e["details"].get("receipt"): e["event"]
                   for e in ledger.audit.entries()
                   if e["event"] in ("inbound_hold", "inbound_accepted", "inbound_rejected")}
        return {"inbound_hold": "en_attente", "inbound_accepted": "accepte",
                "inbound_rejected": "refuse"}.get(decided.get(receipt_id), "non_controle")

    def inbound_screen(self, company: str, receipt_id: str, actor: Actor = "règle") -> dict:
        """Checks a goods receipt; below the threshold, puts it on hold (it and
        everything depending on it) until a human decides."""
        marks = self.audit_marks()
        result = self._screen_one(company, receipt_id, actor)
        if result["hold"]:
            self.run()
        self.timeline = self.collect_timeline(marks)
        result["status"] = self._inbound_status(company, receipt_id)
        return result

    def _screen_one(self, company: str, receipt_id: str, actor: Actor) -> dict:
        result = self.inbound_check(company, receipt_id)
        if result["hold"] and result["status"] == "non_controle":
            ledger = self.ledgers[company]
            if receipt_id not in ledger.suspects:  # do not overwrite a suspicion declared elsewhere
                ledger.mark_suspect([receipt_id],
                                    f"{INBOUND_HOLD_REASON} ({result['score']}/100)")
            ledger.audit.append(self.clock, "inbound_hold", actor, {
                "receipt": receipt_id, "score": result["score"], "band": result["band"],
                "supplier": result["supplier"], "lot": result["lot"],
                "failed": [c["id"] for c in result["checks"] if not c["ok"]],
            })
        return result

    def inbound_screen_all(self, company: str, actor: Actor = "règle") -> list[dict]:
        """Screens all of `company`'s goods receipts that come from a
        partner, in chronological order."""
        from .inbound import RECEIPT_KINDS

        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        receipts = sorted(
            (r for r in ledger.records.values()
             if r.kind in RECEIPT_KINDS and any(
                 ledger.records[i].token is not None for i in r.inputs if i in ledger.records)),
            key=lambda r: (r.ts, r.id))
        marks = self.audit_marks()
        results = [self._screen_one(company, r.id, actor) for r in receipts]
        if any(r["hold"] for r in results):
            self.run()
        self.timeline = self.collect_timeline(marks)
        for r in results:
            r["status"] = self._inbound_status(company, r["receipt"])
        return results

    def inbound_decide(self, company: str, receipt_id: str, decision: str,
                       reason: str = "", actor: Actor = "humain") -> dict:
        """Human decision on a goods receipt put on hold.
        `accept`: the hold is lifted and the receipt becomes trusted
        (`verified`); `reject`: it stays isolated and a signed quality
        report goes out to the supplier."""
        if decision not in ("accept", "reject"):
            raise ValueError(f"unknown decision: {decision}")
        status = self.inbound_check(company, receipt_id)["status"]
        if status in ("accepte", "refuse"):
            raise ValueError(f"receipt {receipt_id} already handled ({status})")
        ledger = self.ledgers[company]
        record = ledger.records[receipt_id]
        marks = self.audit_marks()
        out: dict = {"receipt": receipt_id, "decision": decision, "reports": []}
        if decision == "accept":
            if status != "en_attente":
                raise ValueError(f"receipt {receipt_id} is not on hold: nothing to accept "
                                 "(check it first)")
            other = ledger.suspects.get(receipt_id)
            if other is not None and not other.startswith(INBOUND_HOLD_REASON):
                raise ValueError(f"receipt {receipt_id} declared suspect elsewhere "
                                 f"({other}): lift that suspicion first")
            ledger.clear_suspect([receipt_id])
            record.verified = True
            ledger.audit.append(self.clock, "inbound_accepted", actor, {
                "receipt": receipt_id, "reason": reason or "conclusive human check",
            })
            self.run()
        else:
            if receipt_id not in ledger.suspects:
                ledger.mark_suspect([receipt_id], "receipt rejected")
            ledger.audit.append(self.clock, "inbound_rejected", actor, {
                "receipt": receipt_id, "reason": reason or "receipt rejected",
            })
            self.run()
            try:
                out["reports"] = self.report_upstream(
                    company, receipt_id, reason or "receipt rejected at inbound check", actor)
            except ValueError:
                out["reports"] = []
        self.timeline = self.collect_timeline(marks)
        out["status"] = self._inbound_status(company, receipt_id)
        return out

    # -- timeline (step-by-step replay) ------------------------------------

    def audit_marks(self) -> dict[str, int]:
        """Position of each audit log, to measure an action."""
        return {cid: len(led.audit) for cid, led in self.ledgers.items()}

    def _record(self, rid: str) -> Record | None:
        return self.find_record(rid)

    def _amount(self, rid: str) -> float:
        r = self._record(rid)
        return payment_amount(r) if r is not None else 0

    def collect_timeline(self, marks: dict[str, int] | None = None) -> list[dict]:
        """Converts the audit entries added since `marks` (all if None) into
        ordered replay steps, with cumulative impact counters.

        Order: simulated ts, then company, then index; and, for the same
        instant and ledger, quarantines by path length (a parent always
        precedes its child). Changes no engine result: it is a read of the
        log."""
        new: list[tuple[str, str, dict]] = []
        for cid, ledger in self.ledgers.items():
            start = (marks or {}).get(cid, 0)
            for entry in ledger.audit.entries()[start:]:
                new.append((entry["ts"], cid, entry))
        order = {cid: i for i, cid in enumerate(self.ledgers)}
        new.sort(key=lambda t: (t[0], order[t[1]], t[2]["index"]))
        # Intra-group causality: within the same (ts, ledger), "quarantine"
        # entries are sorted by path length (parent before child) while
        # keeping the positions of the other events.
        ordered: list[tuple[str, str, dict]] = []
        i = 0
        while i < len(new):
            j = i
            while j < len(new) and (new[j][0], new[j][1]) == (new[i][0], new[i][1]):
                j += 1
            grp = new[i:j]
            qpos = {k for k, e in enumerate(grp) if e[2]["event"] == "quarantine"}
            if len(qpos) > 1:
                qs = sorted(
                    (grp[k] for k in qpos),
                    key=lambda t: (len(t[2]["details"].get("taint_path") or []),
                                   t[2]["index"]))
                it = iter(qs)
                grp = [next(it) if k in qpos else grp[k] for k in range(len(grp))]
            ordered.extend(grp)
            i = j
        new = ordered

        # Counters at the start of the replay: current state +/- what the action changed.
        current_q = {
            r.id
            for led in self.ledgers.values()
            for r in led.records.values() if r.status == "quarantined"
        }
        entered = {e["details"]["record"] for _, _, e in new
                   if e["event"] == "quarantine"}
        exited = {e["details"]["record"] for _, _, e in new
                  if e["event"] in ("release", "remediation")}
        qset = (current_q | exited) - entered
        total_amount = sum(
            payment_amount(r)
            for led in self.ledgers.values()
            for r in led.records.values()
        )
        token_links = {link.token: link for link in self.federation.links}

        steps: list[dict] = []
        for ts, cid, entry in new:
            ev, d = entry["event"], entry["details"]
            rid = d.get("record")
            if ev == "quarantine":
                qset.add(rid)
            elif ev in ("release", "remediation") and rid:
                qset.discard(rid)
            blocked_amount = sum(self._amount(r) for r in qset)
            counters = {
                "quarantined": len(qset),
                "gates_blocked": sum(
                    1 for r in qset
                    if self._record(r) is not None and self._record(r).gate
                ),
                "amount_blocked": blocked_amount,
                "amount_flowing": total_amount - blocked_amount,
            }
            steps.append(self._step(len(steps) + 1, ts, cid, ev, d,
                                    counters, token_links))
        return steps

    def _step(self, n: int, ts: str, cid: str, ev: str, d: dict,
              counters: dict, token_links: dict) -> dict:
        rid = d.get("record")
        record = self._record(rid) if rid else None
        path = d.get("taint_path") or []
        parent = path[-2] if len(path) > 1 else None
        rule = d.get("rule")
        alert = None
        if ev in ("alert_sent", "alert_received"):
            links = [
                [token_links[t].sender_record, token_links[t].recipient_record]
                for t in d.get("tokens", []) if t in token_links
            ]
            alert = {
                "type": d.get("type"), "from": d.get("from"), "to": d.get("to"),
                "tokens_count": len(d.get("tokens", [])),
                "verified": d.get("verified"), "links": links,
            }
        if ev == "quarantine":
            if record is not None and record.gate:
                stype = "gate_blocked"
            elif rule in ("source_compromise", "alerte_verifiee", "lot_suspect"):
                stype = "seed"
            else:
                stype = "quarantine"
        else:
            stype = {
                "declaration": "declaration",
                "declaration_withdrawn": "withdrawal",
                "remediation": "remediation",
                "release": "release",
                "alert_sent": "alert_sent",
                "alert_received": "alert_received",
                "lot_suspect": "lot_suspect",
                "lot_suspect_withdrawn": "lot_suspect_withdrawn",
                "quality_report_sent": "report_sent",
                "quality_report_received": "report_received",
                "quality_report_decided": "report_decided",
                "inbound_hold": "inbound_hold",
                "inbound_accepted": "inbound_accepted",
                "inbound_rejected": "inbound_rejected",
            }.get(ev, ev)
        return {
            "n": n, "ts": ts, "type": stype, "company": cid,
            "record": rid, "parent": parent,
            "gate": bool(record.gate) if record else False,
            "label": record.label if record else None,
            "rule": rule, "alert": alert,
            "counters": counters,
            "text": self._step_text(stype, cid, d, record, parent),
        }

    def _step_text(self, stype: str, cid: str, d: dict,
                   record: Record | None, parent: str | None) -> str:
        label = record.label if record else ""
        match stype:
            case "declaration":
                since = d.get("effective_since", d.get("since", ""))[:16].replace("T", " ")
                return f"{d.get('source')} declared compromised since {since} (ledger {cid})."
            case "withdrawal":
                return f"Declaration withdrawn for {d.get('source')} (ledger {cid})."
            case "seed":
                return f"Taint seed: \"{label}\" ({cid})."
            case "quarantine":
                p = self._record(parent)
                via = f" via \"{p.label}\"" if p else ""
                return f"\"{label}\" tainted{via} ({cid})."
            case "gate_blocked":
                amount = record.payload.get("amount") if record else None
                m = f" ({amount} €)" if amount else ""
                return f"Irreversible action blocked: \"{label}\"{m} ({cid})."
            case "release":
                return f"\"{label}\" released ({cid})."
            case "remediation":
                return f"Remediation \"{d.get('action')}\" on \"{label}\" ({cid})."
            case "alert_sent":
                kind = "release" if d.get("type") == "release" else "taint"
                return (f"Signed {kind} alert sent: {d.get('from')} → {d.get('to')} "
                        f"({len(d.get('tokens', []))} token(s)).")
            case "alert_received":
                ok = d.get("verified")
                return (f"Alert received at {d.get('to')}: signature "
                        f"{'verified' if ok else 'REJECTED'}.")
            case "inbound_hold":
                return (f"Goods receipt put on hold at {cid}: score {d.get('score')}/100 "
                        f"({d.get('band')}), awaiting a human decision.")
            case "inbound_accepted":
                return f"Goods receipt accepted after check ({cid}): the lot becomes trusted."
            case "inbound_rejected":
                return f"Goods receipt rejected ({cid}): the lot stays isolated."
            case "lot_suspect":
                return (f"Lot {d.get('lot')} declared suspect at {cid}: "
                        f"{d.get('reason')}. The supplier is not blamed.")
            case "lot_suspect_withdrawn":
                return f"Suspicion lifted on lot {d.get('lot')} ({cid})."
            case "report_sent":
                return (f"Signed quality report {d.get('id')}: {d.get('from')} → "
                        f"{d.get('to')} ({len(d.get('tokens', []))} token(s)).")
            case "report_received":
                ok = d.get("verified")
                return (f"Report {d.get('id')} received at {d.get('to')}: signature "
                        f"{'verified' if ok else 'REJECTED'}, awaiting decision.")
            case "report_decided":
                verdict = "confirmed" if d.get("decision") == "confirm" else "rejected"
                return f"Report {d.get('id')} {verdict} by {cid}."
            case _:
                return f"{stype} ({cid})."

    # -- access -----------------------------------------------------------

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

    # -- serializable state -----------------------------------------------

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
            for key in ("total", "quarantined", "ok", "released", "gates_blocked",
                        "amount_blocked", "amount_flowing")
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
