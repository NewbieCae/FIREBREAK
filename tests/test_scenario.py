import json

from firebreak.scenario import COMPROMISED_SINCE, build_simulation

EXPECTED_QUARANTINED = {
    # supplier: the 3 malicious ones + the legitimate post-14:00 ASN (suspect window)
    "f-asn-X", "f-cert-X", "f-inv-X", "f-asn-08",
    # manufacturer: received copies + X's production/payment/shipment chain
    "m-asn-X", "m-cert-X", "m-inv-X", "m-asn-08",
    "m-gr-X", "m-lot-X", "m-pay-X", "m-ship-X",
    # distributor: receipt + reshipment of the tainted lot
    "d-ship-X", "d-gr-X", "d-out-X",
    # customer: delivery + receipt of the tainted lot
    "c-ship-X", "c-gr-X",
}


def _sim_declared():
    sim = build_simulation()
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    return sim


def _q(sim):
    return {
        r.id
        for led in sim.ledgers.values()
        for r in led.records.values()
        if r.status == "quarantined"
    }


def test_nothing_tainted_before_declaration():
    sim = build_simulation()
    assert _q(sim) == set()
    assert sim.federation.alerts == []


def test_exact_quarantined_set():
    sim = _sim_declared()
    assert _q(sim) == EXPECTED_QUARANTINED


def test_rib_payment_gate_blocked():
    sim = _sim_declared()
    r = sim.ledgers["fabricant"].records["m-pay-X"]
    assert r.status == "quarantined" and r.gate
    assert r.payload["rib"].endswith("666")


def test_propagation_reaches_distributeur_and_client():
    sim = _sim_declared()
    q = _q(sim)
    assert {"d-ship-X", "d-gr-X", "d-out-X"} <= q
    assert {"c-ship-X", "c-gr-X"} <= q
    # signed alerts at every hop
    hops = {(a.sender, a.recipient) for a in sim.federation.alerts}
    assert ("fournisseur", "fabricant") in hops
    assert ("fabricant", "distributeur") in hops
    assert ("distributeur", "client") in hops
    assert all(a.verified for a in sim.federation.alerts)


def test_verified_record_stops_propagation():
    sim = _sim_declared()
    # m-asn-08 is tainted (suspect window) but the physically
    # verified goods receipt stops propagation
    assert sim.ledgers["fabricant"].records["m-asn-08"].status == "quarantined"
    assert sim.ledgers["fabricant"].records["m-gr-08"].status == "ok"
    assert sim.ledgers["fabricant"].records["m-gr-08"].verified


def test_quarantined_fraction_small():
    sim = _sim_declared()
    counters = sim.state()["counters"]["global"]
    assert counters["quarantined"] / counters["total"] < 0.15
    assert counters["quarantined"] >= 1


def test_remediate_frees_descendants():
    sim = _sim_declared()
    sim.remediate("m-gr-X", "human_approval")
    led = sim.ledgers["fabricant"]
    assert led.records["m-gr-X"].status == "released"
    # lot / shipment only depended on m-gr-X: freed
    assert led.records["m-lot-X"].status == "ok"
    assert led.records["m-ship-X"].status == "ok"
    # signed release propagated all the way to the customer
    for rid in ("d-ship-X", "d-gr-X", "d-out-X"):
        assert sim.ledgers["distributeur"].records[rid].status == "ok"
    for rid in ("c-ship-X", "c-gr-X"):
        assert sim.ledgers["client"].records[rid].status == "ok"
    # the payment to the fraudulent RIB stays blocked (seed m-inv-X)
    assert led.records["m-pay-X"].status == "quarantined"


def test_recompute_idempotent_on_scenario():
    sim = _sim_declared()
    before = sim.state()
    sim.run()
    assert sim.state() == before


def test_alerts_carry_only_opaque_tokens():
    sim = _sim_declared()
    labels = {r.label for led in sim.ledgers.values() for r in led.records.values()}
    for alert in sim.federation.alerts:
        payload = alert.payload()
        assert set(payload) == {"type", "from", "to", "tokens", "reason", "issued_at"}
        for tok in payload["tokens"]:
            assert len(tok) == 64 and int(tok, 16) >= 0
        # Tokens are random hex already validated above: remove them before
        # looking for a leak, otherwise "5210" may appear by chance in a token
        # and fail the test (flaky test reported by Mika).
        blob = json.dumps({k: v for k, v in payload.items() if k != "tokens"})
        assert not any(label in blob for label in labels)
        assert "5210" not in blob and "FR76" not in blob


def test_ledgers_only_know_partner_data_through_tokens():
    sim = _sim_declared()
    for cid, led in sim.ledgers.items():
        for r in led.records.values():
            assert r.company == cid
            assert all(i in led.records for i in r.inputs)
            if r.origin != cid:
                assert r.token is not None
