"""Endpoints qualité : lot suspect, analyse de rappel, signalements amont."""

import pytest
from fastapi.testclient import TestClient

from firebreak import api
from firebreak.chain.anchoring import Anchorer
from firebreak.chain.client import NullChain
from firebreak.scenario import build_simulation


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "chain", NullChain())
    monkeypatch.setattr(api, "anchorer", Anchorer(api.chain))
    monkeypatch.setattr(api, "sim", build_simulation("recall"))
    api.anchorer.on_new_simulation(api.sim)
    return TestClient(api.app)


def _quarantined(state):
    return {r["id"] for r in state["records"] if r["status"] == "quarantined"}


def test_lot_suspect_then_withdraw_without_blacklisting(client):
    r = client.post("/api/lots/suspect", json={
        "company": "fabricant", "lot": "COIL-104", "reason": "défaut de coulée"})
    assert r.status_code == 200
    q = _quarantined(r.json())
    assert {"m-lot-04", "m-lot-a4"} <= q
    assert "m-pay-04" not in q and "f-inv-04" not in q  # fournisseur non blacklisté
    assert r.json()["declarations"] == []
    audit = client.get("/api/audit", params={"company": "fabricant"}).json()
    assert "lot_suspect" in {e["event"] for e in audit["entries"]}

    r = client.post("/api/lots/suspect/withdraw",
                    json={"company": "fabricant", "lot": "COIL-104"})
    assert r.status_code == 200 and _quarantined(r.json()) == set()
    steps = client.get("/api/timeline").json()
    assert steps["steps"]


def test_lot_suspect_errors(client):
    assert client.post("/api/lots/suspect",
                       json={"company": "nope", "lot": "X", "reason": ""}).status_code == 404
    assert client.post("/api/lots/suspect/withdraw",
                       json={"company": "fabricant", "lot": "COIL-104"}).status_code == 400


def test_recall_analysis_is_read_only(client):
    r = client.get("/api/recall", params={"company": "fabricant", "ref": "m-ship-03"})
    assert r.status_code == 200
    assert "m-gr-03" in {c["record"] for c in r.json()["candidates"]}
    assert _quarantined(client.get("/api/state").json()) == set()
    assert client.get("/api/recall",
                      params={"company": "fabricant", "ref": "zzz"}).status_code in (400, 404)


def test_report_chain_client_to_distributeur(client):
    r = client.post("/api/reports", json={
        "company": "client", "ref": "c-gr-03", "reason": "casse sur chantier"})
    assert r.status_code == 200
    (rep,) = r.json()
    assert (rep["from"], rep["to"], rep["verified"], rep["status"]) == \
        ("client", "distributeur", True, "pending")
    inbox = client.get("/api/reports", params={"company": "distributeur"}).json()
    assert [x["id"] for x in inbox] == [rep["id"]]
    assert _quarantined(client.get("/api/state").json()) == set()

    # mauvais destinataire : refusé
    assert client.post(f"/api/reports/{rep['id']}/decision",
                       json={"company": "fabricant", "decision": "confirm"}).status_code == 404
    assert client.post(f"/api/reports/{rep['id']}/decision",
                       json={"company": "distributeur", "decision": "maybe"}).status_code == 400

    d = client.post(f"/api/reports/{rep['id']}/decision",
                    json={"company": "distributeur", "decision": "confirm"})
    assert d.status_code == 200 and d.json()["status"] == "confirmed"
    types = {s["type"] for s in client.get("/api/timeline").json()["steps"]}
    assert "report_decided" in types
    for company in ("client", "distributeur"):
        assert client.get("/api/audit", params={"company": company}).status_code == 200
    assert "d-out-03" in _quarantined(client.get("/api/state").json())
    # déjà traité
    assert client.post(f"/api/reports/{rep['id']}/decision",
                       json={"company": "distributeur", "decision": "reject"}).status_code == 400


def test_reports_unknown_company(client):
    assert client.get("/api/reports", params={"company": "nope"}).status_code == 404
