import json
import logging
import time

import pytest

from firebreak import ai
from firebreak.ai import (
    BedrockConverser,
    BedrockError,
    BedrockExplainer,
    MockExplainer,
    get_explainer,
    make_bedrock_client,
)
from firebreak.scenario import build_simulation
from firebreak.simulation import REMEDIATION_ACTIONS


class FakeClient:
    """Faux client bedrock-runtime : aucun appel réseau."""

    def __init__(self, reply=None, error=None, delay=0.0):
        self.reply, self.error, self.delay = reply, error, delay
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


def quarantined_payment():
    sim = build_simulation()
    sim.declare_compromise("fournisseur", sim.ledgers["fournisseur"].records["f-asn-X"].ts
                           .replace(hour=14, minute=0))
    record = sim.find_record("m-pay-X")
    return record, sim.path_records(record)


GOOD = {
    "explanation": "Le paiement est bloqué : la facture vient du fournisseur compromis.",
    "remediation_plan": [
        {"action": "revalidate", "label": "Revalider", "rationale": "Appeler le fournisseur."},
        {"action": "human_approval", "label": "Arbitrage", "rationale": "Décision du DAF."},
    ],
}


def bedrock(reply=None, error=None, delay=0.0, timeout=2.0):
    client = FakeClient(reply, error, delay)
    return BedrockExplainer(BedrockConverser(client=client, model="test-model",
                                             timeout=timeout)), client


def test_actions_match_engine():
    assert set(ai.REMEDIATION_ACTIONS) == REMEDIATION_ACTIONS


def test_mock_is_default(monkeypatch):
    monkeypatch.delenv("FIREBREAK_AI", raising=False)
    assert isinstance(get_explainer(), MockExplainer)
    monkeypatch.setenv("FIREBREAK_AI", "bedrock")
    assert isinstance(get_explainer(), BedrockExplainer)


def test_bedrock_valid_reply():
    record, path = quarantined_payment()
    explainer, client = bedrock(GOOD)
    out = explainer.analyze(record, path)
    assert out["source"] == "bedrock"
    assert out["explanation"] == GOOD["explanation"]
    assert [s["action"] for s in out["remediation_plan"]] == ["revalidate", "human_approval"]
    call = client.calls[0]
    assert call["modelId"] == "test-model"
    assert call["inferenceConfig"]["temperature"] == 0


def test_prompt_contains_only_record_path_and_rules():
    record, path = quarantined_payment()
    explainer, client = bedrock(GOOD)
    explainer.analyze(record, path)
    prompt = json.loads(client.calls[0]["messages"][0]["content"][0]["text"])
    assert set(prompt) == {"record", "taint_path", "applied_rules", "allowed_actions"}
    assert prompt["record"]["id"] == "m-pay-X"
    assert [r["id"] for r in prompt["taint_path"]] == record.taint_path
    assert any(rule.startswith("gate") for rule in prompt["applied_rules"])
    assert "token" not in prompt["record"]


def test_fenced_json_is_accepted():
    record, path = quarantined_payment()
    explainer, _ = bedrock("```json\n" + json.dumps(GOOD) + "\n```")
    assert explainer.analyze(record, path)["source"] == "bedrock"


@pytest.mark.parametrize("reply", [
    "Voici mon analyse : le paiement est suspect.",
    "{pas du json",
    json.dumps(["liste"]),
    json.dumps({"explanation": "", "remediation_plan": GOOD["remediation_plan"]}),
    json.dumps({"explanation": "ok", "remediation_plan": []}),
])
def test_invalid_reply_falls_back_to_mock(reply):
    record, path = quarantined_payment()
    explainer, _ = bedrock(reply)
    out = explainer.analyze(record, path)
    assert out == MockExplainer().analyze(record, path)
    assert out["source"] == "mock"


def test_action_outside_list_is_rejected():
    record, path = quarantined_payment()
    bad = dict(GOOD, remediation_plan=[
        {"action": "release_now", "label": "Débloquer", "rationale": "Le client attend."}])
    explainer, _ = bedrock(bad)
    out = explainer.analyze(record, path)
    assert out["source"] == "mock"
    assert {s["action"] for s in out["remediation_plan"]} <= REMEDIATION_ACTIONS


def test_client_error_falls_back_to_mock():
    record, path = quarantined_payment()
    explainer, _ = bedrock(error=ConnectionError("réseau coupé"))
    assert explainer.analyze(record, path)["source"] == "mock"


def test_timeout_falls_back_to_mock():
    record, path = quarantined_payment()
    explainer, _ = bedrock(GOOD, delay=0.5, timeout=0.05)
    start = time.monotonic()
    assert explainer.analyze(record, path)["source"] == "mock"
    assert time.monotonic() - start < 0.4
    assert ai.BEDROCK_TIMEOUT_S == 8.0


def test_missing_credentials_falls_back_to_mock(monkeypatch, tmp_path):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AWS_PROFILE", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
                "AWS_CONTAINER_CREDENTIALS_FULL_URI", "AWS_WEB_IDENTITY_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_REGION", "eu-west-3")
    with pytest.raises(BedrockError, match="identifiants"):
        make_bedrock_client()
    record, path = quarantined_payment()
    assert BedrockExplainer().analyze(record, path)["source"] == "mock"


def test_secrets_never_logged(caplog):
    record, path = quarantined_payment()
    explainer, _ = bedrock(error=RuntimeError("AKIAFAKESECRET1234 refusé"))
    with caplog.at_level(logging.WARNING, logger="firebreak.ai"):
        explainer.analyze(record, path)
    assert "repli sur le mock" in caplog.text
    assert "AKIAFAKESECRET1234" not in caplog.text


def test_protocol_methods_on_bedrock():
    record, path = quarantined_payment()
    explainer, _ = bedrock(GOOD)
    assert explainer.explain(record, path) == GOOD["explanation"]
    assert explainer.remediation_plan(record)[0]["action"] == "revalidate"
