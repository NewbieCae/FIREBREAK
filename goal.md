# GOAL — finswag / FIREBREAK

> Fichier **partagé par toute l'équipe**. Chaque agent le met à jour à la fin de chaque itération (voir `AGENTS.md` → « Protocole d'équipe »).
> On modifie seulement les lignes qui ont changé et on n'efface jamais le travail d'un autre. En cas de conflit Git, on garde les deux versions.

## Objectif

Livrer **FIREBREAK, le pare-feu des supply chains**, au hackathon Secure Horizons (Track 3 · Uncharted Frontiers) :
une démo de 3 minutes qui montre qu'en cas de compromission d'un partenaire, on bloque **uniquement les opérations contaminées** (3 sur 100, pas 100), avec une décision prouvable et des alertes signées entre entreprises.

- **Rendu : dimanche 11 octobre 2026, 12 h : premier tour de pitch** (5 min + 2 min de questions). Les finalistes repitchent plus tard dans la journée (3 min + 3 min de questions, voir `docs/pitch-firebreak.md`).
- Gel du code visé : dimanche **10 h**, puis répétition du pitch jusqu'à 12 h.
- Idée : `docs/firebreak.md` · Concurrents : `docs/benchmark-firebreak.md` · Plan : `docs/plan.md` · API : `docs/api.md`.

## Équipe

