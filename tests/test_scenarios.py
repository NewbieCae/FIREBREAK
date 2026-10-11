"""The four scenarios: quarantine sets reasoned out by hand."""

import pytest

from firebreak.scenario import COMPROMISED_SINCE, SCENARIOS, build_simulation

EXPECTED = {
    "mixed": {
        "f-asn-X", "f-cert-X", "f-inv-X", "f-asn-08",
        "m-asn-X", "m-cert-X", "m-inv-X", "m-asn-08",
        "m-gr-X", "m-lot-X", "m-pay-X", "m-ship-X",
        "d-ship-X", "d-gr-X", "d-out-X",
        "c-ship-X", "c-gr-X",
    },
    # RIB fraud: everything the supplier issues after 14:00 (including the
    # legitimate invoice F-3008), the received copies, the modified supplier record
    # and the payment depending on it. The callback (verified) protects payment F-3008.
    # No physical goods: nothing goes to the distributor.
    "rib": {
        "f-bank-X", "f-inv-X", "f-inv-08",
        "m-bank-X", "m-inv-X", "m-inv-08", "m-vendor-X", "m-pay-X",
    },
    # Fake certificate: the weighed goods receipt (verified) stops the taint from
    # the ASN, but the quality release depends on the certificate. LOT-901 contains
    # COIL-210, ASM-950 contains LOT-901: blocked down to the customer. LOT-902 continues.
    "cert": {
        "f-asn-X", "f-cert-X",
        "m-asn-X", "m-cert-X", "m-qc-X", "m-lot-901", "m-asm-950", "m-ship-950",
        "d-ship-950", "d-gr-950", "d-out-950",
        "c-ship-950", "c-gr-950",
    },
    # Fake ASN: unchecked goods receipt, phantom stock, lot started on it,
    # shipment, reservation, reshipment, site schedule. The legitimate ASN
    # BC-1008 is suspect (window) but its checked goods receipt stops everything.
    "asn": {
        "f-asn-X", "f-asn-08",
        "m-asn-X", "m-asn-08", "m-gr-X", "m-stock-X", "m-lot-X", "m-ship-X",
        "d-ship-X", "d-res-X", "d-out-X",
        "c-ship-X", "c-plan-X",
    },
}

GATES_BLOCKED = {
    "mixed": {"m-lot-X", "m-pay-X", "m-ship-X", "d-out-X"},
    "rib": {"m-pay-X"},
    "cert": {"m-lot-901", "m-asm-950", "m-ship-950", "d-out-950"},
    "asn": {"m-lot-X", "m-ship-X", "d-out-X"},
}

STOPPERS = {  # verified record with a tainted input
    "mixed": "m-gr-08",
    "rib": "m-call-08",
    "cert": "m-gr-X",
    "asn": "m-gr-08",
}


def _declared(name):
    sim = build_simulation(name)
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    return sim


AFTERNOON = {  # legitimate afternoon activity at the manufacturer (+ copies at d)
    *[f"m-lot-a{i}" for i in range(1, 7)],
    *[f"m-qc-a{i}" for i in range(1, 7)],
    *[f"m-pack-a{i}" for i in range(1, 7)],
    *[f"m-tr-a{i}" for i in range(1, 5)],
    *[f"m-ship-a{i}" for i in range(1, 5)],
    *[f"d-ship-a{i}" for i in range(1, 5)],
    *[f"d-gr-a{i}" for i in range(1, 5)],
    *[f"m-po-a{i}" for i in range(1, 5)],
    *[f"m-pay-a{i}" for i in range(1, 5)],
    "m-so-a1", "m-so-a2", "m-ic-a1", "m-mnt-a1", "m-qc-a7", "m-adj-a1",
}


def _records(sim):
    return {r.id: r for led in sim.ledgers.values() for r in led.records.values()}


def test_all_scenarios_covered():
    assert set(SCENARIOS) == set(EXPECTED) | {"lot", "recall"}


def test_default_is_mixed():
    assert build_simulation().scenario["id"] == "mixed"


def test_unknown_scenario():
    with pytest.raises(ValueError):
        build_simulation("nope")


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_exact_quarantined_set(name):
    records = _records(_declared(name))
    assert {rid for rid, r in records.items() if r.status == "quarantined"} == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_scenario_invariants(name):
    sim = build_simulation(name)
    assert {r.status for r in _records(sim).values()} == {"ok"}
    sim = _declared(name)
    records = _records(sim)
    total = len(records)
    quarantined = [r for r in records.values() if r.status == "quarantined"]
    assert 100 <= total <= 200
    assert 0 < len(quarantined) < 0.15 * total
    assert {r.id for r in quarantined if r.gate} == GATES_BLOCKED[name]
    stopper = records[STOPPERS[name]]
    assert stopper.verified and stopper.status == "ok"
    assert any(records[i].status == "quarantined" for i in stopper.inputs)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_afternoon_never_quarantined(name):
    """The ~40 legitimate afternoon records must NEVER enter quarantine:
    they depend on no supplier data after 2 pm."""
    sim = _declared(name)
    records = _records(sim)
    assert AFTERNOON <= set(records), name  # present in all 4 scenarios
    assert all(records[i].status == "ok" for i in AFTERNOON), name


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_scenario_deterministic(name):
    assert _declared(name).state() == _declared(name).state()


def test_rib_legit_payment_continues():
    records = _records(_declared("rib"))
    assert records["m-pay-08"].status == "ok"
    assert records["m-pay-X"].taint_path[0] in {"m-inv-X", "m-bank-X"}


def test_cert_unrelated_lot_continues_to_distributor():
    records = _records(_declared("cert"))
    for rid in ("m-lot-902", "m-ship-902", "d-ship-902", "d-gr-902"):
        assert records[rid].status == "ok"
    assert records["m-asm-950"].taint_path == [
        "m-cert-X", "m-qc-X", "m-lot-901", "m-asm-950"]


def test_asn_verified_delivery_production_continues():
    records = _records(_declared("asn"))
    assert records["m-lot-908"].status == "ok"
    assert records["c-plan-X"].status == "quarantined"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_withdraw_returns_to_zero(name):
    sim = _declared(name)
    sim.withdraw_compromise("fournisseur")
    assert sim.state()["counters"]["global"]["quarantined"] == 0


@pytest.mark.parametrize("name", ["lot", "recall"])
def test_quality_scenarios_have_incident_and_no_taint(name):
    sim = build_simulation(name)
    meta = sim.scenario
    assert meta["incident"]["type"] == name
    assert "compromise" in meta
    assert {r.status for r in _records(sim).values()} == {"ok"}


def test_quality_thread_coil_104():
    """COIL-104 feeds LOT-504 and LOT-A40; the supplier payment stays ok."""
    records = _records(build_simulation("lot"))
    assert records["m-gr-04"].payload["lot"] == "COIL-104"
    assert "m-gr-04" in records["m-lot-04"].inputs
    assert "m-gr-04" in records["m-lot-a4"].inputs
    assert records["m-pay-04"].status == "ok"