# finswag

Dépôt privé du projet finswag, Team 14 au hackathon Secure Horizons, Track 1 « Guardians of Value » (Fintech Security).

- [Page Notion — brief et coordination](https://app.notion.com/p/3f58c3ea1f5e81e88164e25c35e8475e)
- [Brief et ressources](docs/brief.md)
- [Piste FIREBREAK — pare-feu des supply chains (Track 3)](docs/firebreak.md)
- [Benchmark des concurrents FIREBREAK](docs/benchmark-firebreak.md)
- [Plan de build en 6 étapes](docs/plan.md)
- [Contrat de l'API FIREBREAK](docs/api.md)

## Lancer le projet

Prérequis : Python 3.12 ou plus et [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                                  # installe les dépendances
uv run uvicorn firebreak.api:app --reload --port 8000    # lance le serveur
uv run pytest -q                                         # lance les tests
```

- Dashboard de debug : http://localhost:8000
- Documentation interactive de l'API : http://localhost:8000/docs
- Contrat détaillé : [docs/api.md](docs/api.md)
- IA : simulée par défaut ; `FIREBREAK_AI=bedrock` + `AWS_REGION` + identifiants AWS pour Bedrock ([détails](docs/api.md#ia--bedrock-et-repli-mock)).

## Organisation

- `src/firebreak/` : moteur FIREBREAK (graphe, fédération, scénario, API).
- `tests/` : tests pytest.
- `web/` : dashboard de debug.
- `assets/` : ressources du projet.
- `scripts/` : scripts utilitaires.
- `docs/` : documentation.

Le brief prévoit AWS Bedrock et Avalanche Fuji. Le produit, la stack détaillée et la répartition des rôles restent à valider.
