"""Interface finale servie par l'API (web/app/) et documents d'exemple."""

from fastapi.testclient import TestClient

from firebreak.api import app

client = TestClient(app)


def test_app_index_served():
    r = client.get("/app/")
    assert r.status_code == 200
    assert "FIREBREAK" in r.text


def test_app_assets_served():
    for path in ("/app/app.css", "/app/main.js", "/app/fonts/inter-400.woff2"):
        assert client.get(path).status_code == 200, path


def test_samples_served():
    r = client.get("/samples/facture-rib-modifie.pdf")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert client.get("/samples/epcis-sample.json").status_code == 200
