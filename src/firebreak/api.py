"""Firebreak API — the contract for the dashboard.

State lives in memory: one global Simulation instance, guarded by a lock
(synchronous FastAPI endpoints run in a thread pool).
Contract documented in docs/api.md; OpenAPI schema at /docs.
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .ai import MockExplainer, get_explainer
from .chain.anchoring import Anchorer
from .chain.client import get_chain_client
from .chain.config import load_chain_config
from .chain.tamper import rewrite_journal
from .compare import compare as sim_compare
from .demo import DEMO_CAPTIONS, DEMO_MODE, DEMO_REPLAY_SPEED, DEMO_SCENARIO, demo_caption
from .ingest.documents import DocumentError, Party, document_text, get_extractor
from .ingest.epcis import EpcisError, parse_epcis
from .model import Record
from .scenario import DEFAULT_SCENARIO, SCENARIOS, build_simulation, scenarios_meta
from .schemas import (
    AnchorOut,
    AuditOut,
    ChainStatusOut,
    RewriteBody,
    AuditVerifyOut,
    EpcisImportOut,
    ErrorOut,
    ExplainOut,
    ProposalOut,
    ScenarioId,
    ScenarioOut,
    StateOut,
    CompareOut,
    TimelineOut,
)
from .simulation import (
    REMEDIATION_ACTIONS,
    SCENARIO_TZ,
    serialize_record,
    to_scenario_time,
)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
SAMPLES_DIR = Path(__file__).resolve().parents[2] / "assets" / "samples"

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app = FastAPI(
    title="Firebreak",
    description="Targeted containment of compromises in supply chains.",
    version="1.4.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Demo mode: fixed scenario, AI forced to mock (no network dependency),
# paced SSE replay for the stage. FIREBREAK_DEMO=1.
sim = build_simulation(DEMO_SCENARIO if DEMO_MODE else DEFAULT_SCENARIO)
explainer = MockExplainer() if DEMO_MODE else get_explainer()
demo_index = 0
chain = get_chain_client(load_chain_config())
anchorer = Anchorer(chain)
anchorer.on_new_simulation(sim)
extractor = get_extractor()
proposals: dict[str, dict] = {}
_lock = threading.Lock()

ERRORS = {
    400: {"model": ErrorOut, "description": "Request refused"},
    404: {"model": ErrorOut, "description": "Unknown resource"},
    422: {"model": ErrorOut, "description": "Invalid request body"},
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
        {"detail": "invalid request — " + "; ".join(parts)}, status_code=422
    )


class CompromiseBody(BaseModel):
    company: str = Field(examples=["fournisseur"])
    since: datetime = Field(
        description="Start of the compromise window. Without a time zone: Paris time.",
        examples=["2026-10-10T14:00:00"],
    )


class WithdrawBody(BaseModel):
    company: str = Field(examples=["fournisseur"])


class LotSuspectBody(BaseModel):
    company: str = Field(examples=["fabricant"])
    lot: str = Field(description="Lot number or record id.", examples=["COIL-104"])
    reason: str = Field(default="", examples=["Casting defect"])


class LotWithdrawBody(BaseModel):
    company: str = Field(examples=["fabricant"])
    lot: str = Field(examples=["COIL-104"])


class ReportBody(BaseModel):
    company: str = Field(description="Reporting company.", examples=["client"])
    ref: str = Field(description="Affected lot or record id.", examples=["c-gr-03"])
    reason: str = Field(default="", examples=["Broke on site"])


class ReportDecisionBody(BaseModel):
    company: str = Field(description="Recipient of the report.", examples=["fournisseur"])
    decision: str = Field(description="\"confirm\" or \"reject\".", examples=["confirm"])


class InboundScreenBody(BaseModel):
    company: str = Field(description="Receiving company.", examples=["fabricant"])
    receipt_id: str | None = Field(
        default=None,
        description="Receipt to check; if omitted: all of the day's receipts.",
        examples=["m-gr-X"])


class InboundDecisionBody(BaseModel):
    company: str = Field(examples=["fabricant"])
    decision: str = Field(description="\"accept\" or \"reject\".", examples=["reject"])
    reason: str = Field(default="", examples=["Unknown purchase order, certificate out of sequence"])


class RemediateBody(BaseModel):
    action: str = Field(
        description="Remediation action.",
        json_schema_extra={"enum": sorted(REMEDIATION_ACTIONS)},
        examples=["human_approval"],
    )


def _chain_on() -> bool:
    return chain.status()["mode"] != "off"


def _with_onchain(result: dict) -> dict:
    """Add the Avalanche anchoring to the audit verification (called under `_lock`)."""
    if not _chain_on():
        return result
    checks = anchorer.verify_onchain(sim)
    for j in result["journals"]:
        j["onchain"] = checks.get(j["company"])
    anchored = [j["onchain"] for j in result["journals"] if j.get("onchain")]
    if any(a.get("unreadable") for a in anchored):
        result["onchain_ok"] = None
    else:
        result["onchain_ok"] = all(a["matches"] for a in anchored) if anchored else None
    return result


@app.get("/api/chain/status", summary="Avalanche layer status",
         response_model=ChainStatusOut)
def get_chain_status() -> dict:
    return {**chain.status(), "run_id": anchorer.run_id.hex()}


@app.get("/api/chain/anchors", summary="Avalanche anchors",
         response_model=list[AnchorOut])
def get_chain_anchors(kind: str | None = None, company: str | None = None) -> list[dict]:
    records = [a.to_dict() for a in chain.anchors()
               if (kind is None or a.kind == kind)
               and (company is None or a.company == company)]
    return sorted(records, key=lambda r: r["created_at"])


@app.post("/api/chain/anchor", summary="Anchor the journal heads now",
          response_model=list[AnchorOut], responses={409: ERRORS[400]})
def post_chain_anchor() -> list[dict]:
    if not _chain_on():
        raise HTTPException(409, "chain disabled (FIREBREAK_CHAIN=off)")
    with _lock:
        ids = {r.id for r in anchorer.anchor_all(sim)}
    chain.flush(5.0)
    return [a.to_dict() for a in chain.anchors() if a.id in ids]


@app.post("/api/demo/rewrite", summary="Demo: rewrite a journal and recompute the hashes",
          responses=ERRORS)
def post_demo_rewrite(body: RewriteBody) -> dict:
    if not DEMO_MODE:
        raise HTTPException(404, "Not Found")
    with _lock:
        if body.company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {body.company}")
        try:
            index = rewrite_journal(sim, body.company, body.drop_event)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"company": body.company, "dropped_index": index,
                "verify": _with_onchain(sim.audit_verify())}


@app.get("/api/state", summary="Full simulation state", response_model=StateOut)
def get_state() -> dict:
    with _lock:
        return sim.state()


@app.post("/api/compromise", summary="Declare a company compromised",
          response_model=StateOut, responses=ERRORS)
def post_compromise(body: CompromiseBody) -> dict:
    with _lock:
        if body.company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {body.company}")
        sim.declare_compromise(body.company, to_scenario_time(body.since))
        anchorer.after_action(sim, "compromise")
        return sim.state()


@app.post("/api/compromise/withdraw", summary="Withdraw a declaration (false alarm)",
          response_model=StateOut, responses=ERRORS)
def post_withdraw(body: WithdrawBody) -> dict:
    with _lock:
        if body.company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {body.company}")
        try:
            sim.withdraw_compromise(body.company)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        anchorer.after_action(sim, "withdraw")
        return sim.state()


def _quality_call(company: str, fn, *args):
    if company not in sim.ledgers:
        raise HTTPException(404, f"unknown company: {company}")
    try:
        return fn(company, *args)
    except KeyError as exc:
        raise HTTPException(404, f"unknown: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/lots/suspect", summary="Declare a lot suspect (without blacklisting the supplier)",
          response_model=StateOut, responses=ERRORS)
def post_lot_suspect(body: LotSuspectBody) -> dict:
    with _lock:
        _quality_call(body.company, sim.declare_lot_suspect, body.lot, body.reason)
        anchorer.after_action(sim, "lot_suspect")
        return sim.state()


@app.post("/api/lots/suspect/withdraw", summary="Lift the suspicion on a lot",
          response_model=StateOut, responses=ERRORS)
def post_lot_withdraw(body: LotWithdrawBody) -> dict:
    with _lock:
        _quality_call(body.company, sim.withdraw_lot_suspect, body.lot)
        anchorer.after_action(sim, "lot_suspect_withdrawn")
        return sim.state()


@app.get("/api/recall", summary="Recall analysis: possible causes of a product defect",
         responses=ERRORS)
def get_recall(company: str = Query(examples=["fabricant"]),
               ref: str = Query(examples=["LOT-503"])) -> dict:
    with _lock:
        return _quality_call(company, sim.recall_analysis, ref)


@app.post("/api/reports", summary="Report a quality defect upstream",
          responses=ERRORS)
def post_report(body: ReportBody) -> list[dict]:
    with _lock:
        out = _quality_call(body.company, sim.report_upstream, body.ref, body.reason)
        anchorer.after_action(sim, "quality_report")
        return out


@app.get("/api/reports", summary="Quality reports sent and received", responses=ERRORS)
def get_reports(company: str | None = None) -> list[dict]:
    with _lock:
        if company is not None and company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {company}")
        return sim.reports(company)


@app.post("/api/reports/{report_id}/decision", summary="Confirm or reject a received report",
          responses=ERRORS)
def post_report_decision(report_id: str, body: ReportDecisionBody) -> dict:
    with _lock:
        out = _quality_call(body.company, sim.decide_report, report_id, body.decision)
        anchorer.after_action(sim, "quality_report_decision")
        return out


@app.get("/api/inbound/{receipt_id}/check",
         summary="Trust score of a receipt (read-only)", responses=ERRORS)
def get_inbound_check(receipt_id: str,
                      company: str = Query(examples=["fabricant"])) -> dict:
    with _lock:
        return _quality_call(company, sim.inbound_check, receipt_id)


@app.post("/api/inbound/screen",
          summary="Check receipts and put doubtful lots on hold",
          responses=ERRORS)
def post_inbound_screen(body: InboundScreenBody) -> list[dict]:
    with _lock:
        if body.receipt_id is None:
            out = _quality_call(body.company, sim.inbound_screen_all)
        else:
            out = [_quality_call(body.company, sim.inbound_screen, body.receipt_id)]
        anchorer.after_action(sim, "inbound_screen")
        return out


@app.post("/api/inbound/{receipt_id}/decision",
          summary="Accept or reject a receipt on hold", responses=ERRORS)
def post_inbound_decision(receipt_id: str, body: InboundDecisionBody) -> dict:
    with _lock:
        out = _quality_call(body.company, sim.inbound_decide, receipt_id,
                            body.decision, body.reason)
        anchorer.after_action(sim, "inbound_decision")
        return out


@app.get("/api/audit", summary="Audit journal of a company",
         response_model=AuditOut, responses=ERRORS)
def get_audit(company: str = Query(examples=["fabricant"])) -> dict:
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {company}")
        audit = sim.ledgers[company].audit
        return {"company": company, "head": audit.head, "entries": audit.entries()}


@app.get("/api/audit/verify", summary="Verify the journals' hash chain",
         response_model=AuditVerifyOut, responses=ERRORS)
def get_audit_verify(company: str | None = None) -> dict:
    with _lock:
        if company is not None and company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {company}")
        return _with_onchain(sim.audit_verify(company))


@app.get("/api/records/{record_id}/explain", summary="Explain a record",
         response_model=ExplainOut, responses=ERRORS)
def get_explain(record_id: str) -> dict:
    with _lock:
        record = sim.find_record(record_id)
        if record is None:
            raise HTTPException(404, f"unknown record: {record_id}")
        record, path = copy.deepcopy((record, sim.path_records(record)))
    analysis = explainer.analyze(record, path)  # outside the lock: Bedrock can take 8 s
    return {
        "record": serialize_record(record),
        "path": [serialize_record(r) for r in path],
        **analysis,
    }


@app.post("/api/records/{record_id}/remediate", summary="Remediate a record",
          response_model=StateOut, responses=ERRORS)
def post_remediate(record_id: str, body: RemediateBody) -> dict:
    with _lock:
        if sim.find_record(record_id) is None:
            raise HTTPException(404, f"unknown record: {record_id}")
        if body.action not in REMEDIATION_ACTIONS:
            raise HTTPException(400, f"invalid action: {body.action}")
        try:
            sim.remediate(record_id, body.action)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        anchorer.after_action(sim, "remediate")
        return sim.state()


class ConfirmBody(BaseModel):
    origin: str | None = Field(
        default=None, description="Corrects the detected issuer (company id).")
    inputs: list[str] | None = Field(
        default=None, description="Records of the same ledger this document depends on.")


def _known_ribs(company: str) -> dict[str, set[str]]:
    """Bank details (RIB) already seen in the ledger, by issuer, excluding suspect data."""
    ribs: dict[str, set[str]] = {}
    for r in sim.ledgers[company].records.values():
        rib = r.payload.get("rib")
        if rib and r.status != "quarantined" and not r.payload.get("bank_details_change"):
            ribs.setdefault(r.origin, set()).add(rib)
    return ribs


def _id_prefix(company: str) -> str:
    """Same prefix as the ledger's records (e.g. "m" for fabricant)."""
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


