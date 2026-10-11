"""Client, anchoring and rewriting: no network, no compiled contract."""

import time
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


def test_null_chain_is_inert():
    chain = NullChain()
    rec = chain.submit(ChainOp("audit", "fabricant", "anchorAudit"))
    assert rec.status == "disabled"
    assert chain.status()["mode"] == "off"
    assert chain.anchors() == []
    assert chain.read_audit_anchor(b"\0" * 32, "fabricant") is None


def test_off_mode_gives_null_chain():
    assert isinstance(get_chain_client(ChainConfig(mode="off")), NullChain)


def test_tester_without_mnemonic_is_connected():
    chain = get_chain_client(ChainConfig(mode="tester"))
    assert chain.status()["connected"] is True


def test_tester_anchoring_end_to_end():
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


def test_tester_replaying_the_demo_does_not_fail():
    chain = get_chain_client(ChainConfig(mode="tester"))
    anchorer = Anchorer(chain)
    for _ in range(2):
        sim = build_simulation()
        anchorer.on_new_simulation(sim)
        sim.declare_compromise("fournisseur", datetime(2026, 1, 1))
        anchorer.after_action(sim, "compromise")
        chain.flush(10)
    recs = chain.anchors()
    assert recs and all(r.status == "confirmed" for r in recs), \
        [(r.kind, r.status) for r in recs if r.status != "confirmed"]


def _web3_chain_with_fake_contract(reads, monkeypatch):
    import firebreak.chain.client as client_mod
    monkeypatch.setattr(client_mod, "READ_RETRY_DELAY", 0)

    class Call:
        def __init__(self, value):
            self.value = value

        def call(self):
            if isinstance(self.value, Exception):
                raise self.value
            return self.value

    class Fns:
        def latestAudit(self, run_id, cid):
            return Call(reads.pop(0) if len(reads) > 1 else reads[0])

    class Contract:
        functions = Fns()

    class Eth:
        chain_id = 1

    class W3:
        eth = Eth()

    chain = client_mod.Web3Chain(ChainConfig(mode="tester"), W3(), Contract(), {})
    return chain, client_mod


def test_onchain_read_retries_then_succeeds(monkeypatch):
    head = bytes.fromhex("ab" * 32)
    chain, mod = _web3_chain_with_fake_contract(
        [(b"", 0, 0), RuntimeError("429"), (head, 5, 1)], monkeypatch)
    chain._records.append(AnchorRecord(1, "audit", "fabricant", "0x" + "ab" * 32,
                                       status="confirmed", block=7))
    got = chain.read_audit_anchor(b"\0" * 32, "fabricant")
    assert got["anchored_entries"] == 5 and got["anchored_head"] == head.hex()


def test_unreadable_onchain_read_is_not_unanchored(monkeypatch):
    chain, _ = _web3_chain_with_fake_contract([(b"", 0, 0)], monkeypatch)
    assert chain.read_audit_anchor(b"\0" * 32, "fabricant") is None
    chain._records.append(AnchorRecord(1, "audit", "fabricant", "0x" + "ab" * 32,
                                       status="confirmed", block=7))
    assert chain.read_audit_anchor(b"\0" * 32, "fabricant") == {"unreadable": True}


def test_unreadable_verify_onchain_does_not_claim_tampering():
    class Unreadable(FakeChain):
        def read_audit_anchor(self, run_id, company):
            return {"unreadable": True}

    sim = build_simulation()
    anchorer = Anchorer(Unreadable())
    anchorer.on_new_simulation(sim)
    res = anchorer.verify_onchain(sim)
    assert all(v == {"unreadable": True} for v in res.values())


def _send_fakes(monkeypatch, fail_sends=0, fail_receipts=0, alert_anchored_at=1):
    import firebreak.chain.client as mod
    monkeypatch.setattr(mod, "RETRY_BACKOFF", 0)
    state = {"sends": 0, "receipts": 0}

    class Tx:
        def build_transaction(self, params):
            return params

    class Fns:
        def anchorAlert(self, *a):
            return Tx()

        def acknowledgeAlert(self, *a):
            return Tx()

        def alerts(self, h):
            class C:
                def call(_):
                    return (b"", b"", 0, alert_anchored_at, 0)
            return C()

    class Contract:
        functions = Fns()

    class Signed:
        raw_transaction = b"raw"

    class Acct:
        address = "0xabc"

        def sign_transaction(self, tx):
            return Signed()

    class Eth:
        chain_id = 1
        gas_price = 1

        def get_transaction_count(self, *a):
            return 0

        def send_raw_transaction(self, raw):
            state["sends"] += 1
            if state["sends"] <= fail_sends:
                raise ConnectionError("network")
            return bytes.fromhex("11" * 32)

        def wait_for_transaction_receipt(self, h, timeout, poll_latency):
            state["receipts"] += 1
            if state["receipts"] <= fail_receipts:
                raise TimeoutError("receipt")
            return {"status": 1, "blockNumber": 9}

    class W3:
        eth = Eth()

    chain = mod.Web3Chain(ChainConfig(mode="tester"), W3(), Contract(),
                          {"fabricant": Acct()})
    return chain, state


