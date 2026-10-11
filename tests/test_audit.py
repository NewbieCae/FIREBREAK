from datetime import datetime

from firebreak.audit import GENESIS, AuditLog
from firebreak.scenario import COMPROMISED_SINCE, build_simulation

from test_scenario import EXPECTED_QUARANTINED, _q

TS = datetime(2026, 10, 10, 15, 0)


def _sim_declared():
    sim = build_simulation()
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    return sim


def _events(sim, company):
    return [e["event"] for e in sim.ledgers[company].audit.entries()]


# -- hash chain ---------------------------------------------------------------

def test_chain_links_entries():
    log = AuditLog("x")
    a = log.append(TS, "declaration", "humain", {"source": "y"})
    b = log.append(TS, "quarantine", "règle", {"record": "r"})
    assert a["prev_hash"] == GENESIS
    assert b["prev_hash"] == a["hash"]
    assert log.head == b["hash"]
    assert log.verify() is None


def test_verify_detects_first_tampered_index():
    sim = _sim_declared()
    sim.remediate("m-gr-X", "human_approval")
    audit = sim.ledgers["fabricant"].audit
    assert len(audit) > 5
    assert sim.audit_verify()["ok"] is True
    audit._entries[3]["details"]["rule"] = "tampered"
    res = sim.audit_verify()
    assert res["ok"] is False
    assert res["first_broken"] == {"company": "fabricant", "index": 3}
    by_co = {j["company"]: j for j in res["journals"]}
    assert by_co["fabricant"]["first_broken_index"] == 3
    assert by_co["fournisseur"]["ok"] is True


def test_verify_detects_deleted_entry():
    sim = _sim_declared()
    audit = sim.ledgers["fabricant"].audit
    del audit._entries[1]
    assert audit.verify() == 1


def test_entries_returned_are_copies():
    sim = _sim_declared()
    audit = sim.ledgers["fabricant"].audit
    audit.entries()[0]["actor"] = "intruder"
    assert audit.verify() is None


# -- log content -------------------------------------------------------------

def test_journal_records_full_response():
    sim = _sim_declared()
    sim.remediate("m-gr-X", "human_approval")
    m = sim.ledgers["fabricant"].audit.entries()
    events = [e["event"] for e in m]
    assert events[0] == "declaration"
    assert {"alert_received", "alert_sent", "quarantine", "remediation", "release"} <= set(events)

    q = next(e for e in m if e["event"] == "quarantine" and e["details"]["record"] == "m-pay-X")
    assert q["actor"] == "règle"
    assert q["details"]["rule"] == "dependance"
    assert q["details"]["taint_path"] == ["m-inv-X", "m-pay-X"]
    assert q["details"]["gate"] is True
    seed = next(e for e in m if e["event"] == "quarantine" and e["details"]["record"] == "m-inv-X")
    assert seed["details"]["rule"] == "source_compromise"

    rem = next(e for e in m if e["event"] == "remediation")
    assert rem["actor"] == "humain"
    assert rem["details"]["action"] == "human_approval"
    assert rem["ts"]
    lifted = {e["details"]["record"] for e in m if e["event"] == "release"}
    assert {"m-lot-X", "m-ship-X"} <= lifted

    d = sim.ledgers["distributeur"].audit.entries()
    received = [e for e in d if e["event"] == "alert_received"]
    assert [e["details"]["type"] for e in received] == ["taint", "release"]
    assert all(e["details"]["verified"] for e in received)
    seed_d = next(e for e in d if e["event"] == "quarantine" and e["details"]["record"] == "d-ship-X")
    assert seed_d["details"]["rule"] == "alerte_verifiee"


def test_journal_has_no_partner_business_data():
    sim = _sim_declared()
    blob = str(sim.ledgers["distributeur"].audit.entries())
    assert "m-ship-X" not in blob and "FR76" not in blob


# -- federated releases ------------------------------------------------------

