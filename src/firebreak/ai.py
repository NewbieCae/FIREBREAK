"""Explications Firebreak — l'IA n'explique jamais, elle ne décide pas.

`Explainer` est le point d'extension : une implémentation Bedrock pourra
remplacer `MockExplainer` sans toucher au moteur ni à l'API.
"""

from __future__ import annotations

from typing import Protocol

from .model import Record

GATE_LABELS = {
    "payment": "un paiement",
    "shipment": "une expédition",
    "production_lot": "un lancement de production",
}


class Explainer(Protocol):
    def explain(self, record: Record, path_records: list[Record]) -> str: ...
    def remediation_plan(self, record: Record) -> list[dict]: ...


class MockExplainer:
    """Explainer déterministe basé sur des gabarits français."""

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
