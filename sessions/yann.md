# Session — Yann

> Mis à jour par l'agent de Yann à chaque itération. Le plus récent en haut du journal.

## Où j'en suis

Le moteur FIREBREAK est livré (6 étapes du plan) et **l'interface finale aussi** : `web/app/` (HTML/CSS/JS natif, sans build), servie sur `http://localhost:8000/app/`, ouverte par `bash scripts/demo.sh`. Tous les écrans du brief : carte vivante, propagation SSE, chiffres animés, fil, preuve, cascade de levée, fausse alerte, avec vs sans, journal d'audit, import de documents et EPCIS, vue partenaire étanche, preuves Avalanche (si `FIREBREAK_CHAIN` actif), les 5 gestes à la flèche droite. Testée dans Chrome en 1440×900 et 1920×1080 sur les 4 scénarios ; relecture indépendante faite, ses 12 défauts corrigés. 267 tests verts.

## En cours

- Répétition de la démo sur l'interface finale.

## Prochaine étape

- Gel à 10 h (tag `demo-freeze`), puis répétition jusqu'à 12 h.

## Besoin des autres

- Maria : quand elle reprend la main, tester l'interface sur Windows en 1920×1080 (`git pull`, redémarrer le serveur, ouvrir `/app/`) et remonter chaque défaut via `messages.md`.

## Journal

- **11/10 04 h 05** — Règle messagerie précisée : termes techniques permis s'ils sont synthétiques et dans une phrase construite ; seul l'inventaire brut (listes de chemins, routes, identifiants) est banni.
- **11/10 04 h 00** — Messagerie : les messages d'équipe sont désormais résumés en français courant à l'affichage (plus de citation brute), et les messages envoyés doivent être courts, sans chemins, routes ni identifiants. Règle dans AGENTS.md et dans le hook `team-sync.sh`.
- **11/10 03 h 55** — Revue de l'UI de Maria (branche `origin/Maria-UI`, `web/ui/`, commit dd0a8b9) : extraite hors dépôt et servie sur localhost:5173, API démo sur :8000. Rien de fusionné dans main.
- **11/10 02 h 50** — Déploiement Vercel : https://firebreak-zeta.vercel.app (firebreak.vercel.app était pris). `api/index.py` enveloppe FastAPI et restaure le chemin d'origine (Vercel réécrit tout vers la fonction et perd le chemin ; il passe par `?__path=`). `vercel.json`, `.vercelignore`, `requirements.txt` exporté d'uv. Vérifié : /app/, polices, state, compromise, SSE, explain, compare, samples.
- **11/10 02 h 25** — Interface finale terminée : preuves Avalanche (pastille, liste des ancrages, journal « ancré, bloc N », falsification simulée détectée), 12 défauts de la relecture corrigés (animation interrompue par Réinitialiser, tiroir fermé atteignable au clavier, double clic, flèche → déduite de l'état, vue partenaire sans fuite par le clavier ni les onglets d'audit, imports robustes). Mode allégé automatique si les images ralentissent. `team-sync.sh` : plus de rebase quand l'amont est déjà dans HEAD (la fusion Avalanche était aplatie en conflits et bloquait tous les pushs).
- **11/10 02 h 30** — Fusion de `mika/avalanche-l1` dans `main` sans conflit (ancrage des alertes sur Avalanche L1, off par défaut). `uv sync`, 267 tests verts. Test flaky `test_alerts_carry_only_opaque_tokens` corrigé (jetons exclus de la recherche de fuite). `api.py` en version 1.4.0, aligné sur `docs/api.md`.
- **11/10 02 h 05** — Interface finale `web/app/` : salle de contrôle verre/aurore, logo animé, 40 icônes custom, carte + particules, propagation SSE, preuve, cascade de levée, avec vs sans, audit, import, vue partenaire. API 1.3.0 (ajouts seulement) : `truth.ids` dans `/api/compare`, `/app/` et `/samples/` servis. Dark Reader neutralisé (`darkreader-lock`).
- **11/10 00 h 40** — Brief de l'interface finale : `docs/brief-ui.md` (direction artistique verre/sombre, logo, icônes custom, mouvement, 8 écrans, intégration API, démo en 5 gestes).
- **11/10 01 h 00** — `team-sync.sh` ne commite ni ne pousse plus un conflit non résolu (demande de Céline après les marqueurs poussés dans README.md, commit d8054d9) : fichiers « unmerged » vérifiés avant `git add`, marqueurs `<<<<<<<` / `>>>>>>>` en tête de ligne refusés, contrôle aussi avant push et au début de chaque tour. 43 assertions vertes sur dépôts jetables.
- **11/10 00 h 30** — « Avec vs sans Firebreak » : `/api/compare` (même définition que le banc de Céline), écran coupé en deux, étape 3 de la démo. Scénario enrichi d'un après-midi réaliste au fabricant (40 opérations saines) : sans Firebreak 54 bloquées dont 42 saines + 5 fuites ; avec, 17 / 0 / 0.
- **11/10 01 h 15** — Messagerie d'équipe : `messages.md` (message de bienvenue à tous), `scripts/messages.py` (send / deliver / poll), livraison des messages non lus par le hook à chaque tour, cron chaque minute chez moi. Règles de conflits et pull/push obligatoires dans `AGENTS.md`.
- **11/10 00 h 10** — Étape 6 livrée : mode démo, `/api/demo/step` (5 clics), `docs/demo.md` avec chiffres reproductibles, `scripts/demo.sh`, test de bout en bout, `/api/state` en 28 ms.
- **10/10 23 h 45** — Étape 4 livrée : `/api/timeline`, flux SSE `/api/events`, bouton « Rejouer » animé, compteurs d'euros. Corrigé un triple comptage : seuls les paiements comptent (5 210 € bloqués, 80 402 € continuent).
- **10/10 20 h 30** — Structure d'équipe : `goal.md` partagé, une session par membre, protocole et hook de synchronisation (pull au début, mise à jour des sessions et de `goal.md`, push à la fin).
- **10/10 20 h 10** — Étape 3 livrée (scénarios rib/cert/asn/mixed, généalogie des lots, import EPCIS 2.0). 138 tests verts.
- **10/10 19 h** — Étapes 1, 2 et 5 livrées (API figée + `docs/api.md`, levée de quarantaine signée et journal d'audit, Bedrock + lecture de documents).
- **10/10 18 h 40** — Premier socle FIREBREAK + plan en 6 étapes (`docs/plan.md`).
- **10/10 après-midi** — Idée FIREBREAK (`docs/firebreak.md`), benchmark des concurrents (`docs/benchmark-firebreak.md`).
- **10/10 matin** — Dépôt GitHub privé, invitations GitHub (NewbieCae, mncodol, magraku), page Notion, brief (`docs/brief.md`).

## À faire hors code

- Inviter les 3 adresses sur Notion avec accès en modification (Partager) : le connecteur ne sait pas le faire.
