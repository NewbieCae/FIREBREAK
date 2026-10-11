# finswag — FIREBREAK

Dépôt privé du projet finswag, Team 14 au hackathon Secure Horizons, Track 3 « Uncharted Frontiers » (projet FIREBREAK, pare-feu des supply chains).

## Le pitch en 3 lignes

Quand un partenaire d'une supply chain est compromis, FIREBREAK met en
quarantaine **uniquement les opérations contaminées** — trouvées par un
graphe de dépendances aux règles vérifiables — laisse tourner le reste,
et propage des alertes signées aux partenaires sans divulguer leurs
données commerciales. L'IA n'explique que des décisions déjà prises par
les règles — elle ne bloque rien.

## Architecture

- `src/firebreak/` — moteur : `engine.py` (registres + propagation BFS,
  seeds par origine/fenêtre ou jetons d'alerte, règles `verified`/`released`),
  `federation.py` (alertes Ed25519 à jetons opaques), `simulation.py`
  (point fixe + timeline), `audit.py` (journaux chaînés par hash),
  `scenario.py` (4 scénarios : mixed / rib / cert / asn),
  `ingest/` (documents fournisseurs + EPCIS 2.0), `ai.py`
  (mock déterministe, Bedrock en option avec repli mock), `api.py` (FastAPI).
- `web/app/` — **interface finale** (salle de contrôle, HTML/CSS/JS sans build), servie sur `/app/` ; design dans [design.md](design.md).
- `web/index.html` — dashboard de debug (Cytoscape, rejeu pas à pas,
  pilotage démo au clic ou flèche droite).
- `tests/` — suite pytest (moteur, fédération, scénarios, timeline, démo).
- `docs/` — [produit](docs/firebreak.md), [contrat API](docs/api.md),
  [script de démo](docs/demo.md), [plan](docs/plan.md),
  [benchmark](docs/benchmark-firebreak.md), [brief de l'interface](docs/brief-ui.md).

## Lancer la démo

```bash
bash scripts/demo.sh        # uv sync → serveur :8000 → navigateur
uv run pytest -q            # tests
uv run python -m firebreak.demo_figures   # les chiffres du pitch (reproductible)
```

Interface : http://localhost:8000/app/ — dashboard de debug : http://localhost:8000 — API interactive : http://localhost:8000/docs.

Secrets : voir `.env.example` (jamais de vraie clé dans le dépôt). Sans configuration, les clés de signature et les jetons de la fédération sont aléatoires à chaque lancement.

Variables : `FIREBREAK_DEMO=1` (scénario figé, IA mock, cadence de rejeu) ;
`FIREBREAK_AI=bedrock` + `AWS_REGION` + identifiants AWS pour l'explainer
Bedrock ([détails](docs/api.md#ia--bedrock-et-repli-mock)).

## Coordination d'équipe

- [goal.md](goal.md) (objectif et avancement partagés),
  [sessions/](sessions/) (une session par membre), protocole dans
  [AGENTS.md](AGENTS.md).
- [Page Notion — brief et coordination](https://app.notion.com/p/3f58c3ea1f5e81e88164e25c35e8475e)

Le brief prévoit AWS Bedrock et Avalanche Fuji. Le produit retenu est FIREBREAK (voir `goal.md`).