@app.post("/api/ingest/document", summary="Read a supplier document",
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
    """Raw body: PDF, email (.eml) or text; or JSON `{"text": "..."}`.
    Returns a proposal: nothing is added to the ledger before confirmation."""
    data = await request.body()
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            text_field = (await request.json()).get("text")
        except (ValueError, AttributeError):
            text_field = None
        if not isinstance(text_field, str):
            raise HTTPException(422, "invalid request — text: string expected")
        data = text_field.encode()
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {company}")
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
          summary="Confirm a read document: add it to the ledger",
          response_model=StateOut, responses=ERRORS)
def post_confirm_document(proposal_id: str, body: ConfirmBody | None = None) -> dict:
    body = body or ConfirmBody()
    with _lock:
        proposal = proposals.get(proposal_id)
        if proposal is None:
            raise HTTPException(404, f"unknown proposal: {proposal_id}")
        if proposal["status"] != "pending":
            raise HTTPException(400, "proposal already confirmed")
        rec = proposal["record"]
        ledger = sim.ledgers[rec["company"]]
        origin = body.origin or rec["origin"]
        if origin is None:
            raise HTTPException(400, "issuer not recognized: specify origin")
        if origin not in sim.ledgers:
            raise HTTPException(400, f"unknown company: {origin}")
        if rec["kind"] is None:
            raise HTTPException(400, "document type not recognized")
        inputs = body.inputs if body.inputs is not None else rec["inputs"]
        unknown = [i for i in inputs if i not in ledger.records]
        if unknown:
            raise HTTPException(400, f"unknown inputs in {rec['company']}: "
                                     + ", ".join(unknown))
        ledger.add(Record(
            id=rec["id"], company=rec["company"], origin=origin, kind=rec["kind"],
            ts=datetime.fromisoformat(rec["ts"]), label=rec["label"], inputs=list(inputs),
            gate=False, payload=copy.deepcopy(rec["payload"]),
        ))
        rec["origin"], rec["inputs"] = origin, list(inputs)
        proposal["status"] = "confirmed"
        marks = sim.audit_marks()
        ledger.audit.append(sim.clock, "document_confirmed", "humain", {
            "record": rec["id"],
            "proposal": proposal_id,
            "origin": origin,
            "kind": rec["kind"],
            "inputs": list(inputs),
            "extraction_source": proposal["source"],
            "confidence": proposal["confidence"],
        })
        sim.run()  # the record goes through the same rules as the others
        sim.timeline = sim.collect_timeline(marks)
        anchorer.after_action(sim, "document")
        return sim.state()


