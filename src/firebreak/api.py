"""API Firebreak — contrat pour le tableau de bord.

L'état est en mémoire : une instance globale de Simulation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .ai import MockExplainer
from .scenario import build_simulation
from .simulation import REMEDIATION_ACTIONS

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(
    title="Firebreak",
    description="Confinement ciblé des compromissions dans les supply chains.",
)

sim = build_simulation()
explainer = MockExplainer()


class CompromiseBody(BaseModel):
    company: str
    since: datetime


class RemediateBody(BaseModel):
    action: str


def _serialize_record(r) -> dict:
    return {
        "id": r.id, "company": r.company, "origin": r.origin, "kind": r.kind,
        "ts": r.ts.isoformat(), "label": r.label, "inputs": r.inputs,
        "gate": r.gate, "verified": r.verified, "payload": r.payload,
        "token": r.token, "status": r.status, "taint_path": r.taint_path,
    }


@app.get("/api/state", summary="État complet de la simulation")
def get_state() -> dict:
    return sim.state()


@app.post("/api/compromise", summary="Déclarer une entreprise compromise")
def post_compromise(body: CompromiseBody) -> dict:
    if body.company not in sim.ledgers:
        raise HTTPException(404, f"entreprise inconnue: {body.company}")
    sim.declare_compromise(body.company, body.since)
    return sim.state()


@app.get("/api/records/{record_id}/explain", summary="Explication d'un record")
def get_explain(record_id: str) -> dict:
    record = sim.find_record(record_id)
    if record is None:
        raise HTTPException(404, f"record inconnu: {record_id}")
    path = sim.path_records(record)
    return {
        "record": _serialize_record(record),
        "path": [_serialize_record(r) for r in path],
        "explanation": explainer.explain(record, path),
        "remediation_plan": explainer.remediation_plan(record),
    }


@app.post("/api/records/{record_id}/remediate", summary="Remédier à un record")
def post_remediate(record_id: str, body: RemediateBody) -> dict:
    if sim.find_record(record_id) is None:
        raise HTTPException(404, f"record inconnu: {record_id}")
    if body.action not in REMEDIATION_ACTIONS:
        raise HTTPException(400, f"action invalide: {body.action}")
    try:
        sim.remediate(record_id, body.action)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return sim.state()


@app.post("/api/reset", summary="Réinitialiser le scénario")
def post_reset() -> dict:
    global sim
    sim = build_simulation()
    return sim.state()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
