"""Firebreak API contract: Pydantic response models.

These models feed the OpenAPI schema (/docs): any change to the contract
must go through here and through docs/api.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RecordStatus = Literal["ok", "quarantined", "released"]
RemediationAction = Literal["revalidate", "human_approval", "trusted_source"]


class CompanyOut(BaseModel):
    id: str
    name: str
    role: str
    gs1_prefix: str = Field(
        description="GS1 company prefix: links EPCIS locations (SGLN/GLN) to the company.")


class RecordOut(BaseModel):
    id: str = Field(description="Unique identifier, e.g. \"m-pay-X\".")
    company: str = Field(description="Company that owns the ledger.")
    origin: str = Field(description="Company that issued the data.")
    kind: str = Field(description="Operation type: asn, invoice, payment…")
    ts: str = Field(description="ISO 8601 timestamp (Paris time, no time zone).")
    label: str
    inputs: list[str] = Field(description="Records of the same ledger this one depends on.")
    gate: bool = Field(description="Irreversible action (payment, shipment, production).")
    verified: bool = Field(
        description="Confirmed by a trusted source: never contaminated, stops propagation."
    )
    payload: dict
    token: str | None = Field(
        description="Opaque token of the record received from a partner (null if internal)."
    )
    status: RecordStatus
    taint_path: list[str] | None = Field(
        description="Contamination path from the seed to this record (null if not contaminated)."
    )


class EdgeOut(BaseModel):
    source: str
    target: str
    cross: bool = Field(description="True if the edge links two companies.")


class CountersOut(BaseModel):
    total: int
    quarantined: int
    ok: int
    released: int
    gates_blocked: int = Field(description="Irreversible actions in quarantine.")
    amount_blocked: float = Field(
        default=0, description="Cumulative amount (€) of quarantined payments.")
    amount_flowing: float = Field(
        default=0, description="Cumulative amount (€) of payments that keep flowing.")


class CountersBlock(BaseModel):
    global_: CountersOut = Field(alias="global")
    per_company: dict[str, CountersOut]

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


AlertType = Literal["taint", "release", "report"]
AuditEvent = Literal[
    "declaration", "declaration_withdrawn", "alert_sent", "alert_received",
    "quarantine", "remediation", "release", "document_confirmed", "epcis_import",
    "lot_suspect", "lot_suspect_withdrawn", "quality_report_sent",
    "quality_report_received", "quality_report_decided",
    "inbound_hold", "inbound_accepted", "inbound_rejected",
]


class AlertOut(BaseModel):
    type: AlertType = Field(
        description="\"taint\" = reported contamination; \"release\" = quarantine lifted."
    )
    from_: str = Field(alias="from")
    to: str
    tokens_count: int
    verified: bool | None = Field(description="Signature verified by the recipient.")
    issued_at: str

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class DeclarationOut(BaseModel):
    ledger: str = Field(description="Ledger that holds the declaration.")
    source: str = Field(description="Company declared compromised.")
    since: str


class CompromiseHint(BaseModel):
    company: str = Field(description="Company to declare compromised for the demo.")
    since: str = Field(description="Start of the compromise window.")


ScenarioId = Literal["mixed", "rib", "cert", "asn", "lot", "recall"]


class ScenarioOut(BaseModel):
    id: ScenarioId
    label: str
    description: str
    compromise: CompromiseHint
    incident: dict | None = None


class StateOut(BaseModel):
    companies: list[CompanyOut]
    records: list[RecordOut]
    edges: list[EdgeOut]
    counters: CountersBlock
    alerts: list[AlertOut]
    declarations: list[DeclarationOut]
    scenario: ScenarioOut = Field(description="Scenario loaded by the last reset.")


StepType = Literal[
    "declaration", "withdrawal", "seed", "quarantine", "gate_blocked",
    "release", "remediation", "alert_sent", "alert_received",
    "document_confirmed", "epcis_import", "lot_suspect", "lot_suspect_withdrawn",
    "report_sent", "report_received", "report_decided",
    "inbound_hold", "inbound_accepted", "inbound_rejected",
]


class StepCountersOut(BaseModel):
    quarantined: int = Field(description="Operations in quarantine at this step.")
    gates_blocked: int = Field(description="Irreversible actions blocked at this step.")
    amount_blocked: float = Field(description="Cumulative amount (€) of blocked payments at this step.")
    amount_flowing: float = Field(description="Amount (€) of payments that keep flowing at this step.")


class StepOut(BaseModel):
    n: int = Field(description="Step number, starting at 1.")
    ts: str = Field(description="Simulated timestamp of the step (scenario time).")
    type: StepType
    company: str = Field(description="Ledger concerned by the step.")
    record: str | None = Field(default=None, description="Record concerned, if any.")
    parent: str | None = Field(
        default=None, description="Parent record the contamination depends on.")
    gate: bool = False
    label: str | None = None
    rule: str | None = Field(
        default=None,
        description="Triggering rule: source_compromise, alerte_verifiee, dependance.")
    alert: dict | None = Field(
        default=None,
        description="Alert concerned: from, to, tokens_count, verified, "
                    "links = [sent record, received record] pairs to animate the edges.")
    counters: StepCountersOut = Field(description="Cumulative impact counters at this step.")
    text: str = Field(description="Ready-to-display sentence for the demo.")


class TimelineOut(BaseModel):
    steps: list[StepOut] = Field(
        description="Ordered steps of the last action "
                    "(compromise, withdraw, remediation, ingestion).")


class CompareDeclOut(BaseModel):
    company: str = Field(description="Company declared compromised.")
    since: str


class LeakedOut(BaseModel):
    id: str
    label: str
    company: str


class CompareMetricsOut(BaseModel):
    blocked: int = Field(description="Records blocked by this policy.")
    healthy_blocked: int = Field(description="Records blocked outside the ground truth (collateral).")
    leaked: int = Field(description="Contaminated records not blocked (leaks).")
    leaked_ids: list[LeakedOut]
    gates_blocked: int = Field(description="Irreversible actions blocked.")
    payments_blocked_eur: float = Field(description="Amount of blocked payments (€).")
    payments_flowing_eur: float = Field(description="Amount of payments that keep flowing (€).")
    activity_preserved_pct: float | None = Field(
        description="Share of healthy operations not blocked (%).")
    precision: float | None = Field(description="Blocking precision (null if nothing blocked).")
    recall: float | None = Field(description="Recall (null if nothing contaminated).")
    companies_hit: list[str] = Field(description="Companies with ≥ 1 blocked record.")
    blocked_ids: list[str]


class CompareSideOut(CompareMetricsOut):
    title: str
    policy: str = Field(description="\"B\": cut off supplier + direct customers. \"C\": Firebreak.")
    subtitle: str | None = None
    scope: dict | None = Field(default=None, description="Scope cut off per declaration (policy B).")


class CompareOut(BaseModel):
    declarations: list[CompareDeclOut]
    truth: dict = Field(description="Size of the true contaminated scope (`contaminated`), its identifiers (`ids`) and its definition.")
    without: CompareSideOut = Field(description="Policy B: broad blocking of the partner.")
    with_: CompareSideOut = Field(
        alias="with", description="Policy C: Firebreak targeted quarantine.")
    healthy_blocked_ratio: float | None = Field(
        description="without.healthy_blocked / with.healthy_blocked (null if 0).")
    bench: dict | None = Field(description="Aggregate of bench/results.csv, null if absent.")
    real_world: list[dict] = Field(description="Real-world examples of a total cut-off.")

    model_config = {"populate_by_name": True}


class EpcisIgnoredOut(BaseModel):
    index: int = Field(description="Position of the event in eventList.")
    type: str | None
    reason: str


class EpcisImportOut(BaseModel):
    events: int = Field(description="Number of events in the document.")
    imported: list[RecordOut] = Field(description="Records added, after recomputation.")
    ignored: list[EpcisIgnoredOut]
    state: StateOut


class RemediationOption(BaseModel):
    action: RemediationAction
    label: str
    rationale: str


AISource = Literal["mock", "bedrock"]


class ExplainOut(BaseModel):
    record: RecordOut
    path: list[RecordOut] = Field(description="Records of the taint_path, in order.")
    explanation: str
    remediation_plan: list[RemediationOption]
    source: AISource = Field(
        description="AI that produced the explanation: \"bedrock\", or \"mock\" (deterministic "
                    "template, also used as a fallback if Bedrock fails)."
    )


DocumentKind = Literal["purchase_order", "asn", "invoice", "bank_details_change"]


class ProposedRecordOut(BaseModel):
    id: str = Field(description="Identifier the record will carry once confirmed.")
    company: str = Field(description="Recipient ledger (\"company\" parameter).")
    origin: str | None = Field(description="Detected issuer; null if not recognized.")
    kind: DocumentKind | None = Field(description="Document type; null if not recognized.")
    ts: str = Field(description="Time of receipt (Paris time, no time zone).")
    label: str
    inputs: list[str]
    gate: bool
    payload: dict = Field(
        description="amount, rib, previous_rib, bank_details_change, references, dates "
                    "(only the fields found are present, except references and dates)."
    )


class ProposalOut(BaseModel):
    id: str = Field(description="Proposal identifier, e.g. \"doc-01\".")
    status: Literal["pending", "confirmed"]
    source: AISource = Field(description="Extraction by \"bedrock\" or \"mock\" (regex).")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence (0 to 1).")
    missing: list[str] = Field(description="Fields expected for this type but not found.")
    record: ProposedRecordOut


class AuditEntryOut(BaseModel):
    index: int
    ts: str = Field(description="Scenario time (ISO 8601, Paris time).")
    company: str
    event: AuditEvent
    actor: Literal["humain", "règle"]
    details: dict
    prev_hash: str = Field(description="Hash of the previous entry (64 zeros for the first one).")
    hash: str = Field(description="sha256(prev_hash + canonical JSON of the entry without hash).")


class AuditOut(BaseModel):
    company: str
    head: str = Field(description="Hash of the last entry.")
    entries: list[AuditEntryOut]


class OnchainCheck(BaseModel):
    anchored_head: str | None = Field(
        default=None, description="Journal head as anchored on-chain.")
    anchored_entries: int | None = None
    block: int | None = None
    tx_hash: str | None = None
    explorer_link: str | None = None
    matches: bool | None = Field(
        default=None,
        description="The local journal truncated to `anchored_entries` has "
                    "`anchored_head` as its last hash. null if `unreadable`."
    )
    unreadable: bool = Field(
        default=False,
        description="A confirmed anchor exists but the on-chain read failed "
                    "after several attempts: retry, this is not tampering."
    )


class AuditJournalCheck(BaseModel):
    company: str
    ok: bool
    entries: int
    first_broken_index: int | None = Field(
        description="Index of the first broken entry, null if the chain is intact."
    )
    head: str
    onchain: OnchainCheck | None = Field(
        default=None, description="Avalanche anchor; null if the chain is disabled "
                                  "or nothing is anchored yet.")


class BrokenRef(BaseModel):
    company: str
    index: int


class AuditVerifyOut(BaseModel):
    ok: bool
    first_broken: BrokenRef | None
    journals: list[AuditJournalCheck]
    onchain_ok: bool | None = Field(
        default=None, description="All anchored journals match; null if "
                                  "the chain is disabled or nothing is anchored.")


class ChainQueueOut(BaseModel):
    pending: int
    sent: int
    confirmed: int
    failed: int


class ChainStatusOut(BaseModel):
    mode: str = Field(description="off, tester or l1.")
    connected: bool
    chain_id: int | None
    contract: str | None
    explorer_url: str | None
    run_id: str | None = Field(description="Identifier of the current run (32-byte hex).")
    last_block: int | None
    queue: ChainQueueOut


class AnchorOut(BaseModel):
    id: int
    kind: str = Field(description="audit, alert, incident or ack.")
    company: str
    hash: str
    status: str = Field(description="pending, sent, confirmed, failed or disabled.")
    tx_hash: str | None
    block: int | None
    error: str | None
    created_at: str
    explorer_link: str | None


class RewriteBody(BaseModel):
    company: str = Field(examples=["fabricant"])
    drop_event: str = Field(examples=["alert_received"])


class ErrorOut(BaseModel):
    detail: str
