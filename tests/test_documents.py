import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from firebreak.ai import BedrockConverser
from firebreak.api import app
from firebreak.ingest.documents import (
    BedrockExtractor,
    DocumentError,
    MockExtractor,
    Party,
    document_text,
    get_extractor,
)
from firebreak.scenario import COMPANIES, RIB_FRAUD, RIB_OK

SAMPLES = Path(__file__).resolve().parents[1] / "assets" / "samples"
PARTIES = [Party(c.id, c.name) for c in COMPANIES]
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_state():
    client.post("/api/reset")


def sample_text(name):
    return document_text((SAMPLES / name).read_bytes())


def extract(name, company="fabricant", known=None):
    return MockExtractor().extract(sample_text(name), company, PARTIES, known)


# -- mock extraction (regex) -----------------------------------------------------


def test_invoice_with_modified_rib_pdf():
    out = extract("facture-rib-modifie.pdf")
    assert out["source"] == "mock"
    assert out["kind"] == "invoice"
    assert out["origin"] == "fournisseur"
    assert out["label"] == "Received invoice F-9999 — new bank details"
    p = out["payload"]
    assert p["amount"] == 5210
    assert p["rib"] == RIB_FRAUD
    assert p["previous_rib"] == RIB_OK
    assert p["bank_details_change"] is True
    assert {"F-9999", "BC-9999"} <= set(p["references"])
    assert "2026-10-10" in p["dates"]
    assert out["missing"] == []
    assert 0.8 <= out["confidence"] <= 0.9


def test_shipping_notice_mail():
    out = extract("avis-expedition.eml")
    assert out["kind"] == "asn"
    assert out["origin"] == "fournisseur"
    assert out["label"] == "Received ASN — BC-1009"
    assert {"BC-1009", "BL-4409"} <= set(out["payload"]["references"])
    assert out["payload"]["dates"][:2] == ["2026-10-10", "2026-10-12"]
    assert "rib" not in out["payload"]


def test_purchase_order_text():
    out = extract("bon-de-commande.txt")
    assert out["kind"] == "purchase_order"
    assert out["origin"] == "distributeur"
    assert out["payload"]["amount"] == 12480
    assert out["payload"]["references"] == ["BC-7001"]


def test_rib_change_mail_and_unknown_rib():
    text = ("Objet : changement de RIB\n\nBonjour, Aciers Durand vous informe de ses "
            "nouvelles coordonnées bancaires : FR76 9999 8888 7777 6666 5555 444.")
    out = MockExtractor().extract(text, "fabricant", PARTIES,
                                  {"fournisseur": {RIB_OK}})
    assert out["kind"] == "bank_details_change"
    assert out["payload"]["rib"] == "FR76 9999 8888 7777 6666 5555 444"
    assert out["payload"]["bank_details_change"] is True
    assert out["payload"]["rib_unknown_for_origin"] is True


def test_unclassified_document_low_confidence():
    out = MockExtractor().extract("Bonjour, à bientôt.", "fabricant", PARTIES)
    assert out["kind"] is None
    assert out["confidence"] < 0.3
    assert "kind" in out["missing"]


def test_empty_and_textless_documents():
    with pytest.raises(DocumentError):
        document_text(b"   ")
    with pytest.raises(DocumentError):
        document_text(b"%PDF-1.4 garbage")


def test_extractor_selection(monkeypatch):
    monkeypatch.delenv("FIREBREAK_AI", raising=False)
    assert isinstance(get_extractor(), MockExtractor)
    monkeypatch.setenv("FIREBREAK_AI", "bedrock")
    assert isinstance(get_extractor(), BedrockExtractor)


# -- Bedrock extraction (fake client) ----------------------------------------------


class FakeClient:
    def __init__(self, reply):
        self.reply = reply

    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": json.dumps(self.reply)}]}}}


def bedrock_extract(reply):
    ext = BedrockExtractor(BedrockConverser(client=FakeClient(reply), model="m"))
    return ext.extract(sample_text("facture-rib-modifie.pdf"), "fabricant", PARTIES)


BEDROCK_REPLY = {
    "kind": "invoice", "origin": "fournisseur", "confidence": 0.93,
    "payload": {"amount": 5210.0, "rib": "FR7612345678900000000000666",
                "bank_details_change": True, "references": ["F-9999", "BC-9999"],
                "dates": ["2026-10-10"]},
}


