"""Contrat de l'API Firebreak : modèles Pydantic des réponses.

Ces modèles alimentent l'OpenAPI (/docs) : toute évolution du contrat
doit passer par ici et par docs/api.md.
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


class RecordOut(BaseModel):
    id: str = Field(description="Identifiant unique, ex. « m-pay-X ».")
    company: str = Field(description="Entreprise propriétaire du registre.")
    origin: str = Field(description="Entreprise émettrice de la donnée.")
    kind: str = Field(description="Type d'opération : asn, invoice, payment…")
    ts: str = Field(description="Horodatage ISO 8601 (heure de Paris, sans fuseau).")
    label: str
    inputs: list[str] = Field(description="Records du même registre dont celui-ci dépend.")
    gate: bool = Field(description="Action irréversible (paiement, expédition, production).")
    verified: bool = Field(
        description="Confirmé par une source de confiance : jamais contaminé, stoppe la propagation."
    )
    payload: dict
    token: str | None = Field(
        description="Jeton opaque du record reçu d'un partenaire (null si interne)."
    )
    status: RecordStatus
    taint_path: list[str] | None = Field(
        description="Chemin de contamination du seed jusqu'à ce record (null si non contaminé)."
    )


class EdgeOut(BaseModel):
    source: str
    target: str
    cross: bool = Field(description="True si l'arête relie deux entreprises.")


class CountersOut(BaseModel):
    total: int
    quarantined: int
    ok: int
    released: int
    gates_blocked: int = Field(description="Actions irréversibles en quarantaine.")


class CountersBlock(BaseModel):
    global_: CountersOut = Field(alias="global")
    per_company: dict[str, CountersOut]

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


AlertType = Literal["taint", "release"]
AuditEvent = Literal[
    "declaration", "declaration_withdrawn", "alert_sent", "alert_received",
    "quarantine", "remediation", "release", "document_confirmed",
]


class AlertOut(BaseModel):
    type: AlertType = Field(
        description="« taint » = contamination signalée ; « release » = levée de quarantaine."
    )
    from_: str = Field(alias="from")
    to: str
    tokens_count: int
    verified: bool | None = Field(description="Signature vérifiée par le destinataire.")
    issued_at: str

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class DeclarationOut(BaseModel):
    ledger: str = Field(description="Registre qui porte la déclaration.")
    source: str = Field(description="Entreprise déclarée compromise.")
    since: str


class StateOut(BaseModel):
    companies: list[CompanyOut]
    records: list[RecordOut]
    edges: list[EdgeOut]
    counters: CountersBlock
    alerts: list[AlertOut]
    declarations: list[DeclarationOut]


class RemediationOption(BaseModel):
    action: RemediationAction
    label: str
    rationale: str


AISource = Literal["mock", "bedrock"]


class ExplainOut(BaseModel):
    record: RecordOut
    path: list[RecordOut] = Field(description="Records du taint_path, dans l'ordre.")
    explanation: str
    remediation_plan: list[RemediationOption]
    source: AISource = Field(
        description="IA qui a produit l'explication : « bedrock », ou « mock » (gabarit "
                    "déterministe, aussi utilisé en repli si Bedrock échoue)."
    )


DocumentKind = Literal["purchase_order", "asn", "invoice", "bank_details_change"]


class ProposedRecordOut(BaseModel):
    id: str = Field(description="Identifiant que portera le record une fois confirmé.")
    company: str = Field(description="Registre destinataire (paramètre « company »).")
    origin: str | None = Field(description="Émetteur détecté ; null si non reconnu.")
    kind: DocumentKind | None = Field(description="Type de document ; null si non reconnu.")
    ts: str = Field(description="Heure de réception (heure de Paris, sans fuseau).")
    label: str
    inputs: list[str]
    gate: bool
    payload: dict = Field(
        description="amount, rib, previous_rib, bank_details_change, references, dates "
                    "(seuls les champs trouvés sont présents, sauf references et dates)."
    )


class ProposalOut(BaseModel):
    id: str = Field(description="Identifiant de la proposition, ex. « doc-01 ».")
    status: Literal["pending", "confirmed"]
    source: AISource = Field(description="Extraction par « bedrock » ou « mock » (regex).")
    confidence: float = Field(ge=0, le=1, description="Confiance de l'extraction (0 à 1).")
    missing: list[str] = Field(description="Champs attendus pour ce type mais non trouvés.")
    record: ProposedRecordOut


class AuditEntryOut(BaseModel):
    index: int
    ts: str = Field(description="Heure du scénario (ISO 8601, heure de Paris).")
    company: str
    event: AuditEvent
    actor: Literal["humain", "règle"]
    details: dict
    prev_hash: str = Field(description="Hash de l'entrée précédente (64 zéros pour la première).")
    hash: str = Field(description="sha256(prev_hash + JSON canonique de l'entrée sans hash).")


class AuditOut(BaseModel):
    company: str
    head: str = Field(description="Hash de la dernière entrée.")
    entries: list[AuditEntryOut]


class AuditJournalCheck(BaseModel):
    company: str
    ok: bool
    entries: int
    first_broken_index: int | None = Field(
        description="Index de la première entrée cassée, null si la chaîne est intacte."
    )
    head: str


class BrokenRef(BaseModel):
    company: str
    index: int


class AuditVerifyOut(BaseModel):
    ok: bool
    first_broken: BrokenRef | None
    journals: list[AuditJournalCheck]


class ErrorOut(BaseModel):
    detail: str