@app.post("/api/ingest/epcis", summary="Import a GS1 EPCIS 2.0 document",
          response_model=EpcisImportOut, responses=ERRORS)
def post_ingest_epcis(company: str, document: dict = Body(
        description="EPCIS 2.0 JSON / JSON-LD document (type: EPCISDocument).")) -> dict:
    """Structured data: records are added directly (no confirmation),
    then go through the same rules as the others."""
    with _lock:
        if company not in sim.ledgers:
            raise HTTPException(404, f"unknown company: {company}")
        ledger = sim.ledgers[company]
        taken = {rid for led in sim.ledgers.values() for rid in led.records}
        try:
            result = parse_epcis(document, company, sim.companies, ledger.records,
                                 _id_prefix(company), taken)
        except EpcisError as exc:
            raise HTTPException(400, str(exc)) from exc
        for record in result.records:
            ledger.add(record)
        marks = sim.audit_marks()
        ledger.audit.append(sim.clock, "epcis_import", "humain", {
            "records": [r.id for r in result.records],
            "events": result.events,
            "ignored": len(result.ignored),
        })
        sim.run()
        sim.timeline = sim.collect_timeline(marks)
        anchorer.after_action(sim, "epcis")
        return {
            "events": result.events,
            "imported": [serialize_record(r) for r in result.records],
            "ignored": result.ignored,
            "state": sim.state(),
        }


