"""Ce qu'on ancre après chaque action. Lecture seule sur la simulation."""

from __future__ import annotations

from datetime import datetime

from .client import AnchorRecord, ChainClient, ChainOp
from .ids import ALERT_TYPE, alert_hash, company_id, declaration_hash, hex32, new_run_id


def _epoch(iso: str) -> int:
    return max(0, int(datetime.fromisoformat(iso).timestamp()))


class Anchorer:
    def __init__(self, client: ChainClient) -> None:
        self.client = client
        self.run_id = new_run_id()
        self._alerts_seen = 0
        self._acked: set[int] = set()
        self._entries_seen: dict[str, int] = {}
        self._anchored_lens: dict[str, int] = {}

    def on_new_simulation(self, sim) -> None:
        """Nouveau run : on ne ré-ancre pas l'historique déjà présent."""
        self.run_id = new_run_id()
        self._alerts_seen = len(sim.federation.alerts)
        self._acked = set(range(self._alerts_seen))
        self._entries_seen = {c: len(led.audit) for c, led in sim.ledgers.items()}
        self._anchored_lens = dict(self._entries_seen)

    def after_action(self, sim, action: str) -> list[AnchorRecord]:
        out: list[AnchorRecord] = []
        try:
            out += self._alerts(sim)
            out += self._incidents(sim)
            out += self._audits(sim, force=False)
        except Exception:
            pass  # l'ancrage ne doit jamais casser une action métier
        return out

    def anchor_all(self, sim) -> list[AnchorRecord]:
        """Ancre les têtes de tous les journaux (POST /api/chain/anchor)."""
        return self._audits(sim, force=True)

    def _alerts(self, sim) -> list[AnchorRecord]:
        out = []
        alerts = sim.federation.alerts
        for i in range(self._alerts_seen, len(alerts)):
            a = alerts[i]
            h = alert_hash(a)
            out.append(self.client.submit(ChainOp(
                "alert", a.sender, "anchorAlert",
                (self.run_id, h, company_id(a.recipient), ALERT_TYPE[a.type]),
                hex32(h))))
        self._alerts_seen = len(alerts)
        for i, a in enumerate(alerts):
            if i in self._acked or not a.verified:
                continue
            self._acked.add(i)
            h = alert_hash(a)
            out.append(self.client.submit(ChainOp(
                "ack", a.recipient, "acknowledgeAlert", (h,), hex32(h))))
        return out

    def _incidents(self, sim) -> list[AnchorRecord]:
        out = []
        for cid, led in sim.ledgers.items():
            entries = led.audit.entries()
            for e in entries[self._entries_seen.get(cid, 0):]:
                if e["event"] == "declaration":
                    d = e["details"]
                    h = declaration_hash(d["source"], d["since"], cid)
                    out.append(self.client.submit(ChainOp(
                        "incident", cid, "declareIncident",
                        (self.run_id, company_id(d["source"]), _epoch(d["since"]), h),
                        hex32(h))))
                elif e["event"] == "declaration_withdrawn":
                    d = e["details"]
                    h = declaration_hash(d["source"], d["since"], cid)
                    out.append(self.client.submit(ChainOp(
                        "incident", cid, "withdrawIncident",
                        (self.run_id, company_id(d["source"]), h), hex32(h))))
        return out

    def _audits(self, sim, force: bool) -> list[AnchorRecord]:
        out = []
        for cid, led in sim.ledgers.items():
            n = len(led.audit)
            self._entries_seen[cid] = n
            if n == 0 or (not force and self._anchored_lens.get(cid) == n):
                continue
            self._anchored_lens[cid] = n
            head = led.audit.head
            out.append(self.client.submit(ChainOp(
                "audit", cid, "anchorAudit",
                (self.run_id, bytes.fromhex(head), n), "0x" + head)))
        return out

    def verify_onchain(self, sim) -> dict[str, dict | None]:
        """Pour chaque journal : ancrage lu on-chain comparé au journal local."""
        result: dict[str, dict | None] = {}
        for cid, led in sim.ledgers.items():
            anchor = self.client.read_audit_anchor(self.run_id, cid)
            if anchor is None:
                result[cid] = None
                continue
            n = anchor["anchored_entries"]
            entries = led.audit.entries()
            local = entries[n - 1]["hash"] if 0 < n <= len(entries) else None
            result[cid] = {**anchor, "matches": local == anchor["anchored_head"]}
        return result
