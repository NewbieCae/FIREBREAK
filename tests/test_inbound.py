"""Contrôle des entrées en stock : note de confiance, mise en attente,
décision humaine. Les assertions portent sur les bandes, les décisions et
les contrôles en échec (pas sur les notes exactes), pour rester valides
quand les données de réception s'enrichissent."""

import pytest

from firebreak.inbound import TRUST_THRESHOLD
from firebreak.scenario import build_simulation

MORNING = [f"m-gr-{i:02d}" for i in range(1, 8)]


def failed(result) -> set[str]:
    return {c["id"] for c in result["checks"] if not c["ok"]}


def quarantined(sim) -> set[str]:
    return {r.id for led in sim.ledgers.values() for r in led.records.values()
            if r.status == "quarantined"}


@pytest.mark.parametrize("scenario", ["mixed", "rib", "cert", "asn", "lot", "recall"])
def test_clean_morning_deliveries_are_trusted(scenario):
    sim = build_simulation(scenario)
    for rid in MORNING:
        r = sim.inbound_check("fabricant", rid)
        assert r["band"] == "confiance" and not r["hold"], (rid, r["explanation"])
        assert r["supplier"] == "fournisseur"


def test_mixed_attack_receipt_is_suspect_and_explained():
    sim = build_simulation("mixed")
    r = sim.inbound_check("fabricant", "m-gr-X")
    assert r["band"] == "suspect" and r["hold"] and r["score"] < 60
    assert {"order", "rib"} <= failed(r)
    assert "BC-9999" in r["explanation"] and "humain" in r["explanation"]
    assert r["status"] == "non_controle"
    assert quarantined(sim) == set()  # lecture seule


def test_phantom_delivery_is_suspect():
    r = build_simulation("asn").inbound_check("fabricant", "m-gr-X")
    assert r["hold"] and "order" in failed(r)


def test_wrong_grade_certificate_is_held():
    sim = build_simulation("cert")
    if "lot" not in sim.find_record("m-cert-X").payload:
        pytest.skip("payload du certificat reçu pas encore enrichi (données de réception, pc2)")
    r = sim.inbound_check("fabricant", "m-gr-X")
    assert r["hold"] and "cert" in failed(r)


def test_screen_holds_receipt_and_everything_downstream():
    sim = build_simulation("mixed")
    r = sim.inbound_screen("fabricant", "m-gr-X")
    assert r["status"] == "en_attente"
    q = quarantined(sim)
    assert {"m-gr-X", "m-lot-X", "m-ship-X", "d-gr-X", "c-gr-X"} <= q
    # La facture au RIB modifié n'est pas une entrée en stock : hors périmètre ici.
    assert "m-pay-X" not in q
    types = [s["type"] for s in sim.timeline]
    assert types[0] == "inbound_hold"
    assert sim.audit_verify()["ok"]


def test_trusted_receipt_is_not_held():
    sim = build_simulation("mixed")
    r = sim.inbound_screen("fabricant", "m-gr-01")
    assert not r["hold"] and r["status"] == "non_controle"
    assert quarantined(sim) == set()


def test_screen_all_only_holds_doubtful_receipts():
    sim = build_simulation("mixed")
    results = {r["receipt"]: r for r in sim.inbound_screen_all("fabricant")}
    assert set(MORNING) <= set(results)
    assert all(not results[rid]["hold"] for rid in MORNING)
    assert results["m-gr-X"]["status"] == "en_attente"
    for rid, res in results.items():
        threshold = 60 if res["physically_checked"] else TRUST_THRESHOLD
        assert res["hold"] == (res["score"] < threshold)


def test_accept_makes_receipt_trusted_and_releases():
    sim = build_simulation("mixed")
    sim.inbound_screen("fabricant", "m-gr-X")
    out = sim.inbound_decide("fabricant", "m-gr-X", "accept", "contrôle physique conforme")
    assert out["status"] == "accepte"
    assert sim.find_record("m-gr-X").verified is True
    assert "m-lot-X" not in quarantined(sim)
    with pytest.raises(ValueError):
        sim.inbound_decide("fabricant", "m-gr-X", "reject")