class ResetBody(BaseModel):
    scenario: ScenarioId = Field(default=DEFAULT_SCENARIO, examples=["cert"])


@app.get("/api/scenarios", summary="Available scenarios",
         response_model=list[ScenarioOut])
def get_scenarios() -> list[dict]:
    return scenarios_meta()


@app.get("/api/compare", summary="With vs without Firebreak: policy comparison",
         response_model=CompareOut, responses=ERRORS)
def get_compare() -> dict:
    """Policy B (cut off the supplier and its direct customers) vs
    policy C (targeted quarantine), measured against the same ground
    truth. 400 while no declaration is active."""
    with _lock:
        try:
            return sim_compare(sim)
        except LookupError as exc:
            raise HTTPException(400, str(exc)) from exc


@app.get("/api/timeline", summary="Ordered steps of the last action",
         response_model=TimelineOut)
def get_timeline() -> dict:
    """Step-by-step replay: declarations, seeds, contaminations with their parent,
    alerts sent/verified, blocked gates, releases. Each step carries
    cumulative impact counters (quarantined, gates_blocked,
    amount_blocked, amount_flowing)."""
    with _lock:
        return {"steps": copy.deepcopy(sim.timeline)}


@app.get("/api/events", summary="Live replay (Server-Sent Events)",
         response_class=StreamingResponse)
