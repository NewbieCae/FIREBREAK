"""Client, ancrage et réécriture : sans réseau, sans contrat compilé."""

from datetime import datetime

import pytest

from firebreak.chain.anchoring import Anchorer
from firebreak.chain.client import AnchorRecord, NullChain, ChainOp, get_chain_client
from firebreak.chain.config import ChainConfig
from firebreak.chain.tamper import rewrite_journal
from firebreak.scenario import build_simulation


class FakeChain:
    def __init__(self):
        self.ops: list[ChainOp] = []
        self.audits: dict[str, dict] = {}

    def submit(self, op):
        self.ops.append(op)
        if op.fn == "anchorAudit":
            _, head, n = op.args
            self.audits[op.company] = {"anchored_head": head.hex(),
                                       "anchored_entries": n}
        return AnchorRecord(len(self.ops), op.kind, op.company, op.hash,
                            status="confirmed")

    def read_audit_anchor(self, run_id, company):
        return self.audits.get(company)


def _compromised():
    sim = build_simulation()
    anchorer = Anchorer(FakeChain())
    anchorer.on_new_simulation(sim)
    sim.declare_compromise("fournisseur", datetime(2026, 1, 1))
    return sim, anchorer


def test_null_chain_est_inerte():
    chain = NullChain()
    rec = chain.submit(ChainOp("audit", "fabricant", "anchorAudit"))
    assert rec.status == "disabled"
    assert chain.status()["mode"] == "off"
    assert chain.anchors() == []
    assert chain.read_audit_anchor(b"\0" * 32, "fabricant") is None


def test_mode_off_donne_null_chain():
    assert isinstance(get_chain_client(ChainConfig(mode="off")), NullChain)


def test_tester_sans_mnemonique_est_connecte():
    chain = get_chain_client(ChainConfig(mode="tester"))
    assert chain.status()["connected"] is True


def test_tester_ancrage_de_bout_en_bout():
    chain = get_chain_client(ChainConfig(mode="tester"))
    sim = build_simulation()
    anchorer = Anchorer(chain)
    anchorer.on_new_simulation(sim)
    sim.declare_compromise("fournisseur", datetime(2026, 1, 1))
    anchorer.after_action(sim, "compromise")
    chain.flush(10)
    recs = chain.anchors()
    assert recs and all(r.status == "confirmed" for r in recs), \
        [(r.kind, r.status, r.error) for r in recs]


def test_l1_injoignable_ne_leve_pas():
    cfg = ChainConfig(mode="l1", rpc_url="http://127.0.0.1:1", chain_id=1,
                      mnemonic="test test test test test test test test test "
                               "test test junk")
    chain = get_chain_client(cfg)
    assert chain.status()["connected"] is False
    rec = chain.submit(ChainOp("audit", "fabricant", "anchorAudit"))
    assert rec.status == "failed"


def test_anchorer_ancre_alertes_acks_incidents_audits():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    kinds = [o.kind for o in anchorer.client.ops]
    assert {"alert", "ack", "incident", "audit"} <= set(kinds)
    assert kinds.index("alert") < kinds.index("ack")
    n_alerts = len(sim.federation.alerts)
    assert kinds.count("alert") == n_alerts


def test_anchorer_pas_de_doublon():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    n = len(anchorer.client.ops)
    anchorer.after_action(sim, "noop")
    assert len(anchorer.client.ops) == n


def test_verify_onchain_puis_reecriture_detectee():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    res = anchorer.verify_onchain(sim)
    assert all(v["matches"] for v in res.values() if v)

    rewrite_journal(sim, "fabricant", "alert_received")
    assert sim.ledgers["fabricant"].audit.verify() is None  # local : intègre
    res = anchorer.verify_onchain(sim)
    assert res["fabricant"]["matches"] is False


def test_rewrite_entree_absente():
    sim = build_simulation()
    with pytest.raises(ValueError):
        rewrite_journal(sim, "fabricant", "inexistant")
