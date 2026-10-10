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
| Céline | NewbieCae | `sessions/celine.md` | à préciser |
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
| 6 | Prêt pour la démo | En cours | lancé le 10/10 à 23 h 50, gel à 10 h |

Tests : 147 verts (`uv run pytest -q`), état au 10 octobre à 23 h 45.

Chiffres démo (scénario mixed, fournisseur compromis depuis 14 h) : 17 opérations bloquées sur 145, 4 actions irréversibles bloquées, 5 210 € de paiement frauduleux bloqué, 80 402 € de paiements qui continuent.

## Prochaines actions

- [x] Étape 4 : timeline et flux SSE (`/api/timeline`, `/api/events`, bouton « Rejouer »).
- [ ] Interface finale branchée sur l'API (`docs/api.md`).
- [ ] Étape 6 : mode démo, script de démo avec chiffres réels, gel.
- [ ] Pitch et slides (s'appuyer sur `docs/benchmark-firebreak.md`).
- [ ] Notion : inviter les 3 coéquipières et coéquipiers avec accès en modification (à faire à la main via Partager).

## Décisions

- 10/10 : on construit FIREBREAK, pensé pour le Track 3, au lieu des pistes du Track 1 du brief initial.
- 10/10 : stack Python 3.12 + uv + FastAPI + networkx ; IA simulée par défaut, Bedrock en option.
- 10/10 : le blocage est décidé par des règles sur le graphe, jamais par l'IA.

## Blocages

- À confirmer : le passage officiel du Track 1 au Track 3 auprès des organisateurs (date limite annoncée : 10/10 à 18 h 30). Le README parle encore du Track 1.

- [ ] Banc d'essai : générateur à graine + 3 politiques + CSV (Céline)
- [ ] Clés de signature et PAIR_SECRET de federation.py : ne plus les dériver du nom / ne plus les écrire en dur
- [ ] Retirer adresses e-mail et détails de boîte mail de AGENTS.md et docs/brief.md, puis décider du sort de l'historique
- [ ] README : mettre Track 3 ; confirmer le passage officiel Track 1 → Track 3 auprès des organisateurs