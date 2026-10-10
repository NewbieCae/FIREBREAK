# Session — Céline

> Mis à jour par l'agent de Céline à chaque itération. Le plus récent en haut du journal.

## Où j'en suis

Banc d'essai livré : `src/firebreak/synth.py` (mondes synthétiques à graine avec vérité terrain, dépendances cachées avec probabilité p), 3 politiques (A alerte seule, B blocage fournisseur + partenaires directs, C Firebreak = moteur existant), métriques (fuites, dégâts collatéraux, activité saine préservée, précision, rappel), `scripts/bench.py` → `bench/results.csv` + `docs/bench-results.md`, tests dans `tests/test_bench.py`. Aucune modification de `engine.py` ni `federation.py`.

Résultats (500 graines, 5 entreprises, 300 opérations) : Firebreak bloque 11,4 opérations saines contre 49,5 pour B (4,3× moins), activité saine préservée 95,7 % contre 81,3 %, précision 75 % contre 40 %. Rappel de C : 100 % à p=0, 97,1 % / 94,3 % / 91,6 % à p=0,1 / 0,2 / 0,3. B a un rappel de 98 % quel que soit p.

## En cours

- Banc d'essai v2 (réservé dans `goal.md`) : plan présenté, en attente de validation (D propage aux descendants ? tirage sur toutes les entreprises, ce qui change les chiffres publiés).

## Prochaine étape

- Ajouter au pitch une slide « preuve chiffrée » à partir de `docs/bench-results.md`.
- Pistes possibles : métriques sur les gates (paiements/expéditions) et montants ; un graphique des résultats.

## Besoin des autres

- Yann (pour info) : À p=0, la plupart des faux positifs de Firebreak viennent de la règle d'origine. Toute copie reçue de l'entreprise compromise après `since` est seedée, même si elle reprend un record antérieur à `since` ou `verified`. Garder ce choix prudent, ou seeder via le jeton seulement ? Sur ces mondes, ça ferait gagner de la précision.

## Journal

- 11/10 00 h 30 : README — marqueurs de conflit poussés sur main résolus (version récente gardée + Track 3, ligne secrets `.env.example`, phrase finale brief/FIREBREAK). 197 tests verts.
- 11/10 00 h 15 : plan du banc d'essai v2 rédigé ; défaut trouvé : la dernière entreprise n'est jamais tirée comme compromise.
- 10/10 23 h 59 : banc d'essai livré (synth + 3 politiques + bench 500 graines + 12 tests), 183 tests verts.
