"""API Firebreak — contrat pour le tableau de bord.

L'état est en mémoire : une instance globale de Simulation, protégée par
un verrou (les endpoints FastAPI synchrones tournent dans un pool de threads).
Contrat documenté dans docs/api.md ; schéma OpenAPI sur /docs.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .ai import get_explainer
from .ingest.documents import DocumentError, Party, document_text, get_extractor
from .ingest.epcis import EpcisError, parse_epcis
from .model import Record
from .scenario import DEFAULT_SCENARIO, SCENARIOS, build_simulation, scenarios_meta
from .schemas import (
    AuditOut,
    AuditVerifyOut,
    EpcisImportOut,
    ErrorOut,
    ExplainOut,
    ProposalOut,
    ScenarioId,
    ScenarioOut,
    StateOut,
)
from .simulation import (
    REMEDIATION_ACTIONS,
    SCENARIO_TZ,
    serialize_record,
    to_scenario_time,
)

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
explainer = get_explainer()
extractor = get_extractor()
proposals: dict[str, dict] = {}
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


class WithdrawBody(BaseModel):
    company: str = Field(examples=["fournisseur"])


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


@app.post("/api/compromise/withdraw", summary="Retirer une déclaration (fausse alerte)",
          response_model=StateOut, responses=ERRORS)
def post_withdraw(body: WithdrawBody) -> dict:
    with _lock:
        if body.company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {body.company}")
        try:
            sim.withdraw_compromise(body.company)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return sim.state()


@app.get("/api/audit", summary="Journal d'audit d'une entreprise",
         response_model=AuditOut, responses=ERRORS)
def get_audit(company: str = Query(examples=["fabricant"])) -> dict:
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {company}")
        audit = sim.ledgers[company].audit
        return {"company": company, "head": audit.head, "entries": audit.entries()}


@app.get("/api/audit/verify", summary="Vérifier la chaîne de hash des journaux",
         response_model=AuditVerifyOut, responses=ERRORS)
def get_audit_verify(company: str | None = None) -> dict:
    with _lock:
        if company is not None and company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {company}")
        return sim.audit_verify(company)


@app.get("/api/records/{record_id}/explain", summary="Explication d'un record",
         response_model=ExplainOut, responses=ERRORS)
def get_explain(record_id: str) -> dict:
    with _lock:
        record = sim.find_record(record_id)
        if record is None:
            raise HTTPException(404, f"record inconnu: {record_id}")
        record, path = copy.deepcopy((record, sim.path_records(record)))
    analysis = explainer.analyze(record, path)  # hors verrou : Bedrock peut prendre 8 s
    return {
        "record": serialize_record(record),
        "path": [serialize_record(r) for r in path],
        **analysis,
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


class ConfirmBody(BaseModel):
    origin: str | None = Field(
        default=None, description="Corrige l'émetteur détecté (id d'entreprise).")
    inputs: list[str] | None = Field(
        default=None, description="Records du même registre dont ce document dépend.")


def _known_ribs(company: str) -> dict[str, set[str]]:
    """RIB déjà vus dans le registre, par émetteur, hors données suspectes."""
    ribs: dict[str, set[str]] = {}
    for r in sim.ledgers[company].records.values():
        rib = r.payload.get("rib")
        if rib and r.status != "quarantined" and not r.payload.get("bank_details_change"):
            ribs.setdefault(r.origin, set()).add(rib)
    return ribs


def _id_prefix(company: str) -> str:
    """Même préfixe que les records du registre (ex. « m » pour fabricant)."""
    first = next(iter(sim.ledgers[company].records), "")
    return first.split("-", 1)[0] if "-" in first else company


def _next_record_id(company: str) -> str:
    prefix = _id_prefix(company)
    taken = {p["record"]["id"] for p in proposals.values()}
    n = 1
    while sim.find_record(f"{prefix}-doc-{n:02d}") is not None or \
            f"{prefix}-doc-{n:02d}" in taken:
        n += 1
    return f"{prefix}-doc-{n:02d}"


@app.post("/api/ingest/document", summary="Lire un document fournisseur",
          response_model=ProposalOut, responses=ERRORS,
          openapi_extra={"requestBody": {"content": {
              "application/pdf": {"schema": {"type": "string", "format": "binary"}},
              "text/plain": {"schema": {"type": "string"}},
              "message/rfc822": {"schema": {"type": "string"}},
              "application/json": {"schema": {"type": "object", "properties": {
                  "text": {"type": "string"}}, "required": ["text"]}},
          }}})
async def post_ingest_document(request: Request, company: str,
                               received_at: datetime | None = None) -> dict:
    """Corps brut : PDF, mail (.eml) ou texte ; ou JSON `{"text": "..."}`.
    Renvoie une proposition : rien n'est ajouté au registre avant confirmation."""
    data = await request.body()
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            text_field = (await request.json()).get("text")
        except (ValueError, AttributeError):
            text_field = None
        if not isinstance(text_field, str):
            raise HTTPException(422, "requête invalide — text: chaîne attendue")
        data = text_field.encode()
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {company}")
        parties = [Party(c.id, c.name) for c in sim.companies]
        known = _known_ribs(company)
    try:
        text = await run_in_threadpool(document_text, data)
    except DocumentError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = await run_in_threadpool(extractor.extract, text, company, parties, known)
    ts = to_scenario_time(received_at) if received_at else \
        datetime.now(SCENARIO_TZ).replace(tzinfo=None, microsecond=0)
    with _lock:
        pid = f"doc-{len(proposals) + 1:02d}"
        proposal = {
            "id": pid,
            "status": "pending",
            "source": result["source"],
            "confidence": result["confidence"],
            "missing": result["missing"],
            "record": {
                "id": _next_record_id(company),
                "company": company,
                "origin": result["origin"],
                "kind": result["kind"],
                "ts": ts.isoformat(),
                "label": result["label"],
                "inputs": [],
                "gate": False,
                "payload": result["payload"],
            },
        }
        proposals[pid] = proposal
        return proposal


