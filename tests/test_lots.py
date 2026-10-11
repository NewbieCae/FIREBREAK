"""Quality: suspect lot (without blacklisting the supplier), recall analysis,
signed upstream report, in both directions of the chain.

Base: the clean morning shared by all scenarios (coils COIL-101..107
received from the supplier, lots LOT-501..507, afternoon lots LOT-A10..A60).
Nobody is declared compromised.
"""

import pytest

from firebreak.engine import RULE_SUSPECT
from firebreak.scenario import build_simulation


def quarantined(sim) -> set[str]:
    return {r.id for led in sim.ledgers.values() for r in led.records.values()
            if r.status == "quarantined"}


# COIL-104 is received as m-gr-04; it is used for the morning lot LOT-504 (shipped
# all the way to the customer, who paid for it) and the afternoon lot LOT-A40
# (shipped to the distributor). The supplier invoice (m-inv-04 → m-pay-04) does not
# depend on it.
COIL_104_SCOPE = {
    "m-gr-04", "m-lot-04", "m-ship-04",
    "d-ship-04", "d-gr-04", "d-out-04",
    "c-ship-04", "c-gr-04", "c-pay-04",
    "m-lot-a4", "m-qc-a4", "m-pack-a4", "m-tr-a4", "m-ship-a4",
    "d-ship-a4", "d-gr-a4",
}


@pytest.fixture
def sim():
    s = build_simulation("mixed")
    assert quarantined(s) == set()
    return s


def test_lot_suspect_isolates_only_that_lot(sim):
    ids = sim.declare_lot_suspect("fabricant", "COIL-104", "casting defect")
    assert ids == ["m-gr-04"]
    assert quarantined(sim) == COIL_104_SCOPE
    assert sim.ledgers["fabricant"].quarantine_rule("m-gr-04") == RULE_SUSPECT


def test_supplier_is_not_blacklisted(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "casting defect")
    # Neither the supplier, nor its other coils, nor its invoice are blocked.
    assert not any(r.status == "quarantined" for r in sim.ledgers["fournisseur"].records.values())
    assert sim.find_record("m-pay-04").status == "ok"
    for other in ("m-gr-01", "m-gr-03", "m-gr-05", "m-lot-03", "m-lot-a3"):
        assert sim.find_record(other).status == "ok"
    assert sim.ledgers["fabricant"].declarations == []


def test_withdraw_lot_suspect_releases_in_cascade(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "casting defect")
    assert sim.withdraw_lot_suspect("fabricant", "COIL-104") == ["m-gr-04"]
    assert quarantined(sim) == set()
    assert any(a.type == "release" for a in sim.federation.alerts)
    with pytest.raises(ValueError):
        sim.withdraw_lot_suspect("fabricant", "COIL-104")


def test_suspect_overrides_previous_verification(sim):
    rec = sim.find_record("m-gr-04")
    rec.verified = True  # receiving inspection passed...
    sim.declare_lot_suspect("fabricant", "COIL-104", "defect found afterwards")
    assert rec.status == "quarantined"  # ... but the defect found later takes precedence


def test_unknown_lot_or_company(sim):
    with pytest.raises(KeyError):
        sim.declare_lot_suspect("fabricant", "COIL-000", "x")
    with pytest.raises(KeyError):
        sim.declare_lot_suspect("unknown", "COIL-104", "x")


def test_audit_and_timeline_record_the_decision(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "casting defect")
    events = [e["event"] for e in sim.ledgers["fabricant"].audit.entries()]
    assert "lot_suspect" in events
    types = [s["type"] for s in sim.timeline]
    assert types[0] == "lot_suspect" and "seed" in types and "alert_sent" in types
    assert "supplier is not blamed" in sim.timeline[0]["text"]
    assert sim.audit_verify()["ok"]


def test_recall_analysis_lists_causes_with_scope(sim):
    analysis = sim.recall_analysis("fabricant", "LOT-503")
    assert analysis["target"]["records"] == ["m-lot-03"]
    by_record = {c["record"]: c for c in analysis["candidates"]}
    assert set(by_record) == {"m-asn-03", "m-cert-03", "m-gr-03"}
    coil = by_record["m-gr-03"]
    assert coil["lot"] == "COIL-103" and coil["received"] is False
    # COIL-103 was also used for the afternoon lot LOT-A30: the scope shows it.
    assert coil["impact_partners"] == ["distributeur"] and coil["impact_gates"] == 4
    assert by_record["m-cert-03"]["received"] and by_record["m-cert-03"]["origin"] == "fournisseur"
    assert quarantined(sim) == set()  # read-only


