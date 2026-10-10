# GOAL — finswag / FIREBREAK

> Fichier **partagé par toute l'équipe**. Chaque agent le met à jour à la fin de chaque itération (voir `AGENTS.md` → « Protocole d'équipe »).
> On modifie seulement les lignes qui ont changé et on n'efface jamais le travail d'un autre. En cas de conflit Git, on garde les deux versions.

## Objectif

Livrer **FIREBREAK, le pare-feu des supply chains**, au hackathon Secure Horizons (Track 3 · Uncharted Frontiers) :
une démo de 3 minutes qui montre qu'en cas de compromission d'un partenaire, on bloque **uniquement les opérations contaminées** (3 sur 100, pas 100), avec une décision prouvable et des alertes signées entre entreprises.

- **Rendu : dimanche 11 octobre 2026, 12 h.** (Le brief annonçait 17 h pour la fin du hacking.)
- Gel du code visé : dimanche **10 h**, puis répétition du pitch jusqu'à 12 h.
- Idée : `docs/firebreak.md` · Concurrents : `docs/benchmark-firebreak.md` · Plan : `docs/plan.md` · API : `docs/api.md`.

## Équipe

| Membre | GitHub | Session | Rôle |
|---|---|---|---|
| Yann | Sc4rville | `sessions/yann.md` | Produit : moteur, API, IA |
| Céline | NewbieCae | `sessions/celine.md` | Banc d'essai : preuve chiffrée de l'efficacité (`synth.py`, `scripts/bench.py`) |
| Maria | magraku | `sessions/maria.md` | à préciser |
| Mika | mncodol | `sessions/mika.md` | à préciser |

L'interface finale est faite par une collègue de l'équipe, à partir de `docs/api.md`. Elle indique son nom dans ce tableau.

## Avancement du plan en 6 étapes

| # | Étape | État | Commit / note |
|---|---|---|---|
| 1 | Consolider le socle et figer le contrat API | Fait | `37cf8dd` |
| 2 | Fédération complète et journal d'audit | Fait | `5ea8486` |
| 3 | Scénarios réalistes et import EPCIS | Fait | `6560a9c`, `76711ec` |
| 4 | Timeline et événements live (SSE) | Fait | `fe5ff07`, `c0476e5` (compteurs € = paiements uniquement) |
| 5 | IA : Bedrock et lecture de documents | Fait | `434abde` |
| 6 | Prêt pour la démo | Fait | `9307ad8` — `bash scripts/demo.sh`, script `docs/demo.md`, chiffres `uv run python -m firebreak.demo_figures` |

Tests : 213 verts (`uv run pytest -q`), état au 11 octobre à 01 h.

Chiffres démo (scénario mixed, fournisseur compromis depuis 14 h ; source : `uv run python -m firebreak.demo_figures`) : 17 opérations bloquées sur 193, 4 actions irréversibles bloquées, 5 210 € de paiement frauduleux bloqué, 92 102 € de paiements qui continuent.
Avec vs sans : sans Firebreak (on coupe le fournisseur et ses clients directs), 54 opérations bloquées dont 42 saines, et 5 contaminées passent quand même jusqu'au client ; avec Firebreak, 17 bloquées, 0 saine, 0 fuite.

## Prochaines actions

- [x] Étape 4 : timeline et flux SSE (`/api/timeline`, `/api/events`, bouton « Rejouer »).
- [ ] Interface finale branchée sur l'API (`docs/api.md`).
- [x] Étape 6 : mode démo (`FIREBREAK_DEMO=1`, `/api/demo/step`, flèche droite), script `docs/demo.md`, test de bout en bout.
- [x] Banc d'essai v2 : gates fuités, pire cas / 5e centile, ventilation par entreprise compromise, politique D « Firebreak + prudence », limites écrites par le script (Céline). **⚠️ Chiffres publiés changés le 11/10** (toutes les entreprises tirées + 10 % de réceptions hors fédération) : p=0 → Firebreak 9,6 sains bloqués contre 43,2 pour B (4,5× moins), rappel 100 % contre 98,5 %, 0 action irréversible fuitée ; p=0,3 → rappel C 93,4 %, D 97,9 %. `docs/bench-results.md`, `docs/fiche-defense.md`, l'exemple de `docs/api.md` et `tests/test_compare.py` sont à jour ; `/api/compare` lit le CSV.
- [x] Effet waouh « Avec vs sans Firebreak » : écran coupé en deux (bouton « Avec vs sans » + étape 3 de la démo), `/api/compare`, banc d'essai de Céline, cas JLR et CDK sourcés (Yann).
- [ ] Gel du code à 10 h : tag `demo-freeze` (Yann).
- [ ] Pitch et slides (s'appuyer sur `docs/benchmark-firebreak.md`).
- [ ] Notion : inviter les 3 coéquipières et coéquipiers avec accès en modification (à faire à la main via Partager).

## Décisions

- 11/10 (Céline) : banc v2 — l'entreprise compromise est tirée parmi toutes (client final compris) ; politique D = C + signal « provenance manquante » lu dans l'état du moteur seulement, présentée comme borne haute ; 10 % de réceptions légitimes hors fédération ajoutées comme bruit.

- Track 3 annoncé aux organisateurs, le 10 octobre.

- 10/10 : banc d'essai — vérité terrain = descendants par toutes les vraies dépendances des records émis par l'entreprise compromise après `since`, `verified` exclus (même sémantique que le moteur).

- 10/10 : on construit FIREBREAK, pensé pour le Track 3, au lieu des pistes du Track 1 du brief initial.
- 10/10 : stack Python 3.12 + uv + FastAPI + networkx ; IA simulée par défaut, Bedrock en option.
- 10/10 : le blocage est décidé par des règles sur le graphe, jamais par l'IA.
- 11/10 : pas de branches, tout sur `main`, pull au début et push à la fin de chaque itération ; conflits arbitrés par l'agent (`AGENTS.md` → « Conflits Git »). L'équipe se parle via `messages.md` (`scripts/messages.py`).

## Blocages

- [x] Banc d'essai : générateur à graine + 3 politiques + CSV (Céline) — chiffres v1 caducs (4,3×, 11,4 contre 49,5, 91,6 %), remplacés par la v2 ci-dessus. Reproduire : `uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3`
- [ ] Clés de signature et PAIR_SECRET de federation.py : ne plus les dériver du nom / ne plus les écrire en dur
- [ ] Retirer adresses e-mail et détails de boîte mail de AGENTS.md et docs/brief.md, puis décider du sort de l'historique
- [x] README : mettre Track 3, marqueurs de conflit poussés sur main résolus (Céline, 11/10)
- [ ] Confirmer le passage officiel Track 1 → Track 3 auprès des organisateurs (annoncé le 10/10, voir Décisions)