# Règles communes — agents qui travaillent sur la partie Avalanche

À lire en entier avant toute action. En cas de doute, ces règles l'emportent sur la fiche de tâche.

## Contexte

- Dépôt : `finswag` (projet FIREBREAK, hackathon). Lis `docs/firebreak.md`, puis `docs/avalanche/README.md`, puis ta fiche de tâche.
- Le moteur (`engine.py`, `federation.py`, `simulation.py`, `scenario.py`, `audit.py`) appartient à Yann. **Tu ne le modifies pas**, sauf si ta fiche le demande explicitement, et alors au minimum strict.
- Le contrat de l'API est dans `docs/api.md` : **on ajoute, on ne retire ni ne renomme rien.**

## Git

- Tu travailles **uniquement** sur la branche `mika/avalanche-l1`. Vérifie avec `git branch --show-current` avant de commencer et avant chaque commit.
- Au début : `git fetch origin && git rebase origin/main`. En cas de conflit dans `uv.lock`, reprends la version de `origin/main` puis relance `uv lock`. Pour tout autre conflit, garde les deux contributions ; si c'est un choix produit, arrête-toi et signale-le.
- Petits commits, message en français, préfixe `chain:` (ex. `chain: contrat FirebreakRegistry + tests`).
- **Interdit** : `git push --force`, pousser sur `main`, modifier `sessions/` d'un autre membre, modifier `AGENTS.md`, `.claude/`, `messages.md`. Ne pousse la branche que si la fiche le demande.
- N'utilise pas `scripts/team-sync.sh` ni `scripts/messages.py` : ils poussent sur `main`.

## Secrets

- **Ne lis jamais, n'affiche jamais, ne copie jamais** : `.env`, `.env.local`, tout fichier du dossier `L1 blockchain/`, toute variable `*MNEMONIC*`, `*PRIVATE_KEY*`, `*KEY_SEED*`, `*PAIR_SECRET*`.
- Le code lit ces valeurs depuis l'environnement ; il ne les journalise jamais, ne les met dans aucune réponse d'API, aucun message d'erreur, aucun test.
- Dans les tests : mnémonique de test public de Hardhat/Foundry (`test test test test test test test test test test test junk`) uniquement.
- Avant chaque commit : `git diff --cached` ne doit contenir ni clé privée, ni mnémonique réel, ni URL RPC contenant un jeton d'API.

## Code

- Python 3.12, `uv`. Lancer : `uv run pytest -q`. **Tous les tests doivent rester verts**, y compris ceux des autres.
- Textes visibles par l'utilisateur en français ; code, identifiants, noms de fichiers en anglais.
- Nouvelle dépendance : seulement celles listées dans ta fiche, version stable publiée depuis au moins 7 jours, ajoutée avec `uv add`.
- `FIREBREAK_CHAIN=off` par défaut : avec ce réglage, aucun module réseau (`web3`) n'est importé et le comportement de l'API est strictement identique à `main`.
- Aucun appel réseau dans les tests. La vraie L1 n'est touchée que par les scripts `scripts/chain_*.py` lancés à la main.

## Machine Windows de Mika (`mika/pc1`)

Constaté le 11/10 à 01 h : sans ces réglages, des tests échouent sur Windows alors qu'ils passent sous Linux.

- `uv` est dans `~/.local/bin` : commencer chaque commande par `export PATH="$HOME/.local/bin:$PATH"`.
- Le venv du projet est `finswag/.venv` en **Python 3.12** (sans précision, uv choisit 3.15). En cas de recréation : `uv sync --python 3.12`.
- **`PYTHONUTF8=1`** obligatoire : sinon `scripts/bench.py` plante sur la console cp1252.
- **`tzdata`** manque sous Windows (`ZoneInfo("Europe/Paris")` introuvable). Il est installé à la main dans le venv : lancer les tests avec `uv run --no-sync`, car un `uv sync` le supprime. Correction propre proposée : dépendance `tzdata; sys_platform == "win32"` dans `pyproject.toml` (à valider avec Yann, ça touche le lock de toute l'équipe).
- Commande de test sur cette machine : `PYTHONUTF8=1 uv run --no-sync pytest -q` → 213 verts au 11/10 01 h.
- `py-evm` ne publie que des versions bêta (`0.12.1b1`) et `eth-tester` en dépend : exception admise à la règle « versions stables », pour le groupe dev uniquement. Préférer la dernière version **non bêta** d'`eth-tester` qui résout.

## Fin de tâche

1. `uv run pytest -q` vert (colle le résumé dans ton rapport).
2. Docs mises à jour si ta fiche le demande (`docs/api.md`, `docs/avalanche/README.md`).
3. Commit sur `mika/avalanche-l1`.
4. Rapport final court : ce qui est fait, ce qui ne l'est pas, ce que la tâche suivante doit savoir, et toute hypothèse prise.
