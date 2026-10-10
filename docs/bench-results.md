# Banc d'essai Firebreak — résultats

> Généré par `uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3`. Ne pas éditer à la main.

500 mondes synthétiques par valeur de p (5 entreprises, 300 opérations chacun, générateur `src/firebreak/synth.py`). Dans chaque monde, une entreprise tirée au hasard parmi **toutes** (du fournisseur amont `e0` au client final `e4`) est compromise à partir d'une heure `since`. **Vérité terrain** : ses records émis après `since` et tous leurs descendants par les *vraies* dépendances, sauf les records `verified`. Le moteur ne voit que les dépendances *enregistrées* : chaque vraie dépendance (entrée d'un record ou envoi entre entreprises) est cachée avec la probabilité **p**. Un envoi caché laisse une réception sans jeton ni lien. En plus, 10% des réceptions viennent d'hors fédération : légitimes, elles aussi sans jeton, donc indiscernables dans les registres.

Entreprises compromises tirées (à p = 0) : `e0` (106), `e1` (111), `e2` (92), `e3` (96), `e4` (95).

Aucune entreprise n'est exclue du tirage.

Politiques, appliquées au même monde :

- **A — Alerte seule** : on prévient tout le monde, rien n'est bloqué.
- **B — Blocage fournisseur + partenaires** : tout record daté de `since` ou après chez l'entreprise compromise et ses clients directs est bloqué (la réponse « on coupe le fournisseur »).
- **C — Firebreak** : le moteur du dépôt (`Simulation.declare_compromise`), propagation sur le graphe enregistré + alertes signées.
- **D — Firebreak + prudence** (banc uniquement) : C, plus la quarantaine des réceptions **sans provenance enregistrée** (sans jeton ni lien) datées de `since` ou après chez les partenaires directs connus de l'entreprise compromise, et de tout ce qui en dépend dans le graphe enregistré. D exploite le signal « provenance manquante », lu uniquement dans l'état du moteur : jamais la vérité terrain ni le drapeau « dépendance cachée ».

Valeurs : moyenne ± demi-largeur de l'IC 95 % (approximation normale). « n/d » : non défini (A ne bloque rien, donc pas de précision).

## Fuites (contaminés non bloqués)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 30.4 ± 1.0 | 0.7 ± 0.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 0.1 | 30.4 ± 1.0 | 0.7 ± 0.1 | 0.8 ± 0.1 | 0.3 ± 0.1 |
| 0.2 | 30.4 ± 1.0 | 0.7 ± 0.1 | 1.6 ± 0.2 | 0.6 ± 0.1 |
| 0.3 | 30.4 ± 1.0 | 0.7 ± 0.1 | 2.5 ± 0.3 | 0.8 ± 0.1 |

## Actions irréversibles fuitées (contaminées, gate, non bloquées)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 11.10 ± 0.40 | 0.07 ± 0.03 | 0.00 ± 0.00 | 0.00 ± 0.00 |
| 0.1 | 11.10 ± 0.40 | 0.07 ± 0.03 | 0.15 ± 0.04 | 0.08 ± 0.03 |
| 0.2 | 11.10 ± 0.40 | 0.07 ± 0.03 | 0.32 ± 0.06 | 0.19 ± 0.04 |
| 0.3 | 11.10 ± 0.40 | 0.07 ± 0.03 | 0.45 ± 0.08 | 0.27 ± 0.05 |

## Dégâts collatéraux (sains bloqués)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 0.0 ± 0.0 | 43.2 ± 2.1 | 9.6 ± 0.7 | 11.7 ± 0.8 |
| 0.1 | 0.0 ± 0.0 | 43.2 ± 2.1 | 8.8 ± 0.6 | 11.9 ± 0.8 |
| 0.2 | 0.0 ± 0.0 | 43.2 ± 2.1 | 8.4 ± 0.5 | 12.5 ± 0.7 |
| 0.3 | 0.0 ± 0.0 | 43.2 ± 2.1 | 7.9 ± 0.4 | 13.0 ± 0.7 |

## Activité saine préservée

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 100.0% ± 0.0% | 83.8% ± 0.8% | 96.4% ± 0.3% | 95.6% ± 0.3% |
| 0.1 | 100.0% ± 0.0% | 83.8% ± 0.8% | 96.7% ± 0.2% | 95.5% ± 0.3% |
| 0.2 | 100.0% ± 0.0% | 83.8% ± 0.8% | 96.8% ± 0.2% | 95.3% ± 0.3% |
| 0.3 | 100.0% ± 0.0% | 83.8% ± 0.8% | 97.0% ± 0.2% | 95.1% ± 0.3% |

## Précision

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | n/d | 44.2% ± 1.3% | 78.5% ± 1.3% | 75.2% ± 1.3% |
| 0.1 | n/d | 44.2% ± 1.3% | 78.7% ± 1.1% | 74.0% ± 1.3% |
| 0.2 | n/d | 44.2% ± 1.3% | 78.3% ± 1.1% | 72.3% ± 1.2% |
| 0.3 | n/d | 44.2% ± 1.3% | 78.2% ± 1.0% | 70.8% ± 1.1% |

