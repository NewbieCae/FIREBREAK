"""Timeline / SSE rejeu tests — Handoff 4.

La timeline est lue depuis les journaux d'audit chaînés ; ces tests
prouvent que le rejeu des étapes reproduit l'état final de /api/state.
"""

import json

import pytest
from fastapi.testclient import TestClient

from firebreak.api import app

client = TestClient(app)

QUARANTINE_TYPES = ("seed", "quarantine", "gate_blocked")


@pytest.fixture(autouse=True)
def fresh_state():
    client.post("/api/reset", json={"scenario": "mixed"})


def _compromise():
    hint = client.get("/api/state").json()["scenario"]["compromise"]
    res = client.post("/api/compromise", json=hint)
    assert res.status_code == 200
    return res.json()


def _rebuild_statuses(steps):
    """Rejoue les étapes -> {record_id: status} pour les records touchés."""
    status = {}
    for st in steps:
        if st["record"] is None:
            continue
        if st["type"] in QUARANTINE_TYPES:
            status[st["record"]] = "quarantined"
        elif st["type"] == "release":
            status[st["record"]] = "ok"
        elif st["type"] == "remediation":
            status[st["record"]] = "released"
    return status


def _compromise():
    hint = client.get("/api/state").json()["scenario"]["compromise"]
    res = client.post("/api/compromise", json=hint)
    assert res.status_code == 200
    return res.json()


def test_timeline_rebuilds_to_state():
    state = _compromise()
    steps = client.get("/api/timeline").json()["steps"]
    assert len(steps) > 10

    rebuilt = _rebuild_statuses(steps)
    for r in state["records"]:
        if r["status"] != "ok":
            assert rebuilt.get(r["id"]) == r["status"], \
                f"{r['id']}: state={r['status']} rebuilt={rebuilt.get(r['id'])}"
    extra = {rid for rid, s in rebuilt.items() if s == "quarantined"} - {
        r["id"] for r in state["records"] if r["status"] == "quarantined"}
    assert extra == set()

    # les compteurs cumulés de la dernière étape == compteurs de l'état
    last = steps[-1]["counters"]
    g = state["counters"]["global"]
    assert last["quarantined"] == g["quarantined"]
    assert last["gates_blocked"] == g["gates_blocked"]
    assert last["amount_blocked"] == g["amount_blocked"]
    assert last["amount_flowing"] == g["amount_flowing"]


def test_causal_ordering():
    _compromise()
    steps = client.get("/api/timeline").json()["steps"]
    seen = {}
    for st in steps:
        if st["type"] in QUARANTINE_TYPES:
            if st["parent"]:
                assert st["parent"] in seen, \
                    f"{st['record']} contaminé avant son parent {st['parent']}"
                assert seen[st["parent"]] < st["n"]
            seen[st["record"]] = st["n"]
    sent, received = {}, {}
    for st in steps:
        if st["type"] == "alert_sent":
            sent[(st["alert"]["from"], st["alert"]["to"])] = st["n"]
        elif st["type"] == "alert_received":
            received[(st["alert"]["from"], st["alert"]["to"])] = st["n"]
    for key, n in received.items():
        assert key in sent and sent[key] < n, \
            f"alerte {key} reçue avant d'être émise"


def test_alert_links_resolve_to_cross_edges():
    state = _compromise()
    cross = {(e["source"], e["target"]) for e in state["edges"] if e["cross"]}
    steps = client.get("/api/timeline").json()["steps"]
    alert_steps = [s for s in steps if s["type"] == "alert_sent"]
    assert alert_steps
    for st in alert_steps:
        assert st["alert"]["links"]
        for pair in st["alert"]["links"]:
            assert tuple(pair) in cross


def test_running_counters_end_at_state():
    state = _compromise()
    steps = client.get("/api/timeline").json()["steps"]
    last = steps[-1]["counters"]
    g = state["counters"]["global"]
    assert last["quarantined"] == g["quarantined"]
    assert last["gates_blocked"] == g["gates_blocked"]
    assert last["amount_blocked"] == g["amount_blocked"]
    assert last["amount_flowing"] == g["amount_flowing"]
    # mixed : seul le paiement au RIB frauduleux est bloqué (5 210 €).
    # Les 14 autres paiements continuent : m-pay-01..07 = Σ(4000+317·i)
    # = 36 876 € et c-pay-01..07 = Σ(amount+950) = 43 526 €.
    assert g["amount_blocked"] == 5210
    assert g["amount_flowing"] == 36876 + 43526 == 80402
    # compteurs d'étape monotones pendant la contamination
    for a, b in zip(steps, steps[1:]):
        assert b["counters"]["quarantined"] >= a["counters"]["quarantined"]


def test_timeline_all_scenarios():
    for scenario in ("mixed", "rib", "cert", "asn"):
        client.post("/api/reset", json={"scenario": scenario})
        state = _compromise()
        steps = client.get("/api/timeline").json()["steps"]
        assert len(steps) > 3, scenario
        assert any(s["type"] == "declaration" for s in steps), scenario
        assert any(s["type"] in QUARANTINE_TYPES for s in steps), scenario
        rebuilt = _rebuild_statuses(steps)
        for r in state["records"]:
            if r["status"] == "quarantined":
                assert rebuilt.get(r["id"]) == "quarantined", \
                    f"{scenario}:{r['id']}"
        last = steps[-1]["counters"]
        g = state["counters"]["global"]
        assert last["quarantined"] == g["quarantined"], scenario
        assert last["amount_blocked"] == g["amount_blocked"], scenario
        # amount_blocked peut être 0 si la chaîne contaminée ne porte
        # pas de montant (ex. scénario asn) ; le total doit être positif
        assert g["amount_blocked"] + g["amount_flowing"] > 0, scenario


def test_timeline_remediate_release_cascade():
    state = _compromise()
    target = next(r["id"] for r in state["records"]
                  if r["status"] == "quarantined"
                  and r["company"] == "fabricant"
                  and r["kind"] == "goods_receipt")
    res = client.post(f"/api/records/{target}/remediate",
                      json={"action": "human_approval"})
    assert res.status_code == 200
    steps = client.get("/api/timeline").json()["steps"]
    types = [s["type"] for s in steps]
    assert "remediation" in types and "release" in types
    last = steps[-1]["counters"]
    assert last["quarantined"] == res.json()["counters"]["global"]["quarantined"]


def test_timeline_withdraw_releases_all():
    _compromise()
    res = client.post("/api/compromise/withdraw", json={"company": "fournisseur"})
    assert res.status_code == 200
    steps = client.get("/api/timeline").json()["steps"]
    assert any(s["type"] == "withdrawal" for s in steps)
    assert any(s["type"] == "release" for s in steps)
    assert steps[-1]["counters"]["quarantined"] == 0
    assert res.json()["counters"]["global"]["quarantined"] == 0


def test_sse_streams_events():
    _compromise()
    with client.stream("GET", "/api/events?speed=0") as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        data_lines = []
        for line in res.iter_lines():
            if line.startswith("data: "):
                data_lines.append(line)
            if len(data_lines) >= 3:
                break
        assert len(data_lines) >= 3
        first = json.loads(data_lines[0][6:])
        assert first["n"] == 1
        assert "type" in first and "counters" in first


def test_timeline_empty_fresh():
    steps = client.get("/api/timeline").json()["steps"]
    assert steps == []
