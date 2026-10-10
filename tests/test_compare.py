"""« Avec vs sans Firebreak » — comparaison de politiques (GET /api/compare).

Vérité terrain (indépendante des statuts) : BFS depuis les records émis
par la source dans son propre registre après `since`, le long des
inputs + envois inter-entreprises ; `verified` arrête la propagation.
"""

import json

import pytest
from fastapi.testclient import TestClient

import firebreak.compare as compare_mod
from firebreak.api import app

client = TestClient(app)

# Raisonné depuis scenario.py (attaque mixed, fournisseur compromise 14 h) :
# truth = les 4 records émis par le fournisseur après 14 h + leurs copies
# reçues et dérivés en aval. m-gr-08 est `verified` → arrête la propagation.
TRUTH_MIXED = {
    "f-asn-X", "f-cert-X", "f-inv-X", "f-asn-08",
    "m-asn-X", "m-cert-X", "m-inv-X", "m-asn-08",
    "m-gr-X", "m-lot-X", "m-pay-X", "m-ship-X",
    "d-ship-X", "d-gr-X", "d-out-X",
    "c-ship-X", "c-gr-X",
}
# Périmètre de la politique B : fournisseur + client direct = fabricant.
# Bloqués : tout record f/m avec ts >= 14:00, soit les 12 contaminés +
# m-ship-07 (14:00 pile, sain) + m-gr-08 (vérifié, sain) + les 40 records
# légitimes d'après-midi du fabricant = 54.
AFTERNOON_M = {
    *[f"m-lot-a{i}" for i in range(1, 7)],
    *[f"m-qc-a{i}" for i in range(1, 7)],
    *[f"m-pack-a{i}" for i in range(1, 7)],
    *[f"m-tr-a{i}" for i in range(1, 5)],
    *[f"m-ship-a{i}" for i in range(1, 5)],
    *[f"m-po-a{i}" for i in range(1, 5)],
    *[f"m-pay-a{i}" for i in range(1, 5)],
    "m-so-a1", "m-so-a2", "m-ic-a1", "m-mnt-a1", "m-qc-a7", "m-adj-a1",
}
B_BLOCKED = 54
B_HEALTHY = {"m-ship-07", "m-gr-08"} | AFTERNOON_M
B_LEAKS = {"d-ship-X", "d-gr-X", "d-out-X", "c-ship-X", "c-gr-X"}


@pytest.fixture(autouse=True)
def fresh_state():
    client.post("/api/reset", json={"scenario": "mixed"})


def _compromise():
    res = client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    assert res.status_code == 200
    return res.json()


def test_400_without_declaration():
    res = client.get("/api/compare")
    assert res.status_code == 400
    assert "déclaration" in res.json()["detail"]


def test_truth_and_metrics_mixed():
    _compromise()
    d = client.get("/api/compare").json()

    assert d["declarations"] == [
        {"company": "fournisseur", "since": "2026-10-10T14:00:00"}]
    assert d["truth"]["contaminated"] == len(TRUTH_MIXED)

    b, c = d["without"], d["with"]
    assert b["policy"] == "B" and c["policy"] == "C"
    assert set(b["blocked_ids"]) - TRUTH_MIXED == B_HEALTHY
    assert b["blocked"] == B_BLOCKED
    assert b["healthy_blocked"] == 42
    assert {l["id"] for l in b["leaked_ids"]} == B_LEAKS
    assert b["companies_hit"] == ["fabricant", "fournisseur"]
    # vérité bloquée par B = les 12 contaminés du périmètre f+m
    assert b["recall"] == pytest.approx(12 / 17)

    assert set(c["blocked_ids"]) == TRUTH_MIXED
    assert c["blocked"] == 17 and c["healthy_blocked"] == 0 and c["leaked"] == 0
    assert c["precision"] == 1.0 and c["recall"] == 1.0
    assert c["companies_hit"] == ["client", "distributeur", "fabricant", "fournisseur"]

    assert d["healthy_blocked_ratio"] is None  # 0 sain bloqué avec C


