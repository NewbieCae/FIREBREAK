"""Firebreak explanations — the AI explains and proposes, it never decides.

Blocking depends only on the engine's rules (engine.py). Here:
- `MockExplainer`: deterministic English templates (default, offline);
- `BedrockExplainer`: AWS Bedrock (Converse API), with automatic fallback
  to the mock on error, timeout, missing credentials or invalid reply
  (broken JSON, action not in the list).

Selected through environment variables: see `get_explainer`.
"""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Literal, Protocol

from .model import Record

log = logging.getLogger("firebreak.ai")

Source = Literal["mock", "bedrock"]

REMEDIATION_ACTIONS = ("revalidate", "human_approval", "trusted_source")
DEFAULT_BEDROCK_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
BEDROCK_TIMEOUT_S = 8.0

GATE_LABELS = {
    "payment": "a payment",
    "shipment": "a shipment",
    "production_lot": "a production launch",
}


class Explainer(Protocol):
    def explain(self, record: Record, path_records: list[Record]) -> str: ...
    def remediation_plan(self, record: Record) -> list[dict]: ...


def ai_mode() -> str:
    return os.environ.get("FIREBREAK_AI", "mock").strip().lower()


def applied_rules(record: Record, path_records: list[Record]) -> list[str]:
    """Engine rules that explain the record's status (factual text)."""
    rules: list[str] = []
    if record.verified:
        rules.append("verified: confirmed by a trusted source, never contaminated, "
                     "stops propagation")
    if record.status == "released":
        rules.append("released: unblocked by a remediation, stops propagation")
    if record.status == "quarantined":
        seed = path_records[0] if path_records else record
        if seed.token is not None and seed.origin != seed.company:
            rules.append(f"seed: \"{seed.label}\" received from {seed.origin}, either issued "
                         "within the declared compromise window or flagged by a valid "
                         "signed alert")
        else:
            rules.append(f"seed: \"{seed.label}\" issued by {seed.origin} after the start of "
                         "the declared compromise window")
        if len(path_records) > 1:
            rules.append("propagation: a record is contaminated as soon as one of its inputs "
                         "is (taint_path)")
        if record.gate:
            rules.append("gate: irreversible action in quarantine, blocked until "
                         "remediation")
    if record.status == "ok" and not record.verified:
        rules.append("ok: no input depends on suspect data")
    return rules


class MockExplainer:
    """Deterministic explainer based on English templates."""

    source: Source = "mock"

    def analyze(self, record: Record, path_records: list[Record]) -> dict:
        return {
            "explanation": self.explain(record, path_records),
            "remediation_plan": self.remediation_plan(record),
            "source": self.source,
        }

    def explain(self, record: Record, path_records: list[Record]) -> str:
        if record.status == "quarantined":
            if path_records:
                path = " → ".join(f"\"{r.label}\"" for r in path_records)
                seed = path_records[0]
                text = (
                    f"\"{record.label}\" is quarantined: it depends, "
                    f"directly or indirectly, on \"{seed.label}\" "
                    f"({seed.origin}, {seed.ts.strftime('%H:%M')}), issued within the "
                    f"declared compromise window. Contamination path: "
                    f"{path}."
                )
            else:
                text = f"\"{record.label}\" is quarantined."
            if record.gate:
                kind = GATE_LABELS.get(record.kind, f"a \"{record.kind}\" operation")
                amount = record.payload.get("amount")
                impact = f"Impact: {kind} is blocked"
                impact += f" ({amount} €)." if amount else "."
                if record.payload.get("bank_details_change") or record.payload.get("rib"):
                    impact += " Suspicious bank details (RIB changed)."
                text += " " + impact
            return text
        if record.status == "released":
            return (
                f"\"{record.label}\" was released after remediation; "
                "it is no longer considered contaminated."
            )
        return (
            f"\"{record.label}\" does not depend on any compromised data: "
            "the operation continues normally."
        )

    def remediation_plan(self, record: Record) -> list[dict]:
        return [
            {
                "action": "revalidate",
                "label": "Revalidate the data",
                "rationale": (
                    "Compare the received document with the original source "
                    "(purchase order, certificate) to confirm it is authentic."
                ),
            },
            {
                "action": "human_approval",
                "label": "Human approval",
                "rationale": (
                    "Have a manager decide: the operation is critical "
                    "and a prolonged block has a business cost."
                ),
            },
            {
                "action": "trusted_source",
                "label": "Restart from a trusted source",
                "rationale": (
                    "Rebuild the operation from physical evidence "
                    "or a verified channel (receipt scan, signed call)."
                ),
            },
        ]


# -- Bedrock -------------------------------------------------------------------


class BedrockError(Exception):
    """Bedrock failure (network, credentials, timeout, invalid reply)."""


