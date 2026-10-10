"""Mode démo FIREBREAK — FIREBREAK_DEMO=1.

Scénario par défaut (« mixed »), IA en mock garanti (aucune dépendance
réseau), vitesse de rejeu SSE réglée pour la scène, et le stepper piloté
par POST /api/demo/step (clic ou flèche droite dans le dashboard).
"""

from __future__ import annotations

import os

DEMO_MODE = os.environ.get("FIREBREAK_DEMO", "").strip() == "1"
DEMO_SCENARIO = "mixed"
# Pause entre deux événements SSE en mode démo : assez lent pour raconter,
# assez rapide pour tenir la démo en 3 min.
DEMO_REPLAY_SPEED = 0.35

DEMO_CAPTIONS = [
    "Réinitialisation : scénario « Attaque mixte », une matinée normale — "
    "toutes les opérations circulent.",
    "Aciers Durand est déclarée compromise depuis 14 h : la contamination se "
    "propage d'entreprise en entreprise, seules les opérations contaminées "
    "passent en quarantaine.",
    "Avec vs sans Firebreak : à gauche, la coupure totale du partenaire et "
    "de ses clients ; à droite, la quarantaine ciblée — mêmes fuites "
    "traitées, beaucoup moins de dégâts collatéraux.",
    "Explication : le paiement au RIB modifié est bloqué — la preuve est le "
    "chemin exact dans le graphe de dépendances.",
    "Remédiation : validation humaine de la réception vérifiée — les records "
    "qui n'en dépendaient plus sont libérés et des alertes de levée signées "
    "partent vers les partenaires.",
    "Audit : les journaux de chaque entreprise sont chaînés par hash et "
    "intègres — chaque décision est rejouable.",
]
DEMO_END_CAPTION = (
    "Démo terminée — « Réinitialiser » (ou un premier appel) pour recommencer."
)


def demo_caption(step: int) -> str:
    if 0 <= step < len(DEMO_CAPTIONS):
        return DEMO_CAPTIONS[step]
    return DEMO_END_CAPTION
