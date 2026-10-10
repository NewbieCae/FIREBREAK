# Banc d'essai Firebreak — résultats

> Généré par `uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3`. Ne pas éditer à la main.

500 mondes synthétiques par valeur de p (5 entreprises, 300 opérations chacun, générateur `src/firebreak/synth.py`). Dans chaque monde, une entreprise qui a des clients est compromise à partir d'une heure `since`. **Vérité terrain** : ses records émis après `since` et tous leurs descendants par les *vraies* dépendances, sauf les records `verified`. Le moteur ne voit que les dépendances *enregistrées* : chaque vraie dépendance (entrée d'un record ou envoi entre entreprises) est cachée avec la probabilité **p**.

Politiques, appliquées au même monde :

- **A — Alerte seule** : on prévient tout le monde, rien n'est bloqué.
- **B — Blocage fournisseur + partenaires** : tout record daté de `since` ou après chez l'entreprise compromise et ses clients directs est bloqué (la réponse « on coupe le fournisseur »).
- **C — Firebreak** : le moteur du dépôt (`Simulation.declare_compromise`), propagation sur le graphe enregistré + alertes signées.

Valeurs : moyenne ± demi-largeur de l'IC 95 % (approximation normale). « n/d » : non défini (A ne bloque rien, donc pas de précision).

## Fuites (contaminés non bloqués)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak |
|---|---|---|---|
| 0 | 33.5 ± 1.2 | 0.9 ± 0.2 | 0.0 ± 0.0 |
| 0.1 | 33.5 ± 1.2 | 0.9 ± 0.2 | 1.2 ± 0.2 |
| 0.2 | 33.5 ± 1.2 | 0.9 ± 0.2 | 2.3 ± 0.3 |
| 0.3 | 33.5 ± 1.2 | 0.9 ± 0.2 | 3.4 ± 0.3 |

## Dégâts collatéraux (sains bloqués)

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak |
|---|---|---|---|
| 0 | 0.0 ± 0.0 | 49.5 ± 1.8 | 11.4 ± 0.7 |
| 0.1 | 0.0 ± 0.0 | 49.5 ± 1.8 | 10.3 ± 0.6 |
| 0.2 | 0.0 ± 0.0 | 49.5 ± 1.8 | 9.4 ± 0.5 |
| 0.3 | 0.0 ± 0.0 | 49.5 ± 1.8 | 8.8 ± 0.5 |

## Activité saine préservée

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak |
|---|---|---|---|
| 0 | 100.0% ± 0.0% | 81.3% ± 0.7% | 95.7% ± 0.3% |
| 0.1 | 100.0% ± 0.0% | 81.3% ± 0.7% | 96.1% ± 0.2% |
| 0.2 | 100.0% ± 0.0% | 81.3% ± 0.7% | 96.5% ± 0.2% |
| 0.3 | 100.0% ± 0.0% | 81.3% ± 0.7% | 96.7% ± 0.2% |

## Précision

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak |
|---|---|---|---|
| 0 | n/d | 40.4% ± 1.0% | 75.2% ± 1.2% |
| 0.1 | n/d | 40.4% ± 1.0% | 76.0% ± 1.1% |
| 0.2 | n/d | 40.4% ± 1.0% | 76.8% ± 1.1% |
| 0.3 | n/d | 40.4% ± 1.0% | 77.1% ± 1.0% |

## Rappel

| p | A — Alerte seule | B — Blocage fournisseur + partenaires | C — Firebreak |
|---|---|---|---|
| 0 | 0.0% ± 0.0% | 98.0% ± 0.3% | 100.0% ± 0.0% |
| 0.1 | 0.0% ± 0.0% | 98.0% ± 0.3% | 97.1% ± 0.4% |
| 0.2 | 0.0% ± 0.0% | 98.0% ± 0.3% | 94.3% ± 0.5% |
| 0.3 | 0.0% ± 0.0% | 98.0% ± 0.3% | 91.6% ± 0.6% |

## Lecture

- Un monde compte en moyenne 300 records, dont 33.5 ± 1.2 réellement contaminés.
- p = 0 : Firebreak bloque 4.3 fois moins d'opérations saines que le blocage des partenaires (11.4 contre 49.5), pour un rappel de 100.0% contre 98.0%.
- p = 0.1 : Firebreak bloque 4.8 fois moins d'opérations saines que le blocage des partenaires (10.3 contre 49.5), pour un rappel de 97.1% contre 98.0%.
- p = 0.2 : Firebreak bloque 5.3 fois moins d'opérations saines que le blocage des partenaires (9.4 contre 49.5), pour un rappel de 94.3% contre 98.0%.
- p = 0.3 : Firebreak bloque 5.7 fois moins d'opérations saines que le blocage des partenaires (8.8 contre 49.5), pour un rappel de 91.6% contre 98.0%.
- **A** laisse passer toute la contamination (rappel 0) : c'est le coût de « prévenir sans agir ».
- **B** arrête presque toute la contamination dans ces mondes (elle dépasse rarement le premier rang de clients), mais au prix d'une grosse part d'activité saine bloquée chez le fournisseur et ses partenaires. Son rappel ne dépend pas de p : B n'utilise aucune dépendance enregistrée.
- **C** suit la contamination sur tout le graphe : à p = 0, rappel de 100 %. Ses faux positifs viennent de la règle d'origine du moteur : toute donnée reçue de l'entreprise compromise après `since` est mise en quarantaine, même si c'est la copie d'un record antérieur ou vérifié (choix prudent). Quand p augmente, les dépendances non enregistrées font baisser le rappel : c'est la limite honnête de l'approche — Firebreak ne voit que ce qui est tracé.