def test_reject_keeps_isolated_and_reports_to_supplier():
    sim = build_simulation("mixed")
    sim.inbound_screen("fabricant", "m-gr-X")
    out = sim.inbound_decide("fabricant", "m-gr-X", "reject", "commande inconnue")
    assert out["status"] == "refuse"
    assert {"m-gr-X", "m-lot-X"} <= quarantined(sim)
    (report,) = out["reports"]
    assert report["to"] == "fournisseur" and report["verified"]
    assert set(report["records"]) == {"f-asn-X", "f-cert-X"}
    assert sim.audit_verify()["ok"]


def test_reject_without_prior_screen_also_isolates():
    sim = build_simulation("asn")
    out = sim.inbound_decide("fabricant", "m-gr-X", "reject")
    assert out["status"] == "refuse" and "m-gr-X" in quarantined(sim)


def test_errors():
    sim = build_simulation("mixed")
    with pytest.raises(ValueError):
        sim.inbound_check("fabricant", "m-lot-01")  # pas une réception
    with pytest.raises(KeyError):
        sim.inbound_check("fabricant", "inconnu")
    with pytest.raises(KeyError):
        sim.inbound_check("inconnue", "m-gr-01")
    with pytest.raises(ValueError):
        sim.inbound_decide("fabricant", "m-gr-X", "peut-être")


def test_cannot_accept_a_receipt_that_was_never_held():
    """Relecture pc2 : accepter sans contrôle préalable court-circuitait la mise en attente."""
    sim = build_simulation("mixed")
    with pytest.raises(ValueError):
        sim.inbound_decide("fabricant", "m-gr-X", "accept")
    assert sim.find_record("m-gr-X").verified is False
    with pytest.raises(ValueError):  # réception de confiance : jamais en attente
        sim.inbound_decide("fabricant", "m-gr-01", "accept")


def test_accept_does_not_erase_an_independent_lot_suspicion():
    """Relecture pc2 : accepter la réception effaçait un lot déclaré suspect par la qualité."""
    sim = build_simulation("lot")
    sim.declare_lot_suspect("fabricant", "COIL-104", "défaut de coulée")
    with pytest.raises(ValueError):
        sim.inbound_decide("fabricant", "m-gr-04", "accept")
    assert sim.find_record("m-gr-04").status == "quarantined"
    assert sim.ledgers["fabricant"].suspects["m-gr-04"] == "défaut de coulée"


def test_screen_does_not_overwrite_an_existing_suspicion():
    sim = build_simulation("mixed")
    sim.declare_lot_suspect("fabricant", "m-gr-X", "alerte qualité préalable")
    sim.inbound_screen("fabricant", "m-gr-X")
    assert sim.ledgers["fabricant"].suspects["m-gr-X"] == "alerte qualité préalable"
    with pytest.raises(ValueError):
        sim.inbound_decide("fabricant", "m-gr-X", "accept")


def test_physically_checked_receipt_in_doubt_is_flagged_not_held():
    """Arbitrage pc1 (relecture pc2) : la livraison de 14 h 45 a été contrôlée
    physiquement ; en zone de doute, on signale sans bloquer."""
    sim = build_simulation("mixed")
    r = sim.inbound_check("fabricant", "m-gr-08")
    assert r["physically_checked"] and r["band"] == "doute" and not r["hold"]
    assert "contrôlé physiquement" in r["explanation"]
    sim.inbound_screen("fabricant", "m-gr-08")
    assert sim.find_record("m-gr-08").status == "ok"


def test_physically_checked_but_suspect_is_still_held():
    r = build_simulation("cert").inbound_check("fabricant", "m-gr-X")
    assert r["physically_checked"] and r["band"] == "suspect" and r["hold"]
