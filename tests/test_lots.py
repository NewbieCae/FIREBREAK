"""Qualité : lot suspect (sans blacklister le fournisseur), analyse de rappel,
signalement signé vers l'amont, dans les deux sens de la chaîne.

Base : la matinée propre commune à tous les scénarios (bobines COIL-101..107
reçues du fournisseur, lots LOT-501..507, lots d'après-midi LOT-A10..A60).
Personne n'est déclaré compromis.
"""

import pytest

from firebreak.engine import RULE_SUSPECT
from firebreak.scenario import build_simulation


def quarantined(sim) -> set[str]:
    return {r.id for led in sim.ledgers.values() for r in led.records.values()
            if r.status == "quarantined"}


# COIL-104 est reçue en m-gr-04 ; elle sert au lot du matin LOT-504 (expédié
# jusqu'au client, qui l'a payé) et au lot d'après-midi LOT-A40 (expédié au
# distributeur). La facture du fournisseur (m-inv-04 → m-pay-04) n'en dépend pas.
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
    ids = sim.declare_lot_suspect("fabricant", "COIL-104", "défaut de coulée")
    assert ids == ["m-gr-04"]
    assert quarantined(sim) == COIL_104_SCOPE
    assert sim.ledgers["fabricant"].quarantine_rule("m-gr-04") == RULE_SUSPECT


def test_supplier_is_not_blacklisted(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "défaut de coulée")
    # Ni le fournisseur, ni ses autres bobines, ni sa facture ne sont bloqués.
    assert not any(r.status == "quarantined" for r in sim.ledgers["fournisseur"].records.values())
    assert sim.find_record("m-pay-04").status == "ok"
    for other in ("m-gr-01", "m-gr-03", "m-gr-05", "m-lot-03", "m-lot-a3"):
        assert sim.find_record(other).status == "ok"
    assert sim.ledgers["fabricant"].declarations == []


def test_withdraw_lot_suspect_releases_in_cascade(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "défaut de coulée")
    assert sim.withdraw_lot_suspect("fabricant", "COIL-104") == ["m-gr-04"]
    assert quarantined(sim) == set()
    assert any(a.type == "release" for a in sim.federation.alerts)
    with pytest.raises(ValueError):
        sim.withdraw_lot_suspect("fabricant", "COIL-104")


def test_suspect_overrides_previous_verification(sim):
    rec = sim.find_record("m-gr-04")
    rec.verified = True  # contrôle réception passé…
    sim.declare_lot_suspect("fabricant", "COIL-104", "défaut découvert après coup")
    assert rec.status == "quarantined"  # … mais le défaut découvert ensuite prime


def test_unknown_lot_or_company(sim):
    with pytest.raises(KeyError):
        sim.declare_lot_suspect("fabricant", "COIL-000", "x")
    with pytest.raises(KeyError):
        sim.declare_lot_suspect("inconnue", "COIL-104", "x")


def test_audit_and_timeline_record_the_decision(sim):
    sim.declare_lot_suspect("fabricant", "COIL-104", "défaut de coulée")
    events = [e["event"] for e in sim.ledgers["fabricant"].audit.entries()]
    assert "lot_suspect" in events
    types = [s["type"] for s in sim.timeline]
    assert types[0] == "lot_suspect" and "seed" in types and "alert_sent" in types
    assert "fournisseur n'est pas mis en cause" in sim.timeline[0]["text"]
    assert sim.audit_verify()["ok"]


def test_recall_analysis_lists_causes_with_scope(sim):
    analysis = sim.recall_analysis("fabricant", "LOT-503")
    assert analysis["target"]["records"] == ["m-lot-03"]
    by_record = {c["record"]: c for c in analysis["candidates"]}
    assert set(by_record) == {"m-asn-03", "m-cert-03", "m-gr-03"}
    coil = by_record["m-gr-03"]
    assert coil["lot"] == "COIL-103" and coil["received"] is False
    # COIL-103 a aussi servi au lot d'après-midi LOT-A30 : le périmètre le montre.
    assert coil["impact_partners"] == ["distributeur"] and coil["impact_gates"] == 4
    assert by_record["m-cert-03"]["received"] and by_record["m-cert-03"]["origin"] == "fournisseur"
    assert quarantined(sim) == set()  # lecture seule


