"""Simulation Firebreak : registres + fédération, propagation à point fixe."""

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
        self.timeline: list[dict] = []  # étapes de la dernière action

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
        """Retire la déclaration (fausse alerte) partout où elle est
        enregistrée, puis recalcule : les levées partent en cascade."""
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
            raise ValueError(f"aucune déclaration active pour {company}")
        self.run()
        self.timeline = self.collect_timeline(marks)

    def remediate(self, record_id: str, action: str, actor: Actor = "humain") -> Record:
        if action not in REMEDIATION_ACTIONS:
            raise ValueError(f"action inconnue: {action}")
        record = self.find_record(record_id)
        if record is None:
            raise KeyError(record_id)
        if record.status != "quarantined":
            raise ValueError("record non mis en quarantaine")
        marks = self.audit_marks()
        record.status = "released"
        self.ledgers[record.company].audit.append(self.clock, "remediation", actor, {
            "record": record_id,
            "action": action,
            "taint_path": list(record.taint_path or []),
        })
        self.run()  # recompute complet : libère les descendants qui ne
        # dépendaient que de ce record, puis levées signées vers l'aval
        self.timeline = self.collect_timeline(marks)
        return record

    # -- qualité : lot suspect, rappel, signalement vers l'amont -------------

    def _lot_records(self, company: str, lot: str) -> list[str]:
        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        ids = records_of_lot(ledger, lot)
        if not ids:
            raise KeyError(lot)
        return ids

    def _ref_records(self, company: str, ref: str) -> list[str]:
        """`ref` = id d'un record du registre, ou numéro de lot."""
        ledger = self.ledgers.get(company)
        if ledger is None:
            raise KeyError(company)
        if ref in ledger.records:
            return [ref]
        return self._lot_records(company, ref)

    def declare_lot_suspect(self, company: str, lot: str, reason: str,
                            actor: Actor = "humain") -> list[str]:
        """Isole un lot précis dans le registre de `company` : ce lot et tout
        ce qui en dépend, chez elle puis chez ses clients (alertes signées).
        Son fournisseur n'est pas déclaré compromis : ses autres lots, ses
        factures et ses paiements continuent."""
        ids = self._ref_records(company, lot)  # numéro de lot ou id de record
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
        """Lève la suspicion (analyse concluante) : les levées partent en cascade."""
        ids = self._ref_records(company, lot)  # numéro de lot ou id de record
        ledger = self.ledgers[company]
        active = [rid for rid in ids if rid in ledger.suspects]
        if not active:
            raise ValueError(f"le lot {lot} n'est pas déclaré suspect chez {company}")
        marks = self.audit_marks()
        ledger.clear_suspect(active)
        ledger.audit.append(self.clock, "lot_suspect_withdrawn", actor, {
            "lot": lot, "records": active,
        })
        self.run()
        self.timeline = self.collect_timeline(marks)
        return active

    def recall_analysis(self, company: str, ref: str) -> dict:
        """Défaut constaté tard sur un produit (record ou lot) : remonte sa
        généalogie dans le registre de `company` et liste les causes possibles
        (lots consommés, données reçues de partenaires), avec pour chacune le
        périmètre qu'isolerait sa mise en cause. Lecture seule : c'est
        l'analyste qualité qui choisit la cause et déclare le lot suspect."""
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
                continue  # étape interne sans lot : pas une cause à désigner
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
        """Signalement qualité signé vers l'origine des données reçues qui ont
        servi à `ref` (lot ou record ; un signalement par partenaire). Ne met
        rien en quarantaine chez eux : ils décident au cas par cas
        (`decide_report`). Chaque maillon peut à son tour signaler plus haut."""
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
            raise ValueError(f"{ref} ne dépend d'aucune donnée reçue d'un partenaire")
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
        """Le fournisseur tranche : `confirm` déclare suspects ses records mis
        en cause (puis alerte tous les clients qui en dépendent), `reject`
        clôt le signalement sans rien bloquer."""
        report = next((r for r in self.federation.reports if r.id == report_id), None)
        if report is None or report.recipient != company:
            raise KeyError(report_id)
        if report.status != "pending":
            raise ValueError(f"signalement {report_id} déjà traité ({report.status})")
        if decision not in ("confirm", "reject"):
            raise ValueError(f"décision inconnue: {decision}")
        if decision == "confirm" and not report.verified:
            raise ValueError("signature invalide : impossible de confirmer ce signalement")
        marks = self.audit_marks()
        ledger = self.ledgers[company]
        report.status = "confirmed" if decision == "confirm" else "rejected"
        ledger.audit.append(self.clock, "quality_report_decided", actor, {
            "id": report.id, "from": report.sender, "decision": decision,
            "records": list(report.records),
        })
        if decision == "confirm":
            ledger.mark_suspect(report.records,
                                f"signalement {report.id} de {report.sender} : {report.reason}")
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

    # -- timeline (rejeu pas à pas) ----------------------------------------

    def audit_marks(self) -> dict[str, int]:
        """Position de chaque journal d'audit, pour mesurer une action."""
        return {cid: len(led.audit) for cid, led in self.ledgers.items()}

    def _record(self, rid: str) -> Record | None:
        return self.find_record(rid)

    def _amount(self, rid: str) -> float:
        r = self._record(rid)
        return payment_amount(r) if r is not None else 0

    def collect_timeline(self, marks: dict[str, int] | None = None) -> list[dict]:
        """Convertit les entrées d'audit ajoutées depuis `marks` (toutes si
        None) en étapes ordonnées de rejeu, avec compteurs d'impact cumulés.

        Ordre : ts simulé, puis entreprise, puis index — et, à instant et
        registre égaux, les contaminations par longueur du chemin (un parent
        précède toujours son enfant). Ne change aucun résultat du moteur :
        c'est une lecture du journal."""
        new: list[tuple[str, str, dict]] = []
        for cid, ledger in self.ledgers.items():
            start = (marks or {}).get(cid, 0)
            for entry in ledger.audit.entries()[start:]:
                new.append((entry["ts"], cid, entry))
        order = {cid: i for i, cid in enumerate(self.ledgers)}
        new.sort(key=lambda t: (t[0], order[t[1]], t[2]["index"]))
        # Causalité intra-groupe : dans un même (ts, registre), les entrées
        # "quarantine" se trient par longueur du chemin (parent avant enfant)
        # en conservant les positions des autres événements.
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

        # Compteurs au début du rejeu : état courant ± ce que l'action a changé.
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
                return f"{d.get('source')} déclarée compromise depuis {since} — registre {cid}."
            case "withdrawal":
                return f"Déclaration retirée pour {d.get('source')} — registre {cid}."
            case "seed":
                return f"Semence de contamination : « {label} » ({cid})."
            case "quarantine":
                p = self._record(parent)
                via = f" via « {p.label} »" if p else ""
                return f"« {label} » contaminée{via} ({cid})."
            case "gate_blocked":
                amount = record.payload.get("amount") if record else None
                m = f" ({amount} €)" if amount else ""
                return f"Action irréversible bloquée : « {label} »{m} ({cid})."
            case "release":
                return f"« {label} » libérée ({cid})."
            case "remediation":
                return f"Remédiation « {d.get('action')} » sur « {label} » ({cid})."
            case "alert_sent":
                kind = "levée" if d.get("type") == "release" else "contamination"
                return (f"Alerte signée {kind} émise : {d.get('from')} → {d.get('to')} "
                        f"({len(d.get('tokens', []))} jeton(s)).")
            case "alert_received":
                ok = d.get("verified")
                return (f"Alerte reçue chez {d.get('to')} — signature "
                        f"{'vérifiée' if ok else 'REJETÉE'}.")
            case "lot_suspect":
                return (f"Lot {d.get('lot')} déclaré suspect chez {cid} : "
                        f"{d.get('reason')} — le fournisseur n'est pas mis en cause.")
            case "lot_suspect_withdrawn":
                return f"Suspicion levée sur le lot {d.get('lot')} ({cid})."
            case "report_sent":
                return (f"Signalement qualité signé {d.get('id')} : {d.get('from')} → "
                        f"{d.get('to')} ({len(d.get('tokens', []))} jeton(s)).")
            case "report_received":
                ok = d.get("verified")
                return (f"Signalement {d.get('id')} reçu chez {d.get('to')} — signature "
                        f"{'vérifiée' if ok else 'REJETÉE'}, en attente de décision.")
            case "report_decided":
                verdict = "confirmé" if d.get("decision") == "confirm" else "rejeté"
                return f"Signalement {d.get('id')} {verdict} par {cid}."
            case _:
                return f"{stype} ({cid})."

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
