"""Modèle de données Firebreak.

Un Record est un événement métier enregistré dans le registre (Ledger)
d'une seule entreprise. La dépendance entre records d'un même registre
est exprimée par `inputs` ; les échanges entre entreprises ne circulent
que via des jetons opaques (`token`) et des alertes signées.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Status = Literal["ok", "quarantined", "released"]


@dataclass
class Company:
    id: str
    name: str
    role: str
    gs1_prefix: str = ""  # préfixe entreprise GS1 : relie GLN/SGLN EPCIS à l'entreprise


@dataclass
class Record:
    id: str  # unique globalement, ex. "fab-0042"
    company: str  # entreprise propriétaire du registre
    origin: str  # entreprise émettrice de la donnée
    kind: str  # purchase_order, asn, quality_cert, invoice, payment…
    ts: datetime
    label: str  # libellé humain en français
    inputs: list[str] = field(default_factory=list)  # ids de records du MÊME registre
    gate: bool = False  # action irréversible : paiement, expédition, lancement prod.
    verified: bool = False  # confirmé par une source de confiance
    payload: dict = field(default_factory=dict)
    token: str | None = None  # référence opaque inter-entreprises (records reçus)
    status: Status = "ok"
    taint_path: list[str] | None = None  # preuve explicable : du seed jusqu'à ce record


def payment_amount(record: Record) -> float:
    """Montant comptabilisé d'un record : uniquement les paiements.

    Les montants des factures/ASN n'ont pas cours légal ici — compter les
    documents qui portent un montant compterait les mêmes euros plusieurs
    fois (facture émise + copie reçue + paiement)."""
    if record.kind != "payment":
        return 0.0
    amount = record.payload.get("amount", 0)
    return amount if isinstance(amount, (int, float)) else 0