def _op(fn):
    args = (b"\0" * 32, b"\1" * 32, b"\2" * 32, 0) if fn == "anchorAlert" else (b"\1" * 32,)
    return ChainOp("alert", "fabricant", fn, args, "0x" + "01" * 32)


def test_send_retries_with_backoff_then_confirms(monkeypatch):
    chain, state = _send_fakes(monkeypatch, fail_sends=2)
    rec = chain.submit(_op("anchorAlert"))
    chain.flush(5)
    assert rec.status == "confirmed" and state["sends"] == 3


def test_missing_receipt_does_not_resend_transaction(monkeypatch):
    chain, state = _send_fakes(monkeypatch, fail_receipts=2)
    rec = chain.submit(_op("anchorAlert"))
    chain.flush(5)
    assert rec.status == "confirmed"
    assert state["sends"] == 1 and state["receipts"] == 3


def test_ack_without_anchored_alert_fails_clearly(monkeypatch):
    import firebreak.chain.client as mod
    monkeypatch.setattr(mod, "ACK_WAIT", 0.1)
    monkeypatch.setattr(mod, "ACK_POLL", 0.02)
    chain, state = _send_fakes(monkeypatch, alert_anchored_at=0)
    rec = chain.submit(_op("acknowledgeAlert"))
    chain.flush(5)
    assert rec.status == "failed" and "alert not anchored" in rec.error


def _parallel_chain(monkeypatch, companies, delay=0.1):
    import firebreak.chain.client as mod
    monkeypatch.setattr(mod, "RETRY_BACKOFF", 0)
    monkeypatch.setattr(mod, "ACK_POLL", 0.02)
    anchored = set()

    class Tx:
        def __init__(self, fn, args):
            self.fn, self.args = fn, args

        def build_transaction(self, params):
            return {**params, "fn": self.fn, "args": self.args}

    class Fns:
        def __getattr__(self, fn):
            return lambda *a: Tx(fn, a)

        def alerts(self, h):
            class C:
                def call(_):
                    return (b"", b"", 0, 1 if h in anchored else 0, 0)
            return C()

    class Contract:
        functions = Fns()

    class Acct:
        address = "0xabc"

        def sign_transaction(self, tx):
            class S:
                raw_transaction = tx
            return S()

    class Eth:
        chain_id = 1
        gas_price = 1

        def get_transaction_count(self, *a):
            return 0

        def send_raw_transaction(self, raw):
            time.sleep(delay)
            if raw["fn"] == "anchorAlert":
                anchored.add(raw["args"][0])
            return bytes.fromhex("11" * 32)

        def wait_for_transaction_receipt(self, h, timeout, poll_latency):
            return {"status": 1, "blockNumber": 9}

    class W3:
        eth = Eth()

    return mod.Web3Chain(ChainConfig(mode="tester"), W3(), Contract(),
                         {c: Acct() for c in companies}, max_parallel=4)


def _timed(chain, companies, per_company=3):
    start = time.monotonic()
    recs = [chain.submit(ChainOp("audit", c, "anchorAudit", (b"\0" * 32,), "0x01"))
            for _ in range(per_company) for c in companies]
    chain.flush(10)
    assert all(r.status == "confirmed" for r in recs)
    return time.monotonic() - start


def test_parallel_sends_per_account(monkeypatch):
    one = _timed(_parallel_chain(monkeypatch, ["a"]), ["a"])
    four = _timed(_parallel_chain(monkeypatch, list("abcd")), list("abcd"))
    assert four < 2 * one


def test_ack_submitted_before_its_alert_finishes_after_it(monkeypatch):
    chain = _parallel_chain(monkeypatch, ["a", "b"], delay=0.2)
    h = b"\7" * 32
    ack = chain.submit(ChainOp("ack", "b", "acknowledgeAlert", (h,), "0x01"))
    alert = chain.submit(ChainOp("alert", "a", "anchorAlert", (h,), "0x01"))
    chain.flush(10)
    assert alert.status == "confirmed" and ack.status == "confirmed"


