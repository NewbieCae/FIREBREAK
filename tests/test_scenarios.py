"""Les quatre scénarios : ensembles de quarantaine raisonnés à la main."""

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
    # Fraude au RIB : tout ce que le fournisseur émet après 14:00 (dont la facture
    # légitime F-3008), les copies reçues, la fiche fournisseur modifiée et le
    # paiement qui en dépend. Le contre-appel (verified) protège le paiement F-3008.
    # Aucun objet physique : rien ne part vers le distributeur.
    "rib": {
        "f-bank-X", "f-inv-X", "f-inv-08",
        "m-bank-X", "m-inv-X", "m-inv-08", "m-vendor-X", "m-pay-X",
    },
    # Faux certificat : la réception pesée (verified) arrête la contamination de
    # l'ASN, mais la libération qualité dépend du certificat. LOT-901 contient
    # COIL-210, ASM-950 contient LOT-901 : bloqués jusqu'au client. LOT-902 continue.
    "cert": {
        "f-asn-X", "f-cert-X",
        "m-asn-X", "m-cert-X", "m-qc-X", "m-lot-901", "m-asm-950", "m-ship-950",
        "d-ship-950", "d-gr-950", "d-out-950",
        "c-ship-950", "c-gr-950",
    },
    # Faux ASN : réception sans contrôle, stock fantôme, lot lancé dessus,
    # expédition, réservation, réexpédition, planning chantier. L'ASN légitime
    # BC-1008 est suspect (fenêtre) mais sa réception contrôlée arrête tout.
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

STOPPERS = {  # record verified dont une entrée est contaminée
    "mixed": "m-gr-08",
    "rib": "m-call-08",
    "cert": "m-gr-X",
    "asn": "m-gr-08",
}


def _declared(name):
    sim = build_simulation(name)
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    return sim


def _records(sim):
    return {r.id: r for led in sim.ledgers.values() for r in led.records.values()}


def test_all_scenarios_covered():
    assert set(SCENARIOS) == set(EXPECTED)


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
    assert 100 <= total <= 150
    assert 0 < len(quarantined) < 0.15 * total
    assert {r.id for r in quarantined if r.gate} == GATES_BLOCKED[name]
    stopper = records[STOPPERS[name]]
    assert stopper.verified and stopper.status == "ok"
    assert any(records[i].status == "quarantined" for i in stopper.inputs)


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
