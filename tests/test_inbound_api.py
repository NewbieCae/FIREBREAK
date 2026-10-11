"""API du contrôle des entrées en stock, et ancrage sur l'EVM en mémoire."""

import pytest
from fastapi.testclient import TestClient

import firebreak.api as api_mod
from firebreak.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mixed():
    assert client.post("/api/reset", json={"scenario": "mixed"}).status_code == 200


def test_check_is_read_only_and_explained():
    r = client.get("/api/inbound/m-gr-X/check", params={"company": "fabricant"})
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == "suspect" and body["hold"] and body["status"] == "non_controle"
    assert {c["id"] for c in body["checks"]} >= {"order", "cert", "rib", "alerts"}
    state = client.get("/api/state").json()
    assert state["counters"]["global"]["quarantined"] == 0


def test_screen_one_then_reject_reports_to_supplier():
    r = client.post("/api/inbound/screen", json={"company": "fabricant", "receipt_id": "m-gr-X"})
    assert r.status_code == 200 and r.json()[0]["status"] == "en_attente"
    state = client.get("/api/state").json()
    assert state["counters"]["global"]["quarantined"] > 0
    r = client.post("/api/inbound/m-gr-X/decision",
                    json={"company": "fabricant", "decision": "reject", "reason": "commande inconnue"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "refuse" and out["reports"][0]["to"] == "fournisseur"
    audit = client.get("/api/audit", params={"company": "fabricant"}).json()
    assert {"inbound_hold", "inbound_rejected"} <= {e["event"] for e in audit["entries"]}


def test_screen_all_and_accept():
    r = client.post("/api/inbound/screen", json={"company": "fabricant"})
    assert r.status_code == 200
    held = [x["receipt"] for x in r.json() if x["status"] == "en_attente"]
    assert "m-gr-X" in held
    r = client.post("/api/inbound/m-gr-X/decision", json={"company": "fabricant", "decision": "accept"})
    assert r.status_code == 200 and r.json()["status"] == "accepte"
    assert client.post("/api/inbound/m-gr-X/decision",
                       json={"company": "fabricant", "decision": "accept"}).status_code == 400


def test_errors():
    assert client.get("/api/inbound/inconnu/check", params={"company": "fabricant"}).status_code == 404
    assert client.get("/api/inbound/m-gr-01/check", params={"company": "inconnue"}).status_code == 404
    assert client.get("/api/inbound/m-lot-01/check", params={"company": "fabricant"}).status_code == 400
    assert client.post("/api/inbound/m-gr-X/decision",
                       json={"company": "fabricant", "decision": "bof"}).status_code == 400


def test_anchoring_in_tester_mode(monkeypatch):
    pytest.importorskip("eth_tester")
    from firebreak.chain.accounts import TEST_MNEMONIC
    from firebreak.chain.anchoring import Anchorer
    from firebreak.chain.client import get_chain_client
    from firebreak.chain.config import ChainConfig

    chain = get_chain_client(ChainConfig(mode="tester", mnemonic=TEST_MNEMONIC))
    if not chain.status()["connected"]:
        pytest.skip("mode tester indisponible")
    anchorer = Anchorer(chain)
    monkeypatch.setattr(api_mod, "chain", chain)
    monkeypatch.setattr(api_mod, "anchorer", anchorer)
    anchorer.on_new_simulation(api_mod.sim)
    client.post("/api/inbound/screen", json={"company": "fabricant", "receipt_id": "m-gr-X"})
    client.post("/api/inbound/m-gr-X/decision", json={"company": "fabricant", "decision": "accept"})
    chain.flush(30)
    kinds = [(a.kind, a.status) for a in chain.anchors()]
    assert ("incident", "confirmed") in kinds
    assert all(status == "confirmed" for _, status in kinds)
    v = client.get("/api/audit/verify").json()
    assert v["ok"] and v["onchain_ok"] is True