def get_events(speed: float = Query(
        default=DEMO_REPLAY_SPEED if DEMO_MODE else 0.5, ge=0, le=10,
        description="Pause in seconds between two events (0 = all at once).")):
    with _lock:
        steps = copy.deepcopy(sim.timeline)

    def gen():
        yield ": firebreak replay\n\n"
        for step in steps:
            yield f"data: {json.dumps(step, ensure_ascii=False)}\n\n"
            if speed:
                time.sleep(speed)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/demo/step", summary="Demo: advance one step",
          responses=ERRORS)
def post_demo_step() -> dict:
    """Drives the demo on click (or right arrow):
    0 reset(mixed) → 1 compromise → 2 explanation of the blocked payment
    → 3 remediation (cascading federated release) → 4 audit verification;
    then stays at the end. The response carries the index, the caption,
    the step detail and the full state."""
    global sim, demo_index
    with _lock:
        i = demo_index
        detail: dict | None = None
        error: str | None = None
        if i == 0:
            sim = build_simulation(DEMO_SCENARIO if DEMO_MODE else sim_scenario(sim))
            proposals.clear()
            anchorer.on_new_simulation(sim)
        elif i == 1:
            hint = sim.scenario["compromise"]
            sim.declare_compromise(
                hint["company"],
                to_scenario_time(datetime.fromisoformat(hint["since"])))
            detail = {"steps": len(sim.timeline)}
        elif i == 2:
            try:
                detail = sim_compare(sim)
            except LookupError as exc:
                error = str(exc)
        elif i == 3:
            record = sim.find_record("m-pay-X")
            if record is None or record.status != "quarantined":
                error = "m-pay-X is not quarantined — run step 1 first."
            else:
                rec_copy, path = copy.deepcopy((record, sim.path_records(record)))
                detail = {
                    "record": serialize_record(rec_copy),
                    "path": [serialize_record(r) for r in path],
                    **explainer.analyze(rec_copy, path),
                }
        elif i == 4:
            rec = sim.find_record("m-gr-X")
            if rec is None or rec.status != "quarantined":
                error = "m-gr-X is not quarantined — run step 1 first."
            else:
                sim.remediate("m-gr-X", "human_approval")
                detail = {"steps": len(sim.timeline)}
        elif i == 5:
            detail = sim.audit_verify()
        if i != 0:
            anchorer.after_action(sim, "demo")
        if i < len(DEMO_CAPTIONS):
            demo_index = i + 1
        return {
            "step": i,
            "total": len(DEMO_CAPTIONS),
            "caption": demo_caption(i),
            "detail": detail,
            "error": error,
            "done": i >= len(DEMO_CAPTIONS) - 1,
            "state": sim.state(),
        }


def sim_scenario(sim) -> str:
    return (sim.scenario or {}).get("id", DEFAULT_SCENARIO)


@app.post("/api/reset", summary="Reset (choose the scenario)",
          response_model=StateOut, responses=ERRORS)
def post_reset(body: ResetBody | None = None) -> dict:
    global sim, demo_index
    scenario = (body or ResetBody()).scenario
    if scenario not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario: {scenario}")
    with _lock:
        sim = build_simulation(scenario)
        proposals.clear()
        demo_index = 0
        anchorer.on_new_simulation(sim)
        return sim.state()


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


class _FreshStatic(StaticFiles):
    """Static files revalidated on every load (ETag → 304): after a
    `git pull`, the browser always serves the latest interface."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Final interface (docs/brief-ui.md), served without a build step or Node.
app.mount("/app", _FreshStatic(directory=WEB_DIR / "app", html=True), name="app")
# Sample documents, to try ingestion from the interface.
app.mount("/samples", StaticFiles(directory=SAMPLES_DIR), name="samples")
