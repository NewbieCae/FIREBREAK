# Messages — finswag / FIREBREAK

> Le groupe de discussion de l'équipe, dans le dépôt. Chaque message est livré à son destinataire au prochain tour de son agent (hook `team-sync.sh`) et, chez ceux qui ont le cron, dans la minute.
>
> Envoyer : `python3 scripts/messages.py send tous "ton message"` (ou `yann`, `celine`, `maria`, `mika`, ou plusieurs séparés par des virgules). Le script commite et pousse tout seul.
> On n'édite jamais un message existant ; on en ajoute un en dessous. Format d'un en-tête : `### <de> → <à> · AAAA-MM-JJ HH:MM:SS`.

### yann → tous · 2026-10-11 00:05:00
Wesh la team, bienvenue sur FIREBREAK 🔥

Vous lisez ça parce que votre agent vient de pull le repo. À partir de maintenant, le repo c'est notre groupe WhatsApp. On ne se cherche pas sur Discord, on se parle ICI, et nos agents font le facteur.

Comment on bosse, en 5 règles, pas une de plus :

1. ON POUSSE TOUT SUR MAIN. Zéro branche, zéro pull request. Petits commits, souvent. Chaque vraie itération = pull au début, push à la fin. Avec Claude Code ou Devin c'est automatique (hook `scripts/team-sync.sh`). Avec Codex ou à la main : `bash scripts/team-sync.sh sync` à la fin de chaque itération, pas de négociation.

2. TON AGENT SAIT QUI TU ES. S'il ne sait pas, il te demande ton prénom et fait `git config finswag.member <prenom>`. Une fois, c'est réglé.

3. TU PARLES À L'ÉQUIPE DANS `messages.md`. Dis à ton agent « envoie un message à Yann : ... » ou « dis à tous que ... ». Il lance `python3 scripts/messages.py send tous "..."`, et chacun le reçoit au prochain tour de son agent. Moi je le reçois dans la minute, j'ai un cron qui veille.

4. `goal.md` C'EST LE TABLEAU DE BORD, `sessions/<toi>.md` C'EST TON JOURNAL. Avant de prendre une tâche, tu mets ton prénom dessus dans `goal.md` et tu pousses direct. Comme ça personne ne fait deux fois le même truc.

5. CONFLITS : ton agent arbitre. Il rebase, il garde les deux versions, il lance `uv run pytest -q`. Vert, il pousse. JAMAIS de `git push --force`. C'est la seule façon de perdre le taf d'un autre, donc c'est non.

Où on en est : moteur livré, 147 tests verts, démo avec des vrais chiffres (17 opérations bloquées sur 145, 5 210 € de fraude stoppée, 80 402 € qui continuent). Il reste l'interface, le script de démo et le pitch. Rendu dimanche 12 h, gel du code à 10 h.

Réponds à ce message via ton agent pour que je sache que t'es branché. Let's go. 🚀

### yann → tous · 2026-10-11 00:10:29
Test de la messagerie : si ton agent t'affiche ça, c'est que ça marche. Réponds avec : python3 scripts/messages.py send yann "reçu"

### celine → yann · 2026-10-11 00:42:52
Banc d'essai v2 poussé : les chiffres changent. Entreprise compromise tirée parmi les 5, plus une politique D. p=0 : Firebreak bloque 9,6 sains contre 43,2 pour B, rappel 100 % contre 98,5 %, 0 action irréversible fuitée. J'ai mis à jour test_compare.py (43,2 / 9,6 / 0,985) et l'exemple bench de docs/api.md ; /api/compare lit le CSV, rien à changer côté code. Détails : docs/bench-results.md
