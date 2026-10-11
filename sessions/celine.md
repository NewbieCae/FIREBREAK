# Session — Céline

> Mis à jour par l'agent de Céline à chaque itération. Le plus récent en haut du journal.

## Où j'en suis

Banc d'essai v2 livré : 4 politiques (A alerte seule, B blocage fournisseur + partenaires, C Firebreak, D Firebreak + prudence = C + signal « provenance manquante » lu dans l'état du moteur uniquement), tirage de l'entreprise compromise parmi les 5 (e4, le client final, n'était jamais tirée en v1), 10 % de réceptions légitimes hors fédération (bruit pour D), colonnes `leaked_gates` / `contaminated_gates` / `fp_origin_rule`, rapport avec IC 95 %, 5e centile et pire cas du rappel, part des mondes avec fuite, ventilation par entreprise, limites chiffrées par le script. Toujours aucune modification d'`engine.py` ni de `federation.py`.

**⚠️ Les chiffres publiés ont changé (11/10)** : p=0 → C 9,6 sains bloqués contre 43,2 pour B (4,5× moins), précision 78 % contre 44 %, rappel 100 % contre 98,5 %, 0 action irréversible fuitée (A : 11,1 par monde ; B : au moins une fuite dans 24,6 % des mondes). p=0,3 → rappel C 93,4 % (5e centile 79,2 %, pire cas 66 %), D 97,9 %. À p=0, 100 % des sains bloqués par C viennent de la règle d'origine.

## En cours

- (rien)

## Prochaine étape

- Slides : ajouter « la blockchain prouve » (diapo 4) et la démo de réécriture du journal (diapo 5).
- Slide « preuve chiffrée » pour le pitch à partir de `docs/bench-results.md` (v2 + sensibilité).
- Les chiffres du banc peuvent être figés : la sensibilité ne change aucune conclusion de `docs/fiche-defense.md`.

## Besoin des autres

- Yann : j'ai modifié `tests/test_compare.py` (3 valeurs attendues : 43,2 / 9,6 / 0,985) et l'exemple `bench` de `docs/api.md` pour suivre la v2. Le CSV a désormais des lignes pour D et de nouvelles colonnes (les noms existants sont inchangés, `bench_block` fonctionne tel quel).
- Yann (pour info) : à p=0, tous les faux positifs de Firebreak viennent de la règle d'origine. Garder ce choix prudent ou seeder via le jeton seulement ?

## Journal

- 11/10 03 h 30 : retours d'un coéquipier appliqués après vérification dans `docs/agents-canal.md` et `docs/bench-results.md` : diapo « La preuve » sans la ligne des actions irréversibles (déplacée en Limites avec D 20,6 %), validateur unique et admin unique dits honnêtement, « finalité < 1 s » interdit (≈ 2 s/preuve sur la L1), fiche de défense : temps de réponse mesurés sur la démo. `docs/avalanche/pitch.md` non touché (pris par mika/pc1). 267 tests verts.
- 11/10 02 h 50 : pitch remis en cohérence avec la fusion Avalanche (question 8 « Pourquoi une blockchain ? », diapos 4 et 7, déroulé de démo sur les 5 gestes, 145 → 193 opérations dans le pitch et le brief UI, dates TradeLens unifiées, ligne « pas encore fait » de `docs/api.md` corrigée, README et `docs/firebreak.md`). 267 tests verts.
- 11/10 01 h 30 : balayages de sensibilité livrés (taille 5/8/12 à 60 op./entreprise, bruit hors fédération 0/10/30 % pour D, p = 0 et 0,3, 500 graines). Section « Sensibilité » + limites et vérification des conclusions écrites par le script ; `bench/sensitivity.csv` séparé (ne pollue pas `/api/compare`) ; `results.csv` inchangé. Fiche de défense non modifiée (aucune conclusion ne change). 218 tests verts.
- 11/10 01 h 10 : plan des balayages de sensibilité rédigé, en attente de validation.
- 11/10 01 h : banc d'essai v2 livré et chiffres régénérés (500 graines × 4 p × 4 politiques) ; fiche de défense, exemple API et test_compare mis à jour ; 213 tests verts.
- 11/10 00 h 30 : README — marqueurs de conflit poussés sur main résolus (version récente gardée + Track 3, ligne secrets `.env.example`, phrase finale brief/FIREBREAK). 197 tests verts.
- 11/10 00 h 15 : plan du banc d'essai v2 rédigé ; défaut trouvé : la dernière entreprise n'est jamais tirée comme compromise.
- 10/10 23 h 59 : banc d'essai livré (synth + 3 politiques + bench 500 graines + 12 tests), 183 tests verts.
