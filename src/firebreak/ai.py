"""Explications Firebreak — l'IA explique et propose, elle ne décide jamais.

Le blocage dépend uniquement des règles du moteur (engine.py). Ici :
- `MockExplainer` : gabarits français déterministes (défaut, hors ligne) ;
- `BedrockExplainer` : AWS Bedrock (Converse API), avec repli automatique
  sur le mock en cas d'erreur, de timeout, d'identifiants absents ou de
  réponse invalide (JSON cassé, action hors liste).

Sélection par variables d'environnement : voir `get_explainer`.
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
    "payment": "un paiement",
    "shipment": "une expédition",
    "production_lot": "un lancement de production",
}


class Explainer(Protocol):
    def explain(self, record: Record, path_records: list[Record]) -> str: ...
    def remediation_plan(self, record: Record) -> list[dict]: ...


def ai_mode() -> str:
    return os.environ.get("FIREBREAK_AI", "mock").strip().lower()


def applied_rules(record: Record, path_records: list[Record]) -> list[str]:
    """Règles du moteur qui expliquent le statut du record (texte factuel)."""
    rules: list[str] = []
    if record.verified:
        rules.append("verified : confirmé par une source de confiance, jamais contaminé, "
                     "stoppe la propagation")
    if record.status == "released":
        rules.append("released : débloqué par une remédiation, stoppe la propagation")
    if record.status == "quarantined":
        seed = path_records[0] if path_records else record
        if seed.token is not None and seed.origin != seed.company:
            rules.append(f"seed : « {seed.label} » reçu de {seed.origin}, soit émis dans la "
                         "fenêtre de compromission déclarée, soit signalé par une alerte "
                         "signée valide")
        else:
            rules.append(f"seed : « {seed.label} » émis par {seed.origin} après le début de "
                         "la fenêtre de compromission déclarée")
        if len(path_records) > 1:
            rules.append("propagation : un record est contaminé dès qu'une de ses entrées "
                         "l'est (chemin taint_path)")
        if record.gate:
            rules.append("gate : action irréversible en quarantaine, bloquée jusqu'à "
                         "remédiation")
    if record.status == "ok" and not record.verified:
        rules.append("ok : aucune entrée ne dépend d'une donnée suspecte")
    return rules


class MockExplainer:
    """Explainer déterministe basé sur des gabarits français."""

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
                path = " → ".join(f"« {r.label} »" for r in path_records)
                seed = path_records[0]
                text = (
                    f"« {record.label} » est mis en quarantaine : il dépend, "
                    f"directement ou indirectement, de « {seed.label} » "
                    f"({seed.origin}, {seed.ts.strftime('%H:%M')}), émis dans la "
                    f"fenêtre de compromission déclarée. Chemin de contamination : "
                    f"{path}."
                )
            else:
                text = f"« {record.label} » est mis en quarantaine."
            if record.gate:
                kind = GATE_LABELS.get(record.kind, f"une opération « {record.kind} »")
                amount = record.payload.get("amount")
                impact = f"Impact : blocage d'{kind}"
                impact += f" de {amount} €." if amount else "."
                if record.payload.get("bank_details_change") or record.payload.get("rib"):
                    impact += " Coordonnées bancaires suspectes (RIB modifié)."
                text += " " + impact
            return text
        if record.status == "released":
            return (
                f"« {record.label} » a été libéré après remédiation ; "
                "il n'est plus considéré comme contaminé."
            )
        return (
            f"« {record.label} » ne dépend d'aucune donnée compromise : "
            "l'opération continue normalement."
        )

    def remediation_plan(self, record: Record) -> list[dict]:
        return [
            {
                "action": "revalidate",
                "label": "Revalider la donnée",
                "rationale": (
                    "Comparer le document reçu avec la source d'origine "
                    "(commande, certificat) pour confirmer son authenticité."
                ),
            },
            {
                "action": "human_approval",
                "label": "Validation humaine",
                "rationale": (
                    "Faire arbitrer un responsable : l'opération est critique "
                    "et un blocage prolongé a un coût métier."
                ),
            },
            {
                "action": "trusted_source",
                "label": "Reprendre depuis une source de confiance",
                "rationale": (
                    "Reconstruire l'opération à partir d'une preuve physique "
                    "ou d'un canal vérifié (scan de réception, appel signé)."
                ),
            },
        ]


# -- Bedrock -------------------------------------------------------------------


class BedrockError(Exception):
    """Échec Bedrock (réseau, identifiants, timeout, réponse invalide)."""


def make_bedrock_client() -> Any:
    """Client `bedrock-runtime`, ou BedrockError si boto3 ou les identifiants
    manquent. Les identifiants ne sont jamais lus ni journalisés ici : boto3
    les résout lui-même (variables AWS_*, profil, rôle)."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise BedrockError("boto3 indisponible") from exc
    session = boto3.Session(region_name=os.environ.get("AWS_REGION") or None)
    if session.get_credentials() is None:
        raise BedrockError("identifiants AWS absents")
    if not session.region_name:
        raise BedrockError("région AWS absente (AWS_REGION)")
    config = Config(
        connect_timeout=BEDROCK_TIMEOUT_S,
        read_timeout=BEDROCK_TIMEOUT_S,
        retries={"max_attempts": 1},
    )
    return session.client("bedrock-runtime", config=config)


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_json_reply(text: str) -> dict:
    """JSON objet strict ; tolère seulement un bloc ```json … ``` autour."""
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BedrockError("réponse non JSON") from exc
    if not isinstance(data, dict):
        raise BedrockError("réponse JSON qui n'est pas un objet")
    return data