def make_bedrock_client() -> Any:
    """`bedrock-runtime` client, or BedrockError if boto3 or the credentials
    are missing. Credentials are never read or logged here: boto3 resolves
    them itself (AWS_* variables, profile, role)."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise BedrockError("boto3 unavailable") from exc
    session = boto3.Session(region_name=os.environ.get("AWS_REGION") or None)
    if session.get_credentials() is None:
        raise BedrockError("AWS credentials missing")
    if not session.region_name:
        raise BedrockError("AWS region missing (AWS_REGION)")
    config = Config(
        connect_timeout=BEDROCK_TIMEOUT_S,
        read_timeout=BEDROCK_TIMEOUT_S,
        retries={"max_attempts": 1},
    )
    return session.client("bedrock-runtime", config=config)


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json_reply(text: str) -> dict:
    """Strict JSON object; only tolerates a surrounding ```json … ``` block."""
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BedrockError("non-JSON reply") from exc
    if not isinstance(data, dict):
        raise BedrockError("JSON reply that is not an object")
    return data


class BedrockConverser:
    """Converse call with an overall timeout; returns the reply's JSON."""

    def __init__(self, client: Any = None, model: str | None = None,
                 timeout: float = BEDROCK_TIMEOUT_S) -> None:
        self._client = client
        self.model = model or os.environ.get("FIREBREAK_BEDROCK_MODEL") or DEFAULT_BEDROCK_MODEL
        self.timeout = timeout
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bedrock")

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = make_bedrock_client()
        return self._client

    def ask_json(self, system: str, user: str, max_tokens: int = 800) -> dict:
        try:
            client = self.client
        except BedrockError:
            raise
        except Exception as exc:  # profile not found, invalid config…
            raise BedrockError(type(exc).__name__) from exc
        future = self._pool.submit(
            client.converse,
            modelId=self.model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        try:
            response = future.result(timeout=self.timeout)
        except FutureTimeout as exc:
            raise BedrockError(f"timeout Bedrock ({self.timeout:g} s)") from exc
        except BedrockError:
            raise
        except Exception as exc:  # botocore: ClientError, EndpointConnectionError…
            raise BedrockError(type(exc).__name__) from exc
        try:
            parts = response["output"]["message"]["content"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, TypeError, AttributeError) as exc:
            raise BedrockError("malformed Converse reply") from exc
        return parse_json_reply(text)


EXPLAIN_SYSTEM = (
    "You are the explanation assistant of FIREBREAK, a supply chain firewall. "
    "A record's status (ok, quarantined, released) is decided by deterministic "
    "rules; you never change it and never question it. "
    "You explain in English, for a business manager, why the record has this "
    "status, using only the data provided. Then you propose an ordered "
    "remediation plan chosen ONLY from the actions: revalidate, "
    "human_approval, trusted_source. Reply with a single JSON object, with no "
    'surrounding text: {"explanation": "...", "remediation_plan": [{"action": "...", '
    '"label": "...", "rationale": "..."}]}'
)


def _record_brief(r: Record) -> dict:
    return {
        "id": r.id, "company": r.company, "origin": r.origin, "kind": r.kind,
        "ts": r.ts.isoformat(), "label": r.label, "gate": r.gate,
        "verified": r.verified, "status": r.status, "payload": r.payload,
    }


def validate_explanation(data: dict) -> dict:
    explanation = data.get("explanation")
    plan = data.get("remediation_plan")
    if not isinstance(explanation, str) or not explanation.strip():
        raise BedrockError("explanation missing")
    if not isinstance(plan, list) or not plan:
        raise BedrockError("remediation plan missing")
    clean = []
    for step in plan:
        if not isinstance(step, dict):
            raise BedrockError("invalid plan step")
        action = step.get("action")
        if action not in REMEDIATION_ACTIONS:
            raise BedrockError(f"action not in the list: {action!r}")
        label, rationale = step.get("label"), step.get("rationale")
        if not isinstance(label, str) or not isinstance(rationale, str):
            raise BedrockError("incomplete plan step")
        clean.append({"action": action, "label": label.strip(), "rationale": rationale.strip()})
    return {"explanation": explanation.strip(), "remediation_plan": clean}


class BedrockExplainer:
    """AWS Bedrock explainer; any error → the MockExplainer's reply."""

    source: Source = "bedrock"

    def __init__(self, converser: BedrockConverser | None = None,
                 fallback: MockExplainer | None = None) -> None:
        self.converser = converser or BedrockConverser()
        self.fallback = fallback or MockExplainer()

    def prompt(self, record: Record, path_records: list[Record]) -> str:
        payload = {
            "record": _record_brief(record),
            "taint_path": [_record_brief(r) for r in path_records],
            "applied_rules": applied_rules(record, path_records),
            "allowed_actions": list(REMEDIATION_ACTIONS),
        }
        return json.dumps(payload, ensure_ascii=False, indent=1)

    def analyze(self, record: Record, path_records: list[Record]) -> dict:
        try:
            data = self.converser.ask_json(EXPLAIN_SYSTEM, self.prompt(record, path_records))
            result = validate_explanation(data)
        except BedrockError as exc:
            log.warning("Bedrock unavailable, falling back to the mock: %s", exc)
            return self.fallback.analyze(record, path_records)
        result["source"] = self.source
        return result

    def explain(self, record: Record, path_records: list[Record]) -> str:
        return self.analyze(record, path_records)["explanation"]

    def remediation_plan(self, record: Record) -> list[dict]:
        path = [record] if record.taint_path else []
        return self.analyze(record, path)["remediation_plan"]


def get_explainer() -> MockExplainer | BedrockExplainer:
    """FIREBREAK_AI=bedrock → BedrockExplainer (built-in mock fallback); otherwise mock."""
    if ai_mode() == "bedrock":
        return BedrockExplainer()
    return MockExplainer()
