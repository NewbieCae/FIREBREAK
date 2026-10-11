# FIREBREAK — le pare-feu des supply chains

Secure Horizons 2026 · Team 14 · Track 3 « Uncharted Frontiers ».

> Quand un partenaire d'une chaîne d'approvisionnement est compromis, on isole **ce qui est contaminé**, pas toute l'activité.

## Le problème

Les entreprises d'une même chaîne échangent des données en continu : commandes, stocks, avis d'expédition, certificats, factures. Si l'une d'elles est compromise, elle peut injecter de fausses données chez ses partenaires. Ceux-ci n'ont aujourd'hui que deux options : tout couper avec elle et paralyser l'activité, ou continuer et laisser passer l'attaque.

Si une attaque touche 3 commandes sur 100, pourquoi geler les 100 ?

## Ce que fait FIREBREAK

1. **Provenance** : chaque entreprise enregistre qui dépend de quoi, dans un graphe de dépendances.
2. **Déclaration** : une source est déclarée compromise à partir d'une date.
3. **Quarantaine ciblée** : seules les opérations qui en dépendent, directement ou non, sont mises en quarantaine ; le chemin exact dans le graphe est affiché.
4. **Alertes signées** (Ed25519) entre partenaires, avec des jetons opaques : aucune donnée commerciale ne circule. Chaque acteur ne voit que son registre et les alertes reçues.
5. **Un humain libère** une quarantaine ; les décisions sont inscrites dans des journaux chaînés par hachage.

Les règles décident ; l'IA explique des décisions déjà prises (elle ne bloque rien).

## Architecture

- `src/firebreak/` : moteur. `engine.py` (registres et propagation sur le graphe), `federation.py` (alertes signées, jetons opaques), `simulation.py` (point fixe et timeline), `audit.py` (journaux chaînés), `scenario.py` (six scénarios : `mixed`, `rib`, `cert`, `asn`, `lot`, `recall`), `ingest/` (documents fournisseurs, EPCIS 2.0), `ai.py` (simulée par défaut, Bedrock en option), `api.py` (FastAPI), `chain/` (ancrage optionnel des empreintes sur une L1 Avalanche, désactivé par défaut).
- `contracts/` : contrat `FirebreakRegistry.sol` (empreintes d'alertes, d'accusés, de déclarations et de journaux). Voir `docs/avalanche/`.
- `web/app/` : interface finale (salle de contrôle, sans étape de build), servie sur `/app/`. `web/index.html` : tableau de bord de débogage.
- `scripts/bench.py` et `src/firebreak/synth.py` : banc d'essai (simulateur de mondes aléatoires, quatre politiques comparées).
- `tests/` : suite pytest.
- `docs/` : [produit](docs/firebreak.md), [contrat API](docs/api.md), [script de démo](docs/demo.md), [résultats du banc d'essai](docs/bench-results.md), [fiche de défense](docs/fiche-defense.md), [pitch](docs/pitch-firebreak.md), [benchmark du marché](docs/benchmark-firebreak.md).

## Installation et lancement

Prérequis : Python 3.12 ou plus et [uv](https://docs.astral.sh/uv/).

```bash
git clone <ce dépôt> && cd FIREBREAK
uv sync                                    # installe les dépendances
bash scripts/demo.sh                       # lance le serveur de démo (port 8000) et ouvre le navigateur
uv run pytest -q                           # tests
uv run python -m firebreak.demo_figures    # les chiffres de la démo (reproductibles)
uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3   # banc d'essai (environ une minute)
```

- Interface : http://localhost:8000/app/ · tableau de bord de débogage : http://localhost:8000 · API interactive : http://localhost:8000/docs.
- La démo n'a besoin d'aucun secret ni d'aucun réseau (IA simulée, chaîne désactivée).
- Variables optionnelles, à placer dans `.env.local` (ignoré par Git) : voir `.env.example`. Jamais de vraie clé dans le dépôt. Sans configuration, les clés de signature et les jetons de la fédération sont aléatoires à chaque lancement.

## Résultats mesurés (simulateur)

500 mondes aléatoires, 5 entreprises, 300 opérations par monde. Source unique : [docs/bench-results.md](docs/bench-results.md). A : alerte seule. B : blocage du fournisseur et de ses clients directs. C : FIREBREAK.

| | A | B | C (FIREBREAK) |
|---|---|---|---|
| Opérations saines bloquées à tort, dépendances toutes tracées | 0 | 43,2 | **9,6** |
| Mondes avec une fuite, dépendances toutes tracées | 100 % | 24,6 % | **0 %** |
| Rappel quand 30 % des dépendances sont invisibles | 0 % | 98,5 % | 93,4 % |
| Mondes où une action irréversible contaminée passe, 30 % invisibles | 100 % | 5,0 % | 28,4 % |

Démo (scénario `mixed`, commande `demo_figures`) : 17 opérations bloquées sur 193, 4 actions irréversibles bloquées, 5 210 € de paiement frauduleux bloqués, 92 102 € qui continuent.

## Limites connues

- **Tout est simulé.** Les chiffres décrivent notre modèle de supply chain, pas une entreprise réelle. Aucun client n'a validé le besoin.
- **FIREBREAK ne voit que les dépendances enregistrées.** Quand 30 % sont invisibles, le rappel tombe à 93,4 % et 28,4 % des mondes laissent passer au moins une action irréversible contaminée : c'est un compromis, pas une victoire sur toute la ligne.
- **Règle d'origine prudente.** Même avec toutes les dépendances tracées, FIREBREAK bloque en moyenne 9,6 opérations saines par monde : toute donnée attribuée à l'entreprise compromise après la date déclarée est mise en quarantaine.
- **Le déclencheur est une déclaration ou une alerte reçue.** Nous contenons une compromission, nous ne la détectons pas ; le temps de détection n'est pas mesuré.
- **La politique D (« FIREBREAK + prudence »)** du banc d'essai est une borne haute : elle suppose qu'un envoi non tracé laisse toujours une trace visible.
- **L'IA est simulée par défaut** ; aucune mesure de son effet n'est présentée.
- **L'ancrage sur L1 Avalanche est optionnel** et prouve seulement qu'une preuve n'a pas été modifiée, pas que la décision était juste.
- Les chiffres de marché cités dans les documents viennent de sources secondaires.

## Équipe

Team 14 : Yann, Céline, Maria, Mika. Coordination des agents : [goal.md](goal.md), [sessions/](sessions/), protocole dans [AGENTS.md](AGENTS.md).