def test_bedrock_extraction_valid():
    out = bedrock_extract(BEDROCK_REPLY)
    assert out["source"] == "bedrock"
    assert out["confidence"] == 0.93
    assert out["payload"]["rib"] == RIB_FRAUD
    assert out["payload"]["amount"] == 5210
    assert out["label"] == "Received invoice F-9999 — new bank details"


@pytest.mark.parametrize("patch", [
    {"payload": dict(BEDROCK_REPLY["payload"], rib="FR76 0000 1111 2222 3333 4444 555")},
    {"payload": dict(BEDROCK_REPLY["payload"], references=["F-1234"])},
    {"kind": "virement"},
    {"origin": "pirate"},
    {"confidence": 7},
])
def test_bedrock_extraction_invented_values_fall_back(patch):
    out = bedrock_extract(dict(BEDROCK_REPLY, **patch))
    assert out["source"] == "mock"
    assert out["payload"]["rib"] == RIB_FRAUD


# -- API -----------------------------------------------------------------------------


def post_sample(name, content_type, **params):
    params.setdefault("company", "fabricant")
    return client.post("/api/ingest/document", params=params,
                       content=(SAMPLES / name).read_bytes(),
                       headers={"Content-Type": content_type})


def test_ingest_pdf_is_only_a_proposal():
    res = post_sample("facture-rib-modifie.pdf", "application/pdf",
                      received_at="2026-10-10T16:00:00")
    assert res.status_code == 200
    prop = res.json()
    assert prop["status"] == "pending"
    assert prop["source"] == "mock"
    assert prop["record"]["id"] == "m-doc-01"
    assert prop["record"]["ts"] == "2026-10-10T16:00:00"
    ids = {r["id"] for r in client.get("/api/state").json()["records"]}
    assert "m-doc-01" not in ids


def test_confirm_adds_record_and_rules_apply():
    client.post("/api/compromise", json={"company": "fournisseur",
                                         "since": "2026-10-10T14:00:00"})
    prop = post_sample("facture-rib-modifie.pdf", "application/pdf",
                       received_at="2026-10-10T16:00:00").json()
    res = client.post(f"/api/ingest/document/{prop['id']}/confirm")
    assert res.status_code == 200
    rec = next(r for r in res.json()["records"] if r["id"] == "m-doc-01")
    assert rec["origin"] == "fournisseur"
    assert rec["status"] == "quarantined"
    assert rec["taint_path"] == ["m-doc-01"]
    again = client.post(f"/api/ingest/document/{prop['id']}/confirm")
    assert again.status_code == 400
    audit = client.get("/api/audit", params={"company": "fabricant"}).json()["entries"]
    entry = next(e for e in audit if e["event"] == "document_confirmed")
    assert entry["actor"] == "humain"
    assert entry["details"]["record"] == "m-doc-01"
    assert entry["details"]["extraction_source"] == "mock"
    assert client.get("/api/audit/verify").status_code == 200


def test_confirm_before_compromise_stays_ok_with_inputs():
    prop = post_sample("avis-expedition.eml", "message/rfc822",
                       received_at="2026-10-10T15:25:00").json()
    res = client.post(f"/api/ingest/document/{prop['id']}/confirm",
                      json={"inputs": ["m-int-03"]})
    rec = next(r for r in res.json()["records"] if r["id"] == "m-doc-01")
    assert rec["status"] == "ok"
    assert rec["inputs"] == ["m-int-03"]
    bad = post_sample("bon-de-commande.txt", "text/plain").json()
    res = client.post(f"/api/ingest/document/{bad['id']}/confirm", json={"inputs": ["nope"]})
    assert res.status_code == 400


def test_ingest_json_text_and_errors():
    res = client.post("/api/ingest/document", params={"company": "fabricant"},
                      json={"text": (SAMPLES / "bon-de-commande.txt").read_text()})
    assert res.status_code == 200
    assert res.json()["record"]["kind"] == "purchase_order"
    assert client.post("/api/ingest/document", params={"company": "nope"},
                       content=b"Facture").status_code == 404
    assert client.post("/api/ingest/document", params={"company": "fabricant"},
                       content=b"").status_code == 400
    assert client.post("/api/ingest/document/doc-99/confirm").status_code == 404


def test_reset_clears_proposals():
    prop = post_sample("bon-de-commande.txt", "text/plain").json()
    client.post("/api/reset")
    assert client.post(f"/api/ingest/document/{prop['id']}/confirm").status_code == 404


def test_explain_reports_source():
    res = client.get("/api/records/m-pay-01/explain")
    assert res.json()["source"] == "mock"
