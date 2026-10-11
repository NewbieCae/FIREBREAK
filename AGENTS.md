# Contexte du projet finswag

## Protocole d'équipe — À LIRE PAR TOUT AGENT QUI OUVRE CE DÉPÔT

Quatre personnes travaillent en même temps sur ce dépôt, chacune avec son agent (Claude Code, Devin, Codex…) : **Yann, Céline, Maria, Mika**. Tout le monde travaille directement sur `main`. La communication passe par trois fichiers versionnés :

| Fichier | Rôle | Qui l'écrit |
|---|---|---|
| `goal.md` | Objectif commun, avancement du plan, prochaines actions, décisions, blocages | Tout le monde |
| `sessions/<membre>.md` | Ce que chaque membre a fait, fait maintenant, fera ensuite, et ce dont il a besoin | Uniquement l'agent de ce membre |
| `docs/plan.md` | Plan de build en 6 étapes et handoffs | Mis à jour quand le plan change |
| `messages.md` | Messagerie de l'équipe : on se parle à travers le dépôt | Tout le monde, via `scripts/messages.py send` |

### Qui suis-je ?

Le membre est identifié par `scripts/team-sync.sh whoami`. Il regarde, dans cet ordre : la variable `FINSWAG_MEMBER`, puis `git config finswag.member`, puis l'e-mail et le nom Git. S'il ne trouve personne, **demande à l'utilisateur son prénom**, puis lance `git config finswag.member <yann|celine|maria|mika>`.

### À chaque itération (obligatoire)

1. **Au début** : se synchroniser (`git fetch && git rebase --autostash @{u}`), lire `goal.md` et sa propre session. Regarder les sessions des autres avant de toucher une zone partagée.
2. **Pendant** : avant de prendre une tâche de `goal.md`, mettre son prénom dessus (`- [ ] … (Maria)`) et pousser tout de suite, pour qu'il n'y ait pas deux personnes sur la même tâche.
3. **À la fin de chaque vraie itération, avant de rendre la main** (règle de Yann du 11/10 : **pull au début, push à la fin, à chaque fois, pour tout le monde**) :
   - mettre à jour `sessions/<membre>.md` : « Où j'en suis », « En cours », « Prochaine étape », « Besoin des autres », plus une ligne datée en haut du « Journal » ;
   - mettre à jour `goal.md` : cocher ce qui est fini, ajuster le tableau d'avancement, ajouter les décisions et les blocages ;
   - commit puis push sur `main` (`scripts/team-sync.sh sync` le fait, avec un garde-fou contre les secrets).
4. **Ne jamais modifier la session d'un autre membre.** Dans `goal.md`, ne changer que les lignes concernées. En cas de conflit Git, garder les deux contributions.

### Le hook automatique

`.claude/settings.json` branche `scripts/team-sync.sh` sur Claude Code et sur Devin CLI. Devin lit aussi les hooks de `.claude/`.

- **Début de session et chaque message** : pull, et rappel du membre et du protocole.
- **Fin de tour** : si du code a changé sans que `sessions/<membre>.md` et `goal.md` aient été mis à jour, le hook demande à l'agent de les mettre à jour (une seule fois). Ensuite il commite, se rebase sur `origin/main` et pousse. S'il trouve un secret, il ne commite pas. En cas de conflit avec un coéquipier, il ne pousse pas et l'indique.
- **Codex et les autres agents sans hooks** appliquent ce protocole à la main et terminent chaque itération par `bash scripts/team-sync.sh sync`.

### Règles communes

- Lire `goal.md`, `docs/firebreak.md` et `docs/plan.md` avant de coder. Le contrat de l'API est dans `docs/api.md` : on ne casse pas un endpoint existant.
- `uv run pytest -q` doit rester vert avant chaque push.
- Aucun secret dans le dépôt : les clés vont dans `.env.local`, qui est ignoré.

### Messagerie — `messages.md`, on se parle à travers le dépôt

- **Lire** : à chaque tour, le hook `team-sync.sh start` livre à l'agent les messages non lus adressés au membre (`tous` ou son prénom). L'agent les **résume en tête de réponse**, avant tout le reste : « De Mika (03:57) : » puis 1 à 3 phrases en français courant sur ce qui change et ce qu'on attend de l'utilisateur. Pas de citation brute, pas de chemins de fichiers, de routes d'API, d'identifiants ni de jargon. Sans hook (Codex, humain) : `python3 scripts/messages.py deliver` en début d'itération.
- **Écrire** : quand l'utilisateur dit « envoie un message à Maria », « dis à tous que… », « demande à Yann… », l'agent lance `python3 scripts/messages.py send <tous|yann|celine|maria|mika> "texte"`. Le script commite et pousse tout seul. Plusieurs destinataires : `yann,mika`. **Le message est court et lisible par un humain** : des phrases simples, l'essentiel seulement (ce qui est fait, ce qu'on attend de l'autre). Pas de chemins de fichiers, de routes d'API, d'identifiants ni de listes techniques : les détails vont dans `docs/`, au besoin le message dit juste où regarder.
- **Jamais d'édition d'un message existant.** Le fichier est en `merge=union` (`.gitattributes`) : deux personnes qui ajoutent en même temps ne créent pas de conflit.
- **Chez Yann** un cron (`python3 scripts/messages.py poll`) vérifie toutes les minutes et notifie sur le bureau. Chacun peut installer le même : `crontab -e` puis `* * * * * cd <dépôt> && python3 scripts/messages.py poll`.

### Conflits Git — pas de branches, l'agent arbitre

Décision du 11/10 : tout le monde pousse sur `main`, pas de branches ni de pull requests. Les conflits sont résolus par l'agent de celui qui pousse en second.

- **Éviter le conflit plutôt que le résoudre.** Chacun travaille dans sa zone (moteur dans `src/firebreak/`, interface dans son dossier). Deux personnes sur le même fichier en même temps, c'est là que ça casse. Pousser souvent, par petits commits : un conflit de 3 lignes se règle seul, un conflit de 200 lignes après 2 h sans pousser, non.
- **Fichiers partagés (`goal.md`, `docs/`)** : on ajoute des lignes, on ne réécrit pas. En cas de conflit, on garde les deux contributions.
- **Quand le hook dit « conflit, pas poussé »** : demander à son agent de faire `git fetch && git rebase @{u}`, résoudre, lancer `uv run pytest -q`, puis pousser. Tests verts = fusion bonne. Tests rouges = fusion ratée, pas forcément le code.
- **L'agent ne tranche pas seul** quand ce n'est pas un conflit de texte mais un choix produit : deux versions d'une même fonction, ou un changement d'endpoint dans `docs/api.md` que l'interface utilise. Il pose la question, on décide à deux.
- **Jamais de `git push --force`** sur `main`. C'est la seule manière de perdre le travail d'un autre.
- Le root reste propre : chaque fichier va dans le bon dossier (`docs/`, `assets/`, `scripts/`, `src/`, `tests/`, `web/`).

## Notion — état actuel

Une page Notion « finswag » sert au cadrage et à la coordination (privée). Les invitations des coéquipiers et les coordonnées de contact ne sont **pas** conservées dans ce dépôt : elles restent dans Notion ou dans la boîte de l'équipe. Réutiliser la page existante ; ne pas en créer une nouvelle.

Le brief des organisateurs est résumé dans `docs/brief.md`. Les pistes A/B/C/D du brief initial sont des propositions, pas des décisions ; le produit retenu est FIREBREAK (voir `goal.md`). Le dépôt GitHub est privé.