class BedrockConverser:
    """Appel Converse avec timeout global ; renvoie le JSON de la réponse."""

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
        except Exception as exc:  # profil introuvable, config invalide…
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
        except Exception as exc:  # botocore : ClientError, EndpointConnectionError…
            raise BedrockError(type(exc).__name__) from exc
        try:
            parts = response["output"]["message"]["content"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, TypeError, AttributeError) as exc:
            raise BedrockError("réponse Converse mal formée") from exc
        return parse_json_reply(text)


EXPLAIN_SYSTEM = (
    "Tu es l'assistant d'explication de FIREBREAK, un pare-feu de supply chain. "
    "Le statut d'un record (ok, quarantined, released) est décidé par des règles "
    "déterministes ; tu ne le modifies jamais et tu ne le remets pas en cause. "
    "Tu expliques en français, pour un responsable métier, pourquoi le record a ce "
    "statut, à partir uniquement des données fournies. Puis tu proposes un plan de "
    "reprise ordonné choisi UNIQUEMENT parmi les actions : revalidate, "
    "human_approval, trusted_source. Réponds par un seul objet JSON, sans texte "
    'autour : {"explanation": "...", "remediation_plan": [{"action": "...", '
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
        raise BedrockError("explication absente")
    if not isinstance(plan, list) or not plan:
        raise BedrockError("plan de reprise absent")
    clean = []
    for step in plan:
        if not isinstance(step, dict):
            raise BedrockError("étape de plan invalide")
        action = step.get("action")
        if action not in REMEDIATION_ACTIONS:
            raise BedrockError(f"action hors liste: {action!r}")
        label, rationale = step.get("label"), step.get("rationale")
        if not isinstance(label, str) or not isinstance(rationale, str):
            raise BedrockError("étape de plan incomplète")
        clean.append({"action": action, "label": label.strip(), "rationale": rationale.strip()})
    return {"explanation": explanation.strip(), "remediation_plan": clean}


class BedrockExplainer:
    """Explainer AWS Bedrock ; toute erreur → réponse du MockExplainer."""

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
            log.warning("Bedrock indisponible, repli sur le mock : %s", exc)
            return self.fallback.analyze(record, path_records)
        result["source"] = self.source
        return result

    def explain(self, record: Record, path_records: list[Record]) -> str:
        return self.analyze(record, path_records)["explanation"]

    def remediation_plan(self, record: Record) -> list[dict]:
        path = [record] if record.taint_path else []
        return self.analyze(record, path)["remediation_plan"]


def get_explainer() -> MockExplainer | BedrockExplainer:
    """FIREBREAK_AI=bedrock → BedrockExplainer (repli mock intégré) ; sinon mock."""
    if ai_mode() == "bedrock":
        return BedrockExplainer()
    return MockExplainer()