## Rappel

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 0.0% ± 0.0% | 98.5% ± 0.3% | 100.0% ± 0.0% | 100.0% ± 0.0% |
| 0.1 | 0.0% ± 0.0% | 98.5% ± 0.3% | 98.0% ± 0.3% | 99.4% ± 0.1% |
| 0.2 | 0.0% ± 0.0% | 98.5% ± 0.3% | 95.7% ± 0.5% | 98.6% ± 0.3% |
| 0.3 | 0.0% ± 0.0% | 98.5% ± 0.3% | 93.4% ± 0.6% | 97.9% ± 0.3% |

## Rappel : queue de distribution (moyenne / 5e centile / pire cas)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 0.0% / 0.0% / 0.0% | 98.5% / 91.2% / 72.9% | 100.0% / 100.0% / 100.0% | 100.0% / 100.0% / 100.0% |
| 0.1 | 0.0% / 0.0% / 0.0% | 98.5% / 91.2% / 72.9% | 98.0% / 90.0% / 78.7% | 99.4% / 95.8% / 85.7% |
| 0.2 | 0.0% / 0.0% / 0.0% | 98.5% / 91.2% / 72.9% | 95.7% / 83.3% / 76.7% | 98.6% / 92.4% / 82.5% |
| 0.3 | 0.0% / 0.0% / 0.0% | 98.5% / 91.2% / 72.9% | 93.4% / 79.2% / 66.0% | 97.9% / 90.0% / 78.6% |

## Mondes avec au moins une fuite (toute opération / action irréversible)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak | D — Firebreak + prudence |
|---|---|---|---|---|
| 0 | 100.0% / 100.0% | 24.6% / 5.0% | 0.0% / 0.0% | 0.0% / 0.0% |
| 0.1 | 100.0% / 100.0% | 24.6% / 5.0% | 34.8% / 11.8% | 16.2% / 7.8% |
| 0.2 | 100.0% / 100.0% | 24.6% / 5.0% | 50.2% / 23.4% | 28.6% / 15.8% |
| 0.3 | 100.0% / 100.0% | 24.6% / 5.0% | 62.0% / 28.4% | 35.6% / 20.6% |

## Ventilation par entreprise compromise

Cellule : rappel moyen · sains bloqués · actions irréversibles fuitées (moyennes par monde). `e0` est le plus en amont.

### p = 0

| Compromise | Mondes | A | B | C | D |
|---|---|---|---|---|---|
| `e0` | 106 | 0.0% · 0.0 · 15.38 | 96.2% · 52.5 · 0.24 | 100.0% · 14.2 · 0.00 | 100.0% · 17.7 · 0.00 |
| `e1` | 111 | 0.0% · 0.0 · 10.74 | 97.8% · 59.9 · 0.08 | 100.0% · 14.9 · 0.00 | 100.0% · 17.5 · 0.00 |
| `e2` | 92 | 0.0% · 0.0 · 9.79 | 98.7% · 47.4 · 0.03 | 100.0% · 10.4 · 0.00 | 100.0% · 12.5 · 0.00 |
| `e3` | 96 | 0.0% · 0.0 · 9.92 | 100.0% · 40.5 · 0.00 | 100.0% · 6.2 · 0.00 | 100.0% · 8.1 · 0.00 |
| `e4` | 95 | 0.0% · 0.0 · 9.19 | 100.0% · 11.8 · 0.00 | 100.0% · 1.1 · 0.00 | 100.0% · 1.1 · 0.00 |

### p = 0.1

| Compromise | Mondes | A | B | C | D |
|---|---|---|---|---|---|
| `e0` | 106 | 0.0% · 0.0 · 15.38 | 96.2% · 52.5 · 0.24 | 96.5% · 11.5 · 0.38 | 98.7% · 16.7 · 0.21 |
| `e1` | 111 | 0.0% · 0.0 · 10.74 | 97.8% · 59.9 · 0.08 | 97.3% · 13.7 · 0.17 | 99.0% · 17.7 · 0.10 |
| `e2` | 92 | 0.0% · 0.0 · 9.79 | 98.7% · 47.4 · 0.03 | 98.1% · 9.7 · 0.09 | 99.6% · 12.8 · 0.03 |
| `e3` | 96 | 0.0% · 0.0 · 9.92 | 100.0% · 40.5 · 0.00 | 98.3% · 6.3 · 0.10 | 99.6% · 9.0 · 0.05 |
| `e4` | 95 | 0.0% · 0.0 · 9.19 | 100.0% · 11.8 · 0.00 | 100.0% · 2.0 · 0.00 | 100.0% · 2.0 · 0.00 |

### p = 0.2