def test_recall_from_finished_product_up_the_chain(sim):
    """Breakage found on site, on a lot delivered hours ago.
    Each link reports to the previous one, decides case by case, and only
    the faulty lot is isolated, including its "siblings" already shipped."""
    # 1. The customer reports to the distributor, from its goods receipt.
    (r1,) = sim.report_upstream("client", "c-gr-03", "breakage on site, lot LOT-503")
    assert (r1["from"], r1["to"], r1["verified"]) == ("client", "distributeur", True)
    assert r1["records"] == ["d-out-03"]  # resolved by the distributor alone
    assert quarantined(sim) == set()  # a report blocks nothing on its own

    # 2. The distributor confirms: its reshipment is suspect, the customer is alerted.
    sim.decide_report("distributeur", r1["id"], "confirm")
    assert {"d-out-03", "c-ship-03", "c-gr-03", "c-pay-03"} <= quarantined(sim)

    # 3. It escalates to the manufacturer, which finds its shipment.
    (r2,) = sim.report_upstream("distributeur", "d-out-03", "breakage on site")
    assert r2["to"] == "fabricant" and r2["records"] == ["m-ship-03"]

    # 4. Quality analysis at the manufacturer: coil COIL-103 is at fault.
    causes = {c["record"] for c in sim.recall_analysis("fabricant", "m-ship-03")["candidates"]}
    assert "m-gr-03" in causes
    sim.declare_lot_suspect("fabricant", "COIL-103", "analysis: material defect")
    sibling = {"m-lot-a3", "m-qc-a3", "m-pack-a3", "m-tr-a3", "m-ship-a3", "d-ship-a3", "d-gr-a3"}
    assert sibling <= quarantined(sim)  # LOT-A30, made with the same coil
    assert sim.find_record("m-lot-04").status == "ok"  # the other lots continue

    # 5. Report to the supplier, which confirms: its documents are questioned.
    (r3,) = sim.report_upstream("fabricant", "COIL-103", "non-compliant coil")
    assert r3["to"] == "fournisseur" and r3["records"] == ["f-asn-03", "f-cert-03"]
    sim.decide_report("fournisseur", r3["id"], "confirm")
    assert {"f-asn-03", "f-cert-03", "m-asn-03", "m-cert-03"} <= quarantined(sim)
    # The supplier is still not declared compromised: its other sends go through.
    assert sim.find_record("f-asn-04").status == "ok"
    assert sim.find_record("m-pay-03").status == "ok"
    assert sim.audit_verify()["ok"]


def test_report_rejected_blocks_nothing(sim):
    (r,) = sim.report_upstream("client", "c-gr-03", "breakage")
    view = sim.decide_report("distributeur", r["id"], "reject")
    assert view["status"] == "rejected" and quarantined(sim) == set()
    with pytest.raises(ValueError):
        sim.decide_report("distributeur", r["id"], "confirm")  # already handled


def test_only_recipient_can_decide_and_forged_report_cannot_be_confirmed(sim):
    (r,) = sim.report_upstream("client", "c-gr-03", "breakage")
    with pytest.raises(KeyError):
        sim.decide_report("fabricant", r["id"], "confirm")
    report = sim.federation.reports[-1]
    report.reason = "reason modified after signing"
    assert sim.federation.receive_report(report) == []  # invalid signature
    with pytest.raises(ValueError):
        sim.decide_report("distributeur", r["id"], "confirm")


def test_report_carries_only_tokens(sim):
    sim.report_upstream("client", "c-gr-03", "breakage")
    payload = sim.federation.reports[-1].payload()
    assert set(payload) == {"type", "id", "from", "to", "tokens", "reason", "issued_at"}
    assert all(len(t) == 64 for t in payload["tokens"])


def test_internal_only_lot_cannot_be_reported(sim):
    # A manufacturer lot that depends on nothing received (LOT-A30 depends on COIL-103,
    # itself from received data: pick a purely internal record).
    with pytest.raises(ValueError):
        sim.report_upstream("fabricant", "m-mnt-a1", "x")


def test_declare_by_record_id_too(sim):
    assert sim.declare_lot_suspect("fabricant", "m-gr-04", "defect") == ["m-gr-04"]
    assert quarantined(sim) == COIL_104_SCOPE
    assert sim.withdraw_lot_suspect("fabricant", "m-gr-04") == ["m-gr-04"]
    assert quarantined(sim) == set()
