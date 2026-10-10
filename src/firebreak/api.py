"""API Firebreak — contrat pour le tableau de bord.

L'état est en mémoire : une instance globale de Simulation, protégée par
un verrou (les endpoints FastAPI synchrones tournent dans un pool de threads).
Contrat documenté dans docs/api.md ; schéma OpenAPI sur /docs.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .ai import MockExplainer
from .scenario import build_simulation
from .schemas import ErrorOut, ExplainOut, StateOut
from .simulation import REMEDIATION_ACTIONS, serialize_record, to_scenario_time

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(
    title="Firebreak",
    description="Confinement ciblé des compromissions dans les supply chains.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = build_simulation()
explainer = MockExplainer()
_lock = threading.Lock()

ERRORS = {
    400: {"model": ErrorOut, "description": "Requête refusée"},
    404: {"model": ErrorOut, "description": "Ressource inconnue"},
    422: {"model": ErrorOut, "description": "Corps de requête invalide"},
}


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return JSONResponse(
        {"detail": "requête invalide — " + "; ".join(parts)}, status_code=422
    )


class CompromiseBody(BaseModel):
    company: str = Field(examples=["fournisseur"])
    since: datetime = Field(
        description="Début de la fenêtre de compromission. Sans fuseau : heure de Paris.",
        examples=["2026-10-10T14:00:00"],
    )


class RemediateBody(BaseModel):
    action: str = Field(
        description="Action de reprise.",
        json_schema_extra={"enum": sorted(REMEDIATION_ACTIONS)},
        examples=["human_approval"],
    )


@app.get("/api/state", summary="État complet de la simulation", response_model=StateOut)
def get_state() -> dict:
    with _lock:
        return sim.state()


@app.post("/api/compromise", summary="Déclarer une entreprise compromise",
          response_model=StateOut, responses=ERRORS)
def post_compromise(body: CompromiseBody) -> dict:
    with _lock:
        if body.company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {body.company}")
        sim.declare_compromise(body.company, to_scenario_time(body.since))
        return sim.state()


@app.get("/api/records/{record_id}/explain", summary="Explication d'un record",
         response_model=ExplainOut, responses=ERRORS)
def get_explain(record_id: str) -> dict:
    with _lock:
        record = sim.find_record(record_id)
        if record is None:
            raise HTTPException(404, f"record inconnu: {record_id}")
        path = sim.path_records(record)
        return {
            "record": serialize_record(record),
            "path": [serialize_record(r) for r in path],
            "explanation": explainer.explain(record, path),
            "remediation_plan": explainer.remediation_plan(record),
        }


@app.post("/api/records/{record_id}/remediate", summary="Remédier à un record",
          response_model=StateOut, responses=ERRORS)
def post_remediate(record_id: str, body: RemediateBody) -> dict:
    with _lock:
        if sim.find_record(record_id) is None:
            raise HTTPException(404, f"record inconnu: {record_id}")
        if body.action not in REMEDIATION_ACTIONS:
            raise HTTPException(400, f"action invalide: {body.action}")
        try:
            sim.remediate(record_id, body.action)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return sim.state()


@app.post("/api/reset", summary="Réinitialiser le scénario", response_model=StateOut)
def post_reset() -> dict:
    global sim
    with _lock:
        sim = build_simulation()
        return sim.state()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