| Compromise | Mondes | A | B | C | D |
|---|---|---|---|---|---|
| `e0` | 106 | 0.0% · 0.0 · 15.38 | 96.2% · 52.5 · 0.24 | 91.9% · 9.5 · 0.74 | 97.3% · 16.2 · 0.45 |
| `e1` | 111 | 0.0% · 0.0 · 10.74 | 97.8% · 59.9 · 0.08 | 94.4% · 13.0 · 0.38 | 98.1% · 18.1 · 0.23 |
| `e2` | 92 | 0.0% · 0.0 · 9.79 | 98.7% · 47.4 · 0.03 | 95.6% · 9.5 · 0.26 | 98.7% · 13.9 · 0.12 |
| `e3` | 96 | 0.0% · 0.0 · 9.92 | 100.0% · 40.5 · 0.00 | 97.0% · 6.3 · 0.17 | 99.0% · 9.9 · 0.11 |
| `e4` | 95 | 0.0% · 0.0 · 9.19 | 100.0% · 11.8 · 0.00 | 100.0% · 3.0 · 0.00 | 100.0% · 3.0 · 0.00 |

### p = 0.3

| Compromise | Mondes | A | B | C | D |
|---|---|---|---|---|---|
| `e0` | 106 | 0.0% · 0.0 · 15.38 | 96.2% · 52.5 · 0.24 | 88.0% · 7.7 · 1.01 | 96.1% · 15.5 · 0.58 |
| `e1` | 111 | 0.0% · 0.0 · 10.74 | 97.8% · 59.9 · 0.08 | 91.5% · 11.8 · 0.53 | 96.9% · 18.9 · 0.38 |
| `e2` | 92 | 0.0% · 0.0 · 9.79 | 98.7% · 47.4 · 0.03 | 93.0% · 9.0 · 0.39 | 98.3% · 14.5 · 0.15 |
| `e3` | 96 | 0.0% · 0.0 · 9.92 | 100.0% · 40.5 · 0.00 | 95.6% · 6.4 · 0.24 | 98.5% · 10.8 · 0.19 |
| `e4` | 95 | 0.0% · 0.0 · 9.19 | 100.0% · 11.8 · 0.00 | 100.0% · 4.1 · 0.00 | 100.0% · 4.1 · 0.00 |

## Lecture

- Un monde compte en moyenne 300 records, dont 30.4 ± 1.0 réellement contaminés, parmi lesquels 11.1 actions irréversibles (paiement, expédition, lancement de production).
- p = 0 : Firebreak bloque 4.5 fois moins d'opérations saines que le blocage des partenaires (9.6 contre 43.2), pour un rappel de 100.0% contre 98.5% et 0.00 action(s) irréversible(s) fuitée(s) contre 0.07.
- p = 0.1 : Firebreak bloque 4.9 fois moins d'opérations saines que le blocage des partenaires (8.8 contre 43.2), pour un rappel de 98.0% contre 98.5% et 0.15 action(s) irréversible(s) fuitée(s) contre 0.07.
- p = 0.2 : Firebreak bloque 5.1 fois moins d'opérations saines que le blocage des partenaires (8.4 contre 43.2), pour un rappel de 95.7% contre 98.5% et 0.32 action(s) irréversible(s) fuitée(s) contre 0.07.
- p = 0.3 : Firebreak bloque 5.4 fois moins d'opérations saines que le blocage des partenaires (7.9 contre 43.2), pour un rappel de 93.4% contre 98.5% et 0.45 action(s) irréversible(s) fuitée(s) contre 0.07.
- **A** laisse passer toute la contamination (rappel 0), dont 11.1 actions irréversibles par monde en moyenne : c'est le coût de « prévenir sans agir ».
- **B** ne dépend pas de p (elle n'utilise aucune dépendance enregistrée). Elle arrête presque toute la contamination dans ces mondes, au prix d'une grosse part d'activité saine bloquée.

## Limites

- **Règle d'origine prudente.** À p = 0, Firebreak bloque 9.6 opérations saines par monde, dont 9.6 (100.0%) à cause de la règle d'origine : toute donnée attribuée à l'entreprise compromise après `since` est mise en quarantaine, même si c'est la copie d'une donnée antérieure ou vérifiée, ainsi que ce qui en dépend. C'est un choix prudent du moteur, pas une erreur de propagation.
- **Dépendances manquantes.** Firebreak ne voit que ce qui est tracé. Le rappel de C passe de 100.0% à p = 0 à 93.4% à p = 0.3 (5e centile 79.2%, pire cas 66.0%) ; à p = 0.3, 28.4% des mondes laissent passer au moins une action irréversible contaminée.
- **D exploite le signal « provenance manquante ».** À p = 0.3, D récupère +4.4 points de rappel sur C pour +5.1 opérations saines bloquées par monde ; à p = 0, où rien n'est caché, D ne coûte que le bruit (+2.1) des réceptions légitimes d'hors fédération. Son gain repose sur une hypothèse du simulateur : une dépendance d'envoi manquante laisse toujours une trace visible (une réception non attribuée). Une dépendance interne manquante ne laisse aucune trace, et D ne la rattrape pas. Les chiffres de D sont donc une **borne haute** pour ce signal.
- Tout est simulé : les chiffres décrivent notre modèle de supply chain, pas une entreprise réelle.