def test_truth_independent_of_statuses():
    _compromise()
    before = client.get("/api/compare").json()["truth"]["contaminated"]
    client.post("/api/records/m-gr-X/remediate", json={"action": "human_approval"})
    d = client.get("/api/compare").json()
    assert d["truth"]["contaminated"] == before == 17
    # mais la politique C reflète la remédiation
    assert "m-gr-X" not in d["with"]["blocked_ids"]


def test_payments_and_gates():
    _compromise()
    d = client.get("/api/compare").json()
    b, c = d["without"], d["with"]
    # B : le RIB frauduleux + les 4 paiements d'après-midi (2250+2700+3150+3600)
    assert b["payments_blocked_eur"] == 5210 + 11700 == 16910
    assert c["payments_blocked_eur"] == 5210
    assert b["payments_flowing_eur"] == 97312 - 16910 == 80402
    assert c["payments_flowing_eur"] == 97312 - 5210 == 92102
    # B bloque 3 gates contaminés (m-lot-X, m-pay-X, m-ship-X) + le gate sain
    # m-ship-07 (14:00 pile) + 14 gates d'après-midi : 6 lots, 4 paiements,
    # 4 expéditions = 18
    assert b["gates_blocked"] == 3 + 1 + 14 == 18
    assert c["gates_blocked"] == 4


def test_bench_block_present_and_coherent():
    _compromise()
    d = client.get("/api/compare").json()
    assert d["bench"] is not None
    assert d["bench"]["seeds_per_group"] == 500
    assert d["bench"]["p_values"] == ["0.0", "0.1", "0.2", "0.3"]
    g = d["bench"]["groups"]
    b0, c0 = g["p0.0:B"], g["p0.0:C"]
    assert b0["seeds"] == c0["seeds"] == 500
    # cohérent avec docs/bench-results.md
    assert b0["healthy_blocked_mean"] == pytest.approx(49.5, abs=0.2)
    assert c0["healthy_blocked_mean"] == pytest.approx(11.4, abs=0.2)
    assert c0["recall_mean"] == pytest.approx(1.0, abs=0.01)
    assert b0["recall_mean"] == pytest.approx(0.98, abs=0.01)


def test_bench_null_when_csv_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(compare_mod, "BENCH_CSV", tmp_path / "nope.csv")
    _compromise()
    d = client.get("/api/compare").json()
    assert d["bench"] is None


def test_real_world_texts_exact():
    _compromise()
    d = client.get("/api/compare").json()
    rw = {r["name"]: r for r in d["real_world"]}
    assert rw["Jaguar Land Rover"]["date"] == "septembre 2025"
    assert rw["Jaguar Land Rover"]["text"].startswith(
        "Après une cyberattaque, JLR coupe ses systèmes")
    assert "196 M£" in rw["Jaguar Land Rover"]["text"]
    assert rw["CDK Global"]["date"] == "juin 2024"
    assert "15 000 concessions" in rw["CDK Global"]["text"]
    assert rw["CDK Global"]["source"].startswith("https://www.cnn.com/")


def test_compare_all_scenarios():
    for scenario in ("mixed", "rib", "cert", "asn"):
        client.post("/api/reset", json={"scenario": scenario})
        hint = client.get("/api/state").json()["scenario"]["compromise"]
        assert client.post("/api/compromise", json=hint).status_code == 200
        d = client.get("/api/compare").json()
        assert d["truth"]["contaminated"] > 0, scenario
        assert d["without"]["blocked"] > 0, scenario
        assert d["with"]["blocked"] == d["truth"]["contaminated"], scenario
        # la timeline reflète toujours l'état
        steps = client.get("/api/timeline").json()["steps"]
        g = client.get("/api/state").json()["counters"]["global"]
        assert steps[-1]["counters"]["quarantined"] == g["quarantined"], scenario