def _rpc_chain(monkeypatch, send_errors=(), receipts=None):
    import firebreak.chain.client as mod
    monkeypatch.setattr(mod, "RETRY_BACKOFF", 0)
    monkeypatch.setattr(mod, "ACK_RETRY_DELAY", 0)
    calls = {"nonce": 0, "gas_price": 0, "send": 0, "receipt": 0, "nonces": []}
    errors = list(send_errors)
    statuses = list(receipts or [])

    class Tx:
        def __init__(self, fn):
            self.fn = fn

        def build_transaction(self, params):
            assert params["gas"] > 0
            calls["nonces"].append(params["nonce"])
            return params

    class Fns:
        def __getattr__(self, fn):
            return lambda *a: Tx(fn)

        def alerts(self, h):
            class C:
                def call(_):
                    return (b"", b"", 0, 1, 0)
            return C()

    class Contract:
        functions = Fns()

    class Acct:
        address = "0xabc"

        def sign_transaction(self, tx):
            class S:
                raw_transaction = b"raw"
            return S()

    class Eth:
        chain_id = 1

        @property
        def gas_price(self):
            calls["gas_price"] += 1
            return 1

        def get_transaction_count(self, *a):
            calls["nonce"] += 1
            return 5

        def send_raw_transaction(self, raw):
            calls["send"] += 1
            if errors:
                raise errors.pop(0)
            return bytes.fromhex("11" * 32)

        def wait_for_transaction_receipt(self, h, timeout, poll_latency):
            calls["receipt"] += 1
            ok = statuses.pop(0) if statuses else 1
            return {"status": ok, "blockNumber": 9}

    class W3:
        eth = Eth()

    chain = mod.Web3Chain(ChainConfig(mode="tester"), W3(), Contract(),
                          {"a": Acct()})
    return chain, calls


def test_local_nonce_fixed_gas_and_cached_price(monkeypatch):
    chain, calls = _rpc_chain(monkeypatch)
    recs = [chain.submit(ChainOp("audit", "a", "anchorAudit", (b"\0" * 32,), "0x01"))
            for _ in range(4)]
    chain.flush(5)
    assert all(r.status == "confirmed" for r in recs)
    assert calls["nonces"] == [5, 6, 7, 8]
    assert calls["nonce"] == 1 and calls["gas_price"] == 1
    assert calls["send"] == 4 and calls["receipt"] == 4


def test_nonce_too_low_resyncs(monkeypatch):
    chain, calls = _rpc_chain(monkeypatch, send_errors=[ValueError("nonce too low")])
    rec = chain.submit(ChainOp("audit", "a", "anchorAudit", (b"\0" * 32,), "0x01"))
    chain.flush(5)
    assert rec.status == "confirmed"
    assert calls["nonce"] == 2 and calls["send"] == 2


def test_ack_reverts_once_then_succeeds(monkeypatch):
    chain, calls = _rpc_chain(monkeypatch, receipts=[0, 1])
    rec = chain.submit(ChainOp("ack", "a", "acknowledgeAlert", (b"\1" * 32,), "0x01"))
    chain.flush(5)
    assert rec.status == "confirmed" and calls["send"] == 2
    assert calls["nonces"] == [5, 6]



def test_unreachable_l1_does_not_raise():
    cfg = ChainConfig(mode="l1", rpc_url="http://127.0.0.1:1", chain_id=1,
                      mnemonic="test test test test test test test test test "
                               "test test junk")
    chain = get_chain_client(cfg)
    assert chain.status()["connected"] is False
    rec = chain.submit(ChainOp("audit", "fabricant", "anchorAudit"))
    assert rec.status == "failed"


def test_anchorer_anchors_alerts_acks_incidents_audits():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    kinds = [o.kind for o in anchorer.client.ops]
    assert {"alert", "ack", "incident", "audit"} <= set(kinds)
    assert kinds.index("alert") < kinds.index("ack")
    n_alerts = len(sim.federation.alerts)
    assert kinds.count("alert") == n_alerts


def test_anchorer_no_duplicate():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    n = len(anchorer.client.ops)
    anchorer.after_action(sim, "noop")
    assert len(anchorer.client.ops) == n


def test_verify_onchain_then_rewrite_detected():
    sim, anchorer = _compromised()
    anchorer.after_action(sim, "compromise")
    res = anchorer.verify_onchain(sim)
    assert all(v["matches"] for v in res.values() if v)

    rewrite_journal(sim, "fabricant", "alert_received")
    assert sim.ledgers["fabricant"].audit.verify() is None  # local: intact
    res = anchorer.verify_onchain(sim)
    assert res["fabricant"]["matches"] is False


def test_rewrite_missing_entry():
    sim = build_simulation()
    with pytest.raises(ValueError):
        rewrite_journal(sim, "fabricant", "nonexistent")
