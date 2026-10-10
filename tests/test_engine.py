from datetime import datetime

import pytest

from firebreak.engine import Ledger
from firebreak.model import Record

SINCE = datetime(2026, 10, 10, 14, 0, 0)


def _rec(rid, origin="evil", ts=None, inputs=(), verified=False, gate=False,
         token=None):
    return Record(
        id=rid, company="test", origin=origin, kind="k",
        ts=ts or datetime(2026, 10, 10, 15, 0, 0),
        label=rid, inputs=list(inputs), verified=verified, gate=gate,
        token=token,
    )


@pytest.fixture
def ledger():
    led = Ledger("test")
    led.add(_rec("seed-new", ts=datetime(2026, 10, 10, 15, 0)))          # seed
    led.add(_rec("seed-old", ts=datetime(2026, 10, 10, 13, 0)))         # avant since
    led.add(_rec("other", origin="honest"))
    led.add(_rec("a", origin="test", inputs=["seed-new"]))
    led.add(_rec("b", origin="test", inputs=["a"]))
    led.add(_rec("v", origin="test", inputs=["seed-new"], verified=True))
    led.add(_rec("w", origin="test", inputs=["v"]))
    led.declare_compromised("evil", SINCE)
    led.recompute()
    return led


def q(led):
    return {r.id for r in led.records.values() if r.status == "quarantined"}


def test_seed_selection_by_origin_and_since(ledger):
    assert "seed-new" in q(ledger)
    assert "seed-old" not in q(ledger)
    assert "other" not in q(ledger)


def test_transitive_propagation(ledger):
    assert q(ledger) == {"seed-new", "a", "b"}


def test_verified_stops_propagation(ledger):
    assert "v" not in q(ledger)
    assert "w" not in q(ledger)  # descendant d'un record vérifié : épargné


def test_taint_path(ledger):
    assert ledger.records["seed-new"].taint_path == ["seed-new"]
    assert ledger.records["a"].taint_path == ["seed-new", "a"]
    assert ledger.records["b"].taint_path == ["seed-new", "a", "b"]


def test_released_stops_and_frees_descendants(ledger):
    ledger.records["a"].status = "released"
    ledger.recompute()
    assert ledger.records["a"].status == "released"
    assert q(ledger) == {"seed-new"}  # b libéré : ne dépendait que de a


def test_idempotent_recompute(ledger):
    before = {rid: (r.status, r.taint_path) for rid, r in ledger.records.items()}
    ledger.recompute()
    after = {rid: (r.status, r.taint_path) for rid, r in ledger.records.items()}
    assert before == after


def test_alert_token_seeds(ledger):
    led = Ledger("test")
    led.add(_rec("recv", origin="partner", token="tok-1"))
    led.add(_rec("derived", origin="test", inputs=["recv"]))
    led.register_alert_tokens(["tok-1"])
    led.recompute()
    assert q(led) == {"recv", "derived"}


def test_counters(ledger):
    c = ledger.counters()
    assert c["total"] == 7
    assert c["quarantined"] == 3
    assert c["ok"] == 4
    assert c["released"] == 0
    assert c["gates_blocked"] == 0
