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


def test_compromise_accepts_timezone_aware_since():
    # 12:00Z == 14:00 à Paris (heure d'été) : même résultat que la date naïve
    res = client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T12:00:00Z"})
    assert res.status_code == 200
    assert res.json()["counters"]["global"]["quarantined"] == 17


def test_validation_error_detail_is_a_string():
    res = client.post("/api/compromise", json={"company": "fournisseur"})
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)
    assert "since" in res.json()["detail"]


def test_unknown_route_error_shape():
    res = client.get("/api/nope")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found"}


def test_cors_for_dev_frontends():
    for origin in ("http://localhost:5173", "http://localhost:3000"):
        res = client.options("/api/state", headers={
            "Origin": origin, "Access-Control-Request-Method": "GET"})
        assert res.headers["access-control-allow-origin"] == origin
    res = client.get("/api/state", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in res.headers


def test_openapi_exposes_response_models():
    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    assert {"StateOut", "RecordOut", "ExplainOut", "ErrorOut"} <= set(schemas)
    ok = spec["paths"]["/api/state"]["get"]["responses"]["200"]
    assert ok["content"]["application/json"]["schema"]["$ref"].endswith("StateOut")
    assert set(schemas["RecordOut"]["properties"]["status"]["enum"]) == {
        "ok", "quarantined", "released"}
    counters = schemas["CountersBlock"]["properties"]
    assert "global" in counters
    assert "from" in schemas["AlertOut"]["properties"]


def test_state_payload_keys_stable():
    client.post("/api/compromise", json={
        "company": "fournisseur", "since": "2026-10-10T14:00:00"})
    s = client.get("/api/state").json()
    assert set(s) == {"companies", "records", "edges", "counters", "alerts", "declarations"}
    assert set(s["counters"]) == {"global", "per_company"}
    assert set(s["alerts"][0]) == {"from", "to", "tokens_count", "verified", "issued_at"}
