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


class AlertOut(BaseModel):
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


class ExplainOut(BaseModel):
    record: RecordOut
    path: list[RecordOut] = Field(description="Records du taint_path, dans l'ordre.")
    explanation: str
    remediation_plan: list[RemediationOption]


class ErrorOut(BaseModel):
    detail: str