def test_valid_release_frees_downstream_to_client():
    sim = _sim_declared()
    sim.remediate("m-gr-X", "human_approval")
    for rid in ("d-ship-X", "d-gr-X", "d-out-X", "c-ship-X", "c-gr-X"):
        assert sim.find_record(rid).status == "ok"
    releases = [a for a in sim.federation.alerts if a.type == "release"]
    assert {(a.sender, a.recipient) for a in releases} == {
        ("fabricant", "distributeur"), ("distributeur", "client")}
    assert all(a.verified for a in releases)
    # the payment to the fraudulent RIB stays blocked: only the remediated branch is released
    assert sim.find_record("m-pay-X").status == "quarantined"


def test_forged_release_rejected_downstream_stays_quarantined():
    sim = _sim_declared()
    fed = sim.federation
    real_emit = fed.emit_alerts

    def tampering_emit(ledgers, issued_at):
        alerts = real_emit(ledgers, issued_at)
        for a in alerts:
            if a.type == "release":
                a.signature = "ab" * 64
        return alerts

    fed.emit_alerts = tampering_emit
    sim.remediate("m-gr-X", "human_approval")
    assert sim.find_record("m-ship-X").status == "ok"
    for rid in ("d-ship-X", "d-out-X", "c-ship-X", "c-gr-X"):
        assert sim.find_record(rid).status == "quarantined"
    rejected = [e for e in sim.ledgers["distributeur"].audit.entries()
                if e["event"] == "alert_received" and not e["details"]["verified"]]
    assert len(rejected) == 1
    assert rejected[0]["details"]["type"] == "release"
    assert rejected[0]["details"]["outcome"].startswith("rejected")


# -- multiple declarations and withdrawal -------------------------------------

def test_withdraw_returns_to_initial_state():
    sim = _sim_declared()
    assert _q(sim) == EXPECTED_QUARANTINED
    sim.withdraw_compromise("fournisseur")
    assert _q(sim) == set()
    assert all(r.status == "ok" for led in sim.ledgers.values() for r in led.records.values())
    assert all(not led.declarations and not led.alert_tokens for led in sim.ledgers.values())
    assert "declaration_withdrawn" in _events(sim, "fournisseur")
    assert "declaration_withdrawn" in _events(sim, "fabricant")
    assert sim.audit_verify()["ok"] is True


def test_withdraw_after_remediation_leaves_no_quarantine():
    sim = _sim_declared()
    sim.remediate("m-gr-X", "human_approval")
    sim.withdraw_compromise("fournisseur")
    assert _q(sim) == set()


def test_withdraw_without_declaration_fails():
    sim = build_simulation()
    try:
        sim.withdraw_compromise("fournisseur")
    except ValueError as exc:
        assert "no active declaration" in str(exc)
    else:
        raise AssertionError("withdrawal accepted without a declaration")


def test_redeclare_keeps_earliest_since():
    later = COMPROMISED_SINCE.replace(hour=15)
    sim = build_simulation()
    sim.declare_compromise("fournisseur", later)
    assert "f-asn-X" not in _q(sim)  # 14:10, before 15:00
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    assert _q(sim) == EXPECTED_QUARANTINED
    sim.declare_compromise("fournisseur", later)  # later: ignored
    assert _q(sim) == EXPECTED_QUARANTINED
    decls = sim.ledgers["fabricant"].declarations
    assert len(decls) == 1 and decls[0].since == COMPROMISED_SINCE


def test_two_sources_withdraw_one_keeps_other():
    sim = _sim_declared()
    sim.declare_compromise("distributeur", COMPROMISED_SINCE)
    both = _q(sim)
    assert {"d-gr-X", "d-out-X"} <= both
    sim.withdraw_compromise("fournisseur")
    remaining = _q(sim)
    assert remaining and not any(r.startswith(("f-", "m-")) for r in remaining)
    # d-ship-X comes from the manufacturer, it is no longer suspect; what the
    # distributor produces after 14:00 still is
    assert "d-ship-X" not in remaining
    assert "d-out-X" in remaining
