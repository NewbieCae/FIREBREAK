import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from firebreak.api import app
from firebreak.ingest.epcis import EpcisError, cbv_term, lot_of, owner_of, parse_epcis
from firebreak.scenario import COMPANIES, COMPROMISED_SINCE, build_simulation

SAMPLE = json.loads((Path(__file__).resolve().parents[1]
                     / "assets/samples/epcis-sample.json").read_text())
client = TestClient(app)

# Sample (registre du fabricant) : COIL-12 livrée à 09:00, COIL-77 et COIL-78
# expédiées après 14:00 ; COIL-78 contrôlée conforme ; LOT-801 = COIL-77 + COIL-12,
# LOT-802 = COIL-78 ; LOT-801 palettisé puis expédié au distributeur.
EXPECTED_TAINTED = {
    "m-epcis-03",  # avis d'expédition COIL-77 (14:20, fournisseur)
    "m-epcis-04",  # avis d'expédition COIL-78 (14:30, fournisseur)
    "m-epcis-05",  # réception COIL-77
    "m-epcis-06",  # réception COIL-78
    "m-epcis-08",  # transformation COIL-77 + COIL-12 → LOT-801
    "m-epcis-10",  # palettisation LOT-801
    "m-epcis-11",  # expédition de la palette
}


def _parse(doc=SAMPLE, sim=None):
    sim = sim or build_simulation()
    return sim, parse_epcis(doc, "fabricant", COMPANIES,
                            sim.ledgers["fabricant"].records, "m")


def test_helpers():
    assert cbv_term("urn:epcglobal:cbv:bizstep:shipping") == "shipping"
    assert cbv_term("https://ref.gs1.org/cbv/BizStep-receiving") == "receiving"
    assert cbv_term("inspecting") == "inspecting"
    assert lot_of("urn:epc:class:lgtin:3012345.012345.COIL-77") == "COIL-77"
    assert lot_of("https://id.gs1.org/01/03012345123456/10/LOT-5") == "LOT-5"
    assert owner_of("urn:epc:id:sgln:3023456.00001.0", COMPANIES) == "fabricant"
    assert owner_of("https://id.gs1.org/414/3034567000017", COMPANIES) == "distributeur"
    assert owner_of("urn:epc:id:sgln:9999999.00001.0", COMPANIES) is None


def test_sample_conversion():
    _, result = _parse()
    assert result.ignored == [] and result.events == 11
    recs = {r.id: r for r in result.records}
    assert len(recs) == 11
    assert recs["m-epcis-01"].kind == "asn" and recs["m-epcis-01"].origin == "fournisseur"
    assert recs["m-epcis-02"].inputs == ["m-epcis-01"]
    qc = recs["m-epcis-07"]
    assert qc.kind == "quality_check" and qc.verified
    lot = recs["m-epcis-08"]
    assert lot.kind == "production_lot" and lot.gate
    assert lot.inputs == ["m-epcis-05", "m-epcis-02"]
    assert lot.payload["lot"] == "LOT-801"
    assert lot.payload["input_lots"] == ["COIL-77", "COIL-12"]
    assert recs["m-epcis-10"].inputs == ["m-epcis-08"]
    ship = recs["m-epcis-11"]
    assert ship.kind == "shipment" and ship.gate and ship.inputs == ["m-epcis-10"]
    assert ship.ts.isoformat() == "2026-10-10T16:00:00"


def test_sample_follows_rules_after_compromise():
    sim, result = _parse()
    for r in result.records:
        sim.ledgers["fabricant"].add(r)
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    tainted = {r.id for r in result.records if r.status == "quarantined"}
    assert tainted == EXPECTED_TAINTED


def test_unsupported_and_invalid_events_are_reported():
    doc = copy.deepcopy(SAMPLE)
    doc["epcisBody"]["eventList"] += [
        {"type": "AssociationEvent", "eventTime": "2026-10-10T16:00:00+02:00"},
        {"type": "ObjectEvent", "action": "OBSERVE", "epcList": ["urn:x"]},
        {"type": "ObjectEvent", "action": "OBSERVE", "eventTime": "2026-10-10T16:00:00Z",
         "epcList": ["urn:x"], "bizLocation": {"id": "urn:epc:id:sgln:9999999.00001.0"}},
        {**doc["epcisBody"]["eventList"][0], "errorDeclaration": {"declarationTime": "x"}},
    ]
    _, result = _parse(doc)
    assert len(result.records) == 11
    assert [i["index"] for i in result.ignored] == [11, 12, 14, 13]
    reasons = " ".join(i["reason"] for i in result.ignored)
    assert "non géré" in reasons and "eventTime" in reasons and "GLN inconnu" in reasons


@pytest.mark.parametrize("doc", [{}, {"type": "EPCISDocument"}, [], "x"])
def test_invalid_document(doc):
    with pytest.raises(EpcisError):
        _parse(doc)


def test_second_import_links_to_first():
    sim, first = _parse()
    for r in first.records:
        sim.ledgers["fabricant"].add(r)
    follow_up = {"type": "EPCISDocument", "epcisBody": {"eventList": [{
        "type": "ObjectEvent", "action": "OBSERVE", "bizStep": "inspecting",
        "eventTime": "2026-10-10T16:30:00+02:00", "disposition": "non_conformant",
        "quantityList": [{"epcClass": "urn:epc:class:lgtin:3023456.067890.LOT-802"}],
        "bizLocation": {"id": "urn:epc:id:sgln:3023456.00001.0"}}]}}
    _, second = _parse(follow_up, sim)
    (rec,) = second.records
    assert rec.id == "m-epcis-12" and rec.inputs == ["m-epcis-09"]
    assert not rec.verified  # non conforme : pas une source de confiance


class TestApi:
    @pytest.fixture(autouse=True)
    def fresh(self):
        client.post("/api/reset")

    def test_import_then_compromise(self):
        res = client.post("/api/ingest/epcis?company=fabricant", json=SAMPLE)
        assert res.status_code == 200
        body = res.json()
        assert body["events"] == 11 and len(body["imported"]) == 11
        assert body["state"]["counters"]["global"]["total"] == 193 + 11
        audit = client.get("/api/audit?company=fabricant").json()["entries"]
        assert audit[-1]["event"] == "epcis_import"
        state = client.post("/api/compromise", json={
            "company": "fournisseur", "since": "2026-10-10T14:00:00"}).json()
        tainted = {r["id"] for r in state["records"]
                   if r["id"].startswith("m-epcis") and r["status"] == "quarantined"}
        assert tainted == EXPECTED_TAINTED
        assert client.get("/api/audit/verify").json()["ok"]

    def test_errors(self):
        assert client.post("/api/ingest/epcis?company=nope", json=SAMPLE).status_code == 404
        res = client.post("/api/ingest/epcis?company=fabricant", json={"type": "x"})
        assert res.status_code == 400 and "EPCISDocument" in res.json()["detail"]
