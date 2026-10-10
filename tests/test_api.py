import pytest
from fastapi.testclient import TestClient

from firebreak.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    client.post("/api/reset")


def test_state():
    res = client.get("/api/state")
    assert res.status_code == 200
    s = res.json()
    assert len(s["companies"]) == 4
    assert s["counters"]["global"]["quarantined"] == 0
    assert any(e["cross"] for e in s["edges"])
    assert {r["status"] for r in s["records"]} == {"ok"}


def test_compromise():
    res = client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    assert res.status_code == 200
    g = res.json()["counters"]["global"]
    assert g["quarantined"] > 0
    assert g["gates_blocked"] >= 1
    assert len(res.json()["alerts"]) >= 3


def test_compromise_unknown_company():
    res = client.post("/api/compromise", json={
        "company": "inconnu", "since": "2026-10-10T14:00:00"})
    assert res.status_code == 404


def test_explain():
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    res = client.get("/api/records/m-pay-X/explain")
    assert res.status_code == 200
    data = res.json()
    assert data["record"]["id"] == "m-pay-X"
    assert [r["id"] for r in data["path"]] == data["record"]["taint_path"]
    assert "quarantaine" in data["explanation"]
    assert {p["action"] for p in data["remediation_plan"]} == {
        "revalidate", "human_approval", "trusted_source"}


def test_explain_404():
    assert client.get("/api/records/nope/explain").status_code == 404


def test_remediate():
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    res = client.post("/api/records/m-gr-X/remediate",
                      json={"action": "human_approval"})
    assert res.status_code == 200
    states = {r["id"]: r["status"] for r in res.json()["records"]}
    assert states["m-gr-X"] == "released"
    assert states["m-lot-X"] == "ok"


def test_remediate_errors():
    res = client.post("/api/records/f-int-01/remediate",
                      json={"action": "revalidate"})
    assert res.status_code == 400  # pas en quarantaine
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    res = client.post("/api/records/m-pay-X/remediate", json={"action": "hack"})
    assert res.status_code == 400


def test_reset():
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    s = client.post("/api/reset").json()
    assert s["counters"]["global"]["quarantined"] == 0
    assert s["alerts"] == []
