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
    led.add(_rec("seed-old", ts=datetime(2026, 10, 10, 13, 0)))         # before since
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
    assert "w" not in q(ledger)  # descendant of a verified record: spared


def test_taint_path(ledger):
    assert ledger.records["seed-new"].taint_path == ["seed-new"]
    assert ledger.records["a"].taint_path == ["seed-new", "a"]
    assert ledger.records["b"].taint_path == ["seed-new", "a", "b"]


def test_released_stops_and_frees_descendants(ledger):
    ledger.records["a"].status = "released"
    ledger.recompute()
    assert ledger.records["a"].status == "released"
    assert q(ledger) == {"seed-new"}  # b freed: it only depended on a


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


def test_any_tainted_input_taints_even_if_other_input_verified():
    led = Ledger("test")
    led.add(_rec("bad"))
    led.add(_rec("good", origin="test", verified=True))
    led.add(_rec("mix", origin="test", inputs=["good", "bad"]))
    led.declare_compromised("evil", SINCE)
    led.recompute()
    assert q(led) == {"bad", "mix"}
    assert led.records["mix"].taint_path == ["bad", "mix"]


def test_verified_seed_is_never_tainted():
    led = Ledger("test")
    led.add(_rec("seed", verified=True))
    led.add(_rec("child", origin="test", inputs=["seed"]))
    led.declare_compromised("evil", SINCE)
    led.recompute()
    assert q(led) == set()


def test_since_boundary_is_inclusive():
    led = Ledger("test")
    led.add(_rec("at", ts=SINCE))
    led.declare_compromised("evil", SINCE)
    led.recompute()
    assert q(led) == {"at"}


def test_taint_path_is_shortest_and_deterministic():
    def build():
        led = Ledger("test")
        led.add(_rec("s"))
        led.add(_rec("a", origin="test", inputs=["s"]))
        led.add(_rec("b", origin="test", inputs=["a"]))
        led.add(_rec("z", origin="test", inputs=["b", "s"]))
        led.declare_compromised("evil", SINCE)
        led.recompute()
        return led
    led = build()
    assert led.records["z"].taint_path == ["s", "z"]
    assert build().records["z"].taint_path == led.records["z"].taint_path


def test_add_rejects_foreign_or_duplicate_record():
    led = Ledger("test")
    led.add(_rec("x"))
    with pytest.raises(ValueError):
        led.add(_rec("x"))
    foreign = _rec("y")
    foreign.company = "other"
    with pytest.raises(ValueError):
        led.add(foreign)