def test_recall_from_finished_product_up_the_chain(sim):
    """Casse constatée sur chantier, sur un lot livré depuis des heures.
    Chaque maillon signale au précédent, décide au cas par cas, et seul le
    lot en cause est isolé — y compris ses « frères » déjà expédiés."""
    # 1. Le client signale au distributeur, à partir de sa réception.
    (r1,) = sim.report_upstream("client", "c-gr-03", "casse sur chantier, lot LOT-503")
    assert (r1["from"], r1["to"], r1["verified"]) == ("client", "distributeur", True)
    assert r1["records"] == ["d-out-03"]  # résolu par le distributeur seul
    assert quarantined(sim) == set()  # un signalement ne bloque rien tout seul

    # 2. Le distributeur confirme : sa réexpédition est suspecte, le client est alerté.
    sim.decide_report("distributeur", r1["id"], "confirm")
    assert {"d-out-03", "c-ship-03", "c-gr-03", "c-pay-03"} <= quarantined(sim)

    # 3. Il remonte au fabricant, qui retrouve son expédition.
    (r2,) = sim.report_upstream("distributeur", "d-out-03", "casse sur chantier")
    assert r2["to"] == "fabricant" and r2["records"] == ["m-ship-03"]

    # 4. Analyse qualité au fabricant : la bobine COIL-103 est en cause.
    causes = {c["record"] for c in sim.recall_analysis("fabricant", "m-ship-03")["candidates"]}
    assert "m-gr-03" in causes
    sim.declare_lot_suspect("fabricant", "COIL-103", "analyse : défaut matière")
    sibling = {"m-lot-a3", "m-qc-a3", "m-pack-a3", "m-tr-a3", "m-ship-a3", "d-ship-a3", "d-gr-a3"}
    assert sibling <= quarantined(sim)  # LOT-A30, fabriqué avec la même bobine
    assert sim.find_record("m-lot-04").status == "ok"  # les autres lots continuent

    # 5. Signalement au fournisseur, qui confirme : ses documents sont mis en cause.
    (r3,) = sim.report_upstream("fabricant", "COIL-103", "bobine non conforme")
    assert r3["to"] == "fournisseur" and r3["records"] == ["f-asn-03", "f-cert-03"]
    sim.decide_report("fournisseur", r3["id"], "confirm")
    assert {"f-asn-03", "f-cert-03", "m-asn-03", "m-cert-03"} <= quarantined(sim)
    # Le fournisseur n'est toujours pas déclaré compromis : ses autres envois passent.
    assert sim.find_record("f-asn-04").status == "ok"
    assert sim.find_record("m-pay-03").status == "ok"
    assert sim.audit_verify()["ok"]


def test_report_rejected_blocks_nothing(sim):
    (r,) = sim.report_upstream("client", "c-gr-03", "casse")
    view = sim.decide_report("distributeur", r["id"], "reject")
    assert view["status"] == "rejected" and quarantined(sim) == set()
    with pytest.raises(ValueError):
        sim.decide_report("distributeur", r["id"], "confirm")  # déjà traité


def test_only_recipient_can_decide_and_forged_report_cannot_be_confirmed(sim):
    (r,) = sim.report_upstream("client", "c-gr-03", "casse")
    with pytest.raises(KeyError):
        sim.decide_report("fabricant", r["id"], "confirm")
    report = sim.federation.reports[-1]
    report.reason = "motif modifié après signature"
    assert sim.federation.receive_report(report) == []  # signature invalide
    with pytest.raises(ValueError):
        sim.decide_report("distributeur", r["id"], "confirm")


def test_report_carries_only_tokens(sim):
    sim.report_upstream("client", "c-gr-03", "casse")
    payload = sim.federation.reports[-1].payload()
    assert set(payload) == {"type", "id", "from", "to", "tokens", "reason", "issued_at"}
    assert all(len(t) == 64 for t in payload["tokens"])


def test_internal_only_lot_cannot_be_reported(sim):
    # Un lot du fabricant qui ne dépend de rien de reçu (LOT-A30 dépend de COIL-103,
    # elle-même issue de données reçues : choisir un record purement interne).
    with pytest.raises(ValueError):
        sim.report_upstream("fabricant", "m-mnt-a1", "x")


def test_declare_by_record_id_too(sim):
    assert sim.declare_lot_suspect("fabricant", "m-gr-04", "défaut") == ["m-gr-04"]
    assert quarantined(sim) == COIL_104_SCOPE
    assert sim.withdraw_lot_suspect("fabricant", "m-gr-04") == ["m-gr-04"]
    assert quarantined(sim) == set()
