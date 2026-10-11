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
    gs1_prefix: str = Field(
        description="Préfixe entreprise GS1 : relie les lieux (SGLN/GLN) EPCIS à l'entreprise.")


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
    amount_blocked: float = Field(
        default=0, description="Montant cumulé (€) des paiements en quarantaine.")
    amount_flowing: float = Field(
        default=0, description="Montant cumulé (€) des paiements qui continuent.")


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


class CompromiseHint(BaseModel):
    company: str = Field(description="Entreprise à déclarer compromise pour la démo.")
    since: str = Field(description="Début de la fenêtre de compromission.")


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
    scenario: ScenarioOut = Field(description="Scénario chargé par le dernier reset.")


StepType = Literal[
    "declaration", "withdrawal", "seed", "quarantine", "gate_blocked",
    "release", "remediation", "alert_sent", "alert_received",
    "document_confirmed", "epcis_import", "lot_suspect", "lot_suspect_withdrawn",
    "report_sent", "report_received", "report_decided",
    "inbound_hold", "inbound_accepted", "inbound_rejected",
]


class StepCountersOut(BaseModel):
    quarantined: int = Field(description="Opérations en quarantaine à cette étape.")
    gates_blocked: int = Field(description="Actions irréversibles bloquées à cette étape.")
    amount_blocked: float = Field(description="Montant des paiements bloqués cumulé (€) à cette étape.")
    amount_flowing: float = Field(description="Montant des paiements qui continuent (€) à cette étape.")


class StepOut(BaseModel):
    n: int = Field(description="Numéro d'étape, à partir de 1.")
    ts: str = Field(description="Horodatage simulé de l'étape (heure du scénario).")
    type: StepType
    company: str = Field(description="Registre concerné par l'étape.")
    record: str | None = Field(default=None, description="Record concerné, s'il y en a un.")
    parent: str | None = Field(
        default=None, description="Record parent dont dépend la contamination.")
    gate: bool = False
    label: str | None = None
    rule: str | None = Field(
        default=None,
        description="Règle déclencheuse : source_compromise, alerte_verifiee, dependance.")
    alert: dict | None = Field(
        default=None,
        description="Alerte concernée : from, to, tokens_count, verified, "
                    "links = paires [record émis, record reçu] pour animer les arêtes.")
    counters: StepCountersOut = Field(description="Compteurs d'impact cumulés à cette étape.")
    text: str = Field(description="Phrase française prête à afficher pour la démo.")


class TimelineOut(BaseModel):
    steps: list[StepOut] = Field(
        description="Étapes ordonnées de la dernière action "
                    "(compromise, withdraw, remédiation, ingestion).")


class CompareDeclOut(BaseModel):
    company: str = Field(description="Entreprise déclarée compromise.")
    since: str


class LeakedOut(BaseModel):
    id: str
    label: str
    company: str


class CompareMetricsOut(BaseModel):
    blocked: int = Field(description="Records bloqués par cette politique.")
    healthy_blocked: int = Field(description="Records bloqués hors vérité terrain (collatéraux).")
    leaked: int = Field(description="Records contaminés non bloqués (fuites).")
    leaked_ids: list[LeakedOut]
    gates_blocked: int = Field(description="Actions irréversibles bloquées.")
    payments_blocked_eur: float = Field(description="Montant des paiements bloqués (€).")
    payments_flowing_eur: float = Field(description="Montant des paiements qui continuent (€).")
    activity_preserved_pct: float | None = Field(
        description="Part des opérations saines non bloquées (%).")
    precision: float | None = Field(description="Précision du blocage (null si rien de bloqué).")
    recall: float | None = Field(description="Rappel (null si rien de contaminé).")
    companies_hit: list[str] = Field(description="Entreprises avec ≥ 1 record bloqué.")
    blocked_ids: list[str]


class CompareSideOut(CompareMetricsOut):
    title: str
    policy: str = Field(description="« B » : coupe fournisseur + clients directs. « C » : Firebreak.")
    subtitle: str | None = None
    scope: dict | None = Field(default=None, description="Périmètre coupé par déclaration (politique B).")


class CompareOut(BaseModel):
    declarations: list[CompareDeclOut]
    truth: dict = Field(description="Taille du vrai périmètre contaminé (`contaminated`), ses identifiants (`ids`) et sa définition.")
    without: CompareSideOut = Field(description="Politique B : blocage large du partenaire.")
    with_: CompareSideOut = Field(
        alias="with", description="Politique C : quarantaine ciblée Firebreak.")
    healthy_blocked_ratio: float | None = Field(
        description="without.healthy_blocked / with.healthy_blocked (null si 0).")
    bench: dict | None = Field(description="Agrégat de bench/results.csv, null si absent.")
    real_world: list[dict] = Field(description="Exemples réels de coupure totale.")

    model_config = {"populate_by_name": True}


class EpcisIgnoredOut(BaseModel):
    index: int = Field(description="Position de l'événement dans eventList.")
    type: str | None
    reason: str


class EpcisImportOut(BaseModel):
    events: int = Field(description="Nombre d'événements dans le document.")
    imported: list[RecordOut] = Field(description="Records ajoutés, après recalcul.")
    ignored: list[EpcisIgnoredOut]
    state: StateOut


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


class OnchainCheck(BaseModel):
    anchored_head: str | None = Field(
        default=None, description="Tête du journal telle qu'ancrée sur la chaîne.")
    anchored_entries: int | None = None
    block: int | None = None
    tx_hash: str | None = None
    explorer_link: str | None = None
    matches: bool | None = Field(
        default=None,
        description="Le journal local tronqué à `anchored_entries` a pour dernier hash "
                    "`anchored_head`. null si `unreadable`."
    )
    unreadable: bool = Field(
        default=False,
        description="Un ancrage confirmé existe mais la lecture on-chain a échoué "
                    "après plusieurs tentatives : à réessayer, ce n'est pas une falsification."
    )


class AuditJournalCheck(BaseModel):
    company: str
    ok: bool
    entries: int
    first_broken_index: int | None = Field(
        description="Index de la première entrée cassée, null si la chaîne est intacte."
    )
    head: str
    onchain: OnchainCheck | None = Field(
        default=None, description="Ancrage Avalanche ; null si la chaîne est désactivée "
                                  "ou si rien n'est encore ancré.")


class BrokenRef(BaseModel):
    company: str
    index: int


class AuditVerifyOut(BaseModel):
    ok: bool
    first_broken: BrokenRef | None
    journals: list[AuditJournalCheck]
    onchain_ok: bool | None = Field(
        default=None, description="Tous les journaux ancrés correspondent ; null si "
                                  "la chaîne est désactivée ou rien d'ancré.")


class ChainQueueOut(BaseModel):
    pending: int
    sent: int
    confirmed: int
    failed: int


class ChainStatusOut(BaseModel):
    mode: str = Field(description="off, tester ou l1.")
    connected: bool
    chain_id: int | None
    contract: str | None
    explorer_url: str | None
    run_id: str | None = Field(description="Identifiant du run courant (hex 32 octets).")
    last_block: int | None
    queue: ChainQueueOut


class AnchorOut(BaseModel):
    id: int
    kind: str = Field(description="audit, alert, incident ou ack.")
    company: str
    hash: str
    status: str = Field(description="pending, sent, confirmed, failed ou disabled.")
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