| Membre | GitHub | Session | Rôle |
|---|---|---|---|
| Yann | Sc4rville | `sessions/yann.md` | Produit : moteur, API, IA |
| Céline | NewbieCae | `sessions/celine.md` | Banc d'essai : preuve chiffrée de l'efficacité (`synth.py`, `scripts/bench.py`) |
| Maria | magraku | `sessions/maria.md` | à préciser (proposé : slides du pitch selon `design.md` + test de l'interface en 1920×1080) |
| Mika | mncodol | `sessions/mika.md` | Avalanche L1 (preuves on-chain) et scénarios qualité (lot suspect, rappel), avec deux agents (pc1, pc2) |

L'interface finale (`web/app/`, sur `/app/`) est faite par Yann, à partir de `docs/api.md` et du brief `docs/brief-ui.md` ; design dans `design.md`.

## Avancement du plan en 6 étapes

| # | Étape | État | Commit / note |
|---|---|---|---|
| 1 | Consolider le socle et figer le contrat API | Fait | `37cf8dd` |
| 2 | Fédération complète et journal d'audit | Fait | `5ea8486` |
| 3 | Scénarios réalistes et import EPCIS | Fait | `6560a9c`, `76711ec` |
| 4 | Timeline et événements live (SSE) | Fait | `fe5ff07`, `c0476e5` (compteurs € = paiements uniquement) |
| 5 | IA : Bedrock et lecture de documents | Fait | `434abde` |
| 6 | Prêt pour la démo | Fait | `9307ad8` — `bash scripts/demo.sh`, script `docs/demo.md`, chiffres `uv run python -m firebreak.demo_figures` |

Tests : 267 verts (`uv run pytest -q`), état au 11 octobre à 02 h 50.

Chiffres démo (scénario mixed, fournisseur compromis depuis 14 h ; source : `uv run python -m firebreak.demo_figures`) : 17 opérations bloquées sur 193, 4 actions irréversibles bloquées, 5 210 € de paiement frauduleux bloqué, 92 102 € de paiements qui continuent.
Avec vs sans : sans Firebreak (on coupe le fournisseur et ses clients directs), 54 opérations bloquées dont 42 saines, et 5 contaminées passent quand même jusqu'au client ; avec Firebreak, 17 bloquées, 0 saine, 0 fuite.

## Prochaines actions

- [x] Étape 4 : timeline et flux SSE (`/api/timeline`, `/api/events`, bouton « Rejouer »).
- [x] Interface finale branchée sur l'API (`docs/api.md`), selon le brief `docs/brief-ui.md` (Yann) — `web/app/`, servie sur http://localhost:8000/app/ (`bash scripts/demo.sh` l'ouvre) : les 8 écrans du brief, bonus compris (import, vue partenaire), preuves Avalanche si la chaîne est active, les 5 gestes à la flèche droite. Testée en 1440×900 et 1920×1080 sur les 4 scénarios.
- [x] Étape 6 : mode démo (`FIREBREAK_DEMO=1`, `/api/demo/step`, flèche droite), script `docs/demo.md`, test de bout en bout.
- [x] Banc d'essai : balayages de sensibilité (taille 5/8/12 entreprises à 60 opérations chacune, bruit hors fédération 0/10/30 %) avant de figer les chiffres (Céline) — section « Sensibilité » de `docs/bench-results.md`, données dans `bench/sensitivity.csv`. **Les 4 conclusions de la fiche de défense tiennent** (C < B en collatéraux à toutes les tailles, ratio 4,5× à 9×, qui augmente avec la taille ; rappel C 100 % à p=0 ; à p=0,3, C sous B en rappel ; D rattrape des fuites quel que soit le bruit, mais 7 sains bloqués par fuite rattrapée à 30 % de bruit). Chiffres principaux et `bench/results.csv` inchangés à l'octet.
- [x] Banc d'essai v2 : gates fuités, pire cas / 5e centile, ventilation par entreprise compromise, politique D « Firebreak + prudence », limites écrites par le script (Céline). **⚠️ Chiffres publiés changés le 11/10** (toutes les entreprises tirées + 10 % de réceptions hors fédération) : p=0 → Firebreak 9,6 sains bloqués contre 43,2 pour B (4,5× moins), rappel 100 % contre 98,5 %, 0 action irréversible fuitée ; p=0,3 → rappel C 93,4 %, D 97,9 %. `docs/bench-results.md`, `docs/fiche-defense.md`, l'exemple de `docs/api.md` et `tests/test_compare.py` sont à jour ; `/api/compare` lit le CSV.
- [x] Effet waouh « Avec vs sans Firebreak » : écran coupé en deux (bouton « Avec vs sans » + étape 3 de la démo), `/api/compare`, banc d'essai de Céline, cas JLR et CDK sourcés (Yann).
- [x] Fusion Avalanche dans `main` (Yann, 02 h 30). Reste à Mika : bug `read_audit_anchor` (statut `unreadable`, 3 tentatives) et mesures réelles dans `docs/avalanche/pitch.md`, directement sur `main`.
- [x] Déploiement Vercel de l'interface et de l'API (Yann) : https://firebreak-zeta.vercel.app, `vercel deploy --prod` depuis la racine.
- [x] Scénarios qualité dans les deux sens (Mika) : lot suspect sans blacklister le fournisseur, analyse de rappel depuis un produit fini, signalement qualité signé vers l'amont avec décision au cas par cas ; scénarios `lot` et `recall`, API (`docs/api.md`), panneau de debug, ancrage Avalanche. Validé sur la vraie L1 (25 preuves, 0 échec). 295 tests verts.
- [x] Afficher le parcours qualité (`lot`, `recall`) dans l'interface finale `/app/` (Yann) : gestes guidés dans le dock (« Étape 2/6 · Distributeur »), tiroir d'analyse de rappel, levée du lot ; « Avec vs sans » masqué sur ces scénarios (pas de déclaration à comparer).
- [x] Refonte visuelle de `/app/` en registre keynote (Yann) : noir, horizon granuleux, sans boîtes, Geist, nouveau logo ; `design.md` réécrit.
- [ ] Envoi des ancrages en parallèle par entreprise pour vider la file plus vite sur la vraie L1 (Mika, pc2).
- [ ] Gel du code à 10 h : tag `demo-freeze` (Yann).
- [ ] Pitch et slides (s'appuyer sur `docs/benchmark-firebreak.md`).
- [ ] Notion : inviter les 3 coéquipières et coéquipiers avec accès en modification (à faire à la main via Partager).

## Décisions

- 11/10 05 h 55 (Yann) : pour redéployer sur Vercel quand le dernier commit n'est pas de Yann (sinon Vercel le bloque) : `git archive HEAD | tar -x -C <dossier>`, copier `.vercel/` dedans, puis `vercel deploy --prod` depuis ce dossier. Rappel : sur Vercel l'état vit en mémoire par instance ; un parcours en plusieurs étapes peut se perdre si deux requêtes tombent sur deux instances, d'où la démo en local en priorité.
- 11/10 04 h 50 (Yann) : nouveau design de l'interface, à reprendre dans les slides : fond noir `#050506`, le sain en blanc neutre, corail = bloqué, ambre = reprise, bleu `#6e95ff` = preuve ; police Geist ; logo = grille de points coupée par une barre. Tout est dans `design.md`.
- 11/10 03 h 45 (Mika) : on ne blackliste pas un fournisseur pour un problème qualité : on isole le lot en cause, au cas par cas, sur décision humaine ; les alertes vont dans les deux sens (vers l'aval : alertes signées ; vers l'amont : signalements qualité signés).

- 11/10 04 h 00 (Yann) : messagerie lisible. À l'affichage, l'agent résume chaque message en 1 à 3 phrases simples. À l'envoi, message court et humain, en phrases construites ; les termes techniques sont permis s'ils restent synthétiques, mais pas d'inventaire de chemins, routes ou identifiants (les détails vont dans docs/). Voir AGENTS.md, section Messagerie.
- 11/10 03 h 50 (Céline) : Track 3 validé par l'organisation. Calendrier : premier pitch à 12 h, finale plus tard dans la journée pour les finalistes.

- 11/10 03 h 30 (Céline) : chiffres de chaîne cités = ceux de la vraie L1 (≈ 2 s par preuve, 12 ancrages en ≈ 24 s), annoncés « mesurés sur notre démo » ; on dit « un seul validateur en démo, les membres du consortium en production » ; la ligne « actions irréversibles à p=0,3 » passe de la diapo Preuve à la diapo Limites.

- 11/10 02 h 50 (Céline) : le pitch assume la blockchain. `docs/pitch-firebreak.md` (question 8, diapos 4 et 7, déroulé de la démo aligné sur les 5 gestes de `/app/` et sur 193 opérations), `docs/firebreak.md`, `docs/benchmark-firebreak.md`, `docs/api.md` (limite du journal → ancrage Avalanche), README : « les règles décident, l'IA explique, la blockchain prouve ». TradeLens : arrêt annoncé fin 2022, fermeture début 2023.

- 11/10 02 h 50 (Yann) : interface + API déployées sur Vercel : **https://firebreak-zeta.vercel.app** (fonction Python unique `api/index.py`, IA simulée, chaîne off). Plan de secours de la démo si le portable lâche. État en mémoire par instance : faire « Réinitialiser » avant la démo.
- 11/10 02 h 30 (Yann) : la partie Avalanche de Mika (`mika/avalanche-l1`) est **fusionnée dans `main`** (267 tests verts). Désactivée par défaut (`FIREBREAK_CHAIN=off`), contrat déployé sur la L1 de test (`contracts/deployments/l1.json`). Contrat API 1.4.0. Les branches `mika/*` sont intégrées : on repart tous de `main`.
- 11/10 (Yann) : interface finale en HTML/CSS/JS natif dans `web/app/`, servie par l'API sur `/app/` (pas de Node, pas de build, polices auto-hébergées). Contrat API 1.3.0 : ajout de `truth.ids` à `/api/compare`.
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
- [x] Confirmer le passage officiel Track 1 → Track 3 auprès des organisateurs : validé par l'organisation (confirmé par Céline le 11/10, la note manquait)