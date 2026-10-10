from datetime import datetime

import pytest

from firebreak.engine import Ledger
from firebreak.federation import Federation
from firebreak.model import Record

SINCE = datetime(2026, 10, 10, 14, 0, 0)
NOW = datetime(2026, 10, 10, 15, 0, 0)


@pytest.fixture
def setup():
    fed = Federation(["a", "b"])
    la, lb = Ledger("a"), Ledger("b")
    # A envoie un record à B ; B garde une copie opaque (token)
    la.add(Record("a-out", "a", "a", "asn", NOW, "sortant"))
    token = fed.register_send("a", "a-out", "b", "b-recv")
    lb.add(Record("b-recv", "b", "a", "asn", NOW, "reçu", token=token))
    lb.add(Record("b-der", "b", "b", "goods_receipt", NOW, "dérivé",
                  inputs=["b-recv"]))
    return fed, la, lb


def taint_a_out(la):
    la.declare_compromised("a", SINCE)
    la.recompute()
    assert la.records["a-out"].status == "quarantined"


def test_valid_alert_seeds_received_records(setup):
    fed, la, lb = setup
    taint_a_out(la)
    alerts = fed.emit_alerts({"a": la, "b": lb}, NOW)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.sender == "a" and alert.recipient == "b"
    assert fed.deliver(alert, {"a": la, "b": lb}) is True
    assert alert.verified is True
    lb.recompute()
    assert lb.records["b-recv"].status == "quarantined"
    assert lb.records["b-der"].status == "quarantined"


def test_tampered_alert_rejected_and_seeds_nothing(setup):
    fed, la, lb = setup
    taint_a_out(la)
    alert = fed.emit_alerts({"a": la, "b": lb}, NOW)[0]
    alert.tokens = ["deadbeef" * 8]  # falsification des jetons
    assert fed.deliver(alert, {"a": la, "b": lb}) is False
    assert alert.verified is False
    lb.recompute()
    assert all(r.status == "ok" for r in lb.records.values())


def test_alert_contains_no_business_data(setup):
    fed, la, lb = setup
    taint_a_out(la)
    alert = fed.emit_alerts({"a": la, "b": lb}, NOW)[0]
    payload = alert.payload()
    assert set(payload) == {"from", "to", "tokens", "reason", "issued_at"}
    for tok in payload["tokens"]:
        assert "a-out" not in tok  # jamais l'id du record d'origine
