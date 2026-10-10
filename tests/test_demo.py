"""Démo de bout en bout — Handoff 6.

Rejoue exactement le script de docs/demo.md via l'API :
reset → compromise → rejeu timeline → explain → remediate → release
fédérée → audit verify. Plus le stepper /api/demo/step, la latence de
/api/state (< 200 ms) et la fiabilité du reset.
"""

import time

import pytest
from fastapi.testclient import TestClient

from firebreak.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    client.post("/api/reset", json={"scenario": "mixed"})


def test_demo_script_end_to_end():
    # 1. reset
    s = client.post("/api/reset", json={"scenario": "mixed"}).json()
    assert s["counters"]["global"]["quarantined"] == 0
    assert s["alerts"] == []

    # 2. compromise
    s = client.post("/api/compromise", json=s["scenario"]["compromise"]).json()
    g = s["counters"]["global"]
    assert g["quarantined"] > 0 and g["gates_blocked"] >= 1

    # 3. rejeu pas à pas : la timeline reconstruit l'état
    steps = client.get("/api/timeline").json()["steps"]
    assert steps and steps[-1]["counters"]["quarantined"] == g["quarantined"]

    # 4. explain le paiement au RIB modifié
    ex = client.get("/api/records/m-pay-X/explain").json()
    assert ex["record"]["status"] == "quarantined"
    assert ex["path"]

    # 5. remediate → release fédérée : alertes de levée signées vers l'aval
    s = client.post("/api/records/m-gr-X/remediate",
                    json={"action": "human_approval"}).json()
    statuses = {r["id"]: r["status"] for r in s["records"]}
    assert statuses["m-gr-X"] == "released"
    assert statuses["m-lot-X"] == "ok"
    assert any(a["type"] == "release" for a in s["alerts"]), \
        "aucune alerte de levée émise vers l'aval"

    # 6. audit verify : journaux intègres
    v = client.get("/api/audit/verify").json()
    assert v["ok"] and sum(j["entries"] for j in v["journals"]) > 0


def test_demo_step_drives_the_script():
    r0 = client.post("/api/demo/step").json()          # reset
    assert r0["step"] == 0 and r0["done"] is False
    assert r0["state"]["counters"]["global"]["quarantined"] == 0

    r1 = client.post("/api/demo/step").json()          # compromise
    assert r1["step"] == 1
    assert r1["state"]["counters"]["global"]["quarantined"] > 0
    assert r1["detail"]["steps"] > 0                    # timeline disponible

    r2 = client.post("/api/demo/step").json()          # avec vs sans
    assert r2["step"] == 2
    assert r2["detail"]["without"]["policy"] == "B"
    assert r2["detail"]["with"]["policy"] == "C"
    assert r2["detail"]["with"]["healthy_blocked"] == 0

    r3 = client.post("/api/demo/step").json()          # explain m-pay-X
    assert r3["step"] == 3 and r3["detail"]["explanation"]
    assert r3["detail"]["record"]["id"] == "m-pay-X"

    r4 = client.post("/api/demo/step").json()          # remediate → cascade
    assert r4["step"] == 4 and r4["error"] is None
    st = {r["id"]: r["status"] for r in r4["state"]["records"]}
    assert st["m-gr-X"] == "released" and st["m-lot-X"] == "ok"

    r5 = client.post("/api/demo/step").json()          # audit verify
    assert r5["step"] == 5 and r5["detail"]["ok"] is True
    assert r5["done"] is True

    r6 = client.post("/api/demo/step").json()          # reste en fin
    assert r6["step"] == 6 and r6["done"] is True
    assert r6["caption"]

    for r in (r0, r1, r2, r3, r4, r5, r6):
        assert r["caption"]  # légende française toujours présente


def test_state_latency_under_200ms():
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    worst = 0.0
    for _ in range(10):
        t0 = time.perf_counter()
        res = client.get("/api/state")
        worst = max(worst, time.perf_counter() - t0)
        assert res.status_code == 200
    assert worst < 0.2, f"/api/state trop lent : {worst * 1000:.0f} ms"


def test_reset_reliable_between_runs():
    for _ in range(2):
        s = client.post("/api/reset", json={"scenario": "mixed"}).json()
        assert s["counters"]["global"]["quarantined"] == 0
        assert s["alerts"] == [] and s["declarations"] == []
        assert client.get("/api/timeline").json()["steps"] == []
