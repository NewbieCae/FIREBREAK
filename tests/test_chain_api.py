"""API chaîne : mode off sans effet, mode tester (EVM en mémoire) de bout en bout."""

import importlib.util
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from firebreak import api
from firebreak.chain.anchoring import Anchorer
from firebreak.chain.client import NullChain, get_chain_client
from firebreak.chain.config import ChainConfig
from firebreak.scenario import build_simulation

TEST_MNEMONIC = "test test test test test test test test test test test junk"
SINCE = {"company": "fournisseur", "since": "2026-10-10T14:00:00"}

HAS_TESTER = (
    importlib.util.find_spec("web3") is not None
    and importlib.util.find_spec("firebreak.chain.deployer") is not None
    and importlib.util.find_spec("firebreak.chain.artifact") is not None
)


@pytest.fixture
def off_client(monkeypatch):
    monkeypatch.setattr(api, "chain", NullChain())
    monkeypatch.setattr(api, "anchorer", Anchorer(api.chain))
    return TestClient(api.app)


@pytest.fixture
def tester_client(monkeypatch):
    if not HAS_TESTER:
        pytest.skip("deployer/artifact de pc1 absents")
    chain = get_chain_client(ChainConfig(mode="tester", mnemonic=TEST_MNEMONIC))
    if not chain.status()["connected"]:
        pytest.skip(f"mode tester indisponible : {chain.error}")
    monkeypatch.setattr(api, "chain", chain)
    monkeypatch.setattr(api, "anchorer", Anchorer(chain))
    monkeypatch.setattr(api, "sim", build_simulation())
    api.anchorer.on_new_simulation(api.sim)
    return TestClient(api.app)


def test_off_status(off_client):
    r = off_client.get("/api/chain/status").json()
    assert r["mode"] == "off" and r["connected"] is False
    assert r["queue"] == {"pending": 0, "sent": 0, "confirmed": 0, "failed": 0}


def test_off_verify_inchange(off_client):
    off_client.post("/api/compromise", json=SINCE)
    v = off_client.get("/api/audit/verify").json()
    assert v["ok"] is True and v["onchain_ok"] is None
    assert all(j["onchain"] is None for j in v["journals"])


def test_off_anchor_409_et_liste_vide(off_client):
    assert off_client.post("/api/chain/anchor").status_code == 409
    assert off_client.get("/api/chain/anchors").json() == []


def test_rewrite_404_sans_demo(off_client, monkeypatch):
    monkeypatch.setattr(api, "DEMO_MODE", False)
    r = off_client.post("/api/demo/rewrite",
                        json={"company": "fabricant", "drop_event": "alert_received"})
    assert r.status_code == 404


def test_tester_ancrage_et_verification(tester_client):
    assert tester_client.post("/api/compromise", json=SINCE).status_code == 200
    api.chain.flush(10)
    anchors = tester_client.get("/api/chain/anchors").json()
    kinds = {a["kind"] for a in anchors}
    assert {"alert", "ack", "incident", "audit"} <= kinds
    assert all(a["status"] == "confirmed" for a in anchors)
    v = tester_client.get("/api/audit/verify").json()
    assert v["ok"] is True and v["onchain_ok"] is True
    assert all(j["onchain"]["matches"] for j in v["journals"] if j["onchain"])


def test_tester_reecriture_detectee(tester_client, monkeypatch):
    monkeypatch.setattr(api, "DEMO_MODE", True)
    tester_client.post("/api/compromise", json=SINCE)
    api.chain.flush(10)
    r = tester_client.post("/api/demo/rewrite",
                           json={"company": "fabricant", "drop_event": "alert_received"})
    assert r.status_code == 200
    v = tester_client.get("/api/audit/verify").json()
    assert v["ok"] is True and v["onchain_ok"] is False
    fab = next(j for j in v["journals"] if j["company"] == "fabricant")
    assert fab["onchain"]["matches"] is False


def test_tester_anchor_force(tester_client):
    tester_client.post("/api/compromise", json=SINCE)
    r = tester_client.post("/api/chain/anchor")
    assert r.status_code == 200
    assert r.json() and all(a["kind"] == "audit" for a in r.json())