@app.post("/api/ingest/document/{proposal_id}/confirm",
          summary="Confirmer un document lu : ajout au registre",
          response_model=StateOut, responses=ERRORS)
def post_confirm_document(proposal_id: str, body: ConfirmBody | None = None) -> dict:
    body = body or ConfirmBody()
    with _lock:
        proposal = proposals.get(proposal_id)
        if proposal is None:
            raise HTTPException(404, f"proposition inconnue: {proposal_id}")
        if proposal["status"] != "pending":
            raise HTTPException(400, "proposition déjà confirmée")
        rec = proposal["record"]
        ledger = sim.ledgers[rec["company"]]
        origin = body.origin or rec["origin"]
        if origin is None:
            raise HTTPException(400, "émetteur non reconnu : préciser origin")
        if origin not in sim.ledgers:
            raise HTTPException(400, f"entreprise inconnue: {origin}")
        if rec["kind"] is None:
            raise HTTPException(400, "type de document non reconnu")
        inputs = body.inputs if body.inputs is not None else rec["inputs"]
        unknown = [i for i in inputs if i not in ledger.records]
        if unknown:
            raise HTTPException(400, f"inputs inconnus dans {rec['company']}: "
                                     + ", ".join(unknown))
        ledger.add(Record(
            id=rec["id"], company=rec["company"], origin=origin, kind=rec["kind"],
            ts=datetime.fromisoformat(rec["ts"]), label=rec["label"], inputs=list(inputs),
            gate=False, payload=copy.deepcopy(rec["payload"]),
        ))
        rec["origin"], rec["inputs"] = origin, list(inputs)
        proposal["status"] = "confirmed"
        ledger.audit.append(sim.clock, "document_confirmed", "humain", {
            "record": rec["id"],
            "proposal": proposal_id,
            "origin": origin,
            "kind": rec["kind"],
            "inputs": list(inputs),
            "extraction_source": proposal["source"],
            "confidence": proposal["confidence"],
        })
        sim.run()  # le record passe par les mêmes règles que les autres
        return sim.state()


@app.post("/api/ingest/epcis", summary="Importer un document GS1 EPCIS 2.0",
          response_model=EpcisImportOut, responses=ERRORS)
def post_ingest_epcis(company: str, document: dict = Body(
        description="Document EPCIS 2.0 JSON / JSON-LD (type: EPCISDocument).")) -> dict:
    """Données structurées : les records sont ajoutés directement (pas de
    confirmation), puis passent par les mêmes règles que les autres."""
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"entreprise inconnue: {company}")
        ledger = sim.ledgers[company]
        taken = {rid for led in sim.ledgers.values() for rid in led.records}
        try:
            result = parse_epcis(document, company, sim.companies, ledger.records,
                                 _id_prefix(company), taken)
        except EpcisError as exc:
            raise HTTPException(400, str(exc)) from exc
        for record in result.records:
            ledger.add(record)
        ledger.audit.append(sim.clock, "epcis_import", "humain", {
            "records": [r.id for r in result.records],
            "events": result.events,
            "ignored": len(result.ignored),
        })
        sim.run()
        return {
            "events": result.events,
            "imported": [serialize_record(r) for r in result.records],
            "ignored": result.ignored,
            "state": sim.state(),
        }


class ResetBody(BaseModel):
    scenario: ScenarioId = Field(default=DEFAULT_SCENARIO, examples=["cert"])


@app.get("/api/scenarios", summary="Scénarios disponibles",
         response_model=list[ScenarioOut])
def get_scenarios() -> list[dict]:
    return scenarios_meta()


@app.post("/api/reset", summary="Réinitialiser (choix du scénario)",
          response_model=StateOut, responses=ERRORS)
def post_reset(body: ResetBody | None = None) -> dict:
    global sim
    scenario = (body or ResetBody()).scenario
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"scénario inconnu: {scenario}")
    with _lock:
        sim = build_simulation(scenario)
        proposals.clear()
        return sim.state()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
