# Tâche 05 — Dashboard, script de démo et éléments de pitch

Lis d'abord `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, `docs/api.md` (section Avalanche), `docs/demo.md`, puis `web/index.html`.

## 1. Panneau « Avalanche » dans `web/index.html`

`web/index.html` est le dashboard de debug de Yann : ajoute un panneau **repliable**, sans toucher au reste de la mise en page ni au comportement existant. Il ne s'affiche que si `GET /api/chain/status` répond `mode != "off"`.

- En-tête : point vert/rouge `connected`, chainId, adresse du contrat (raccourcie, lien explorer), `run_id` raccourci, compteurs de la file.
- Liste des ancrages (`/api/chain/anchors`, rafraîchie toutes les 2 s) : icône par `kind`, entreprise, hash raccourci, statut (pastille), lien `tx` vers l'explorer.
- Sur chaque alerte animée existante (pointillés entre entreprises) : quand l'ancrage correspondant est `confirmed`, afficher un petit badge « ancrée · bloc N ».
- Bouton « Vérifier sur Avalanche » → `/api/audit/verify`, affiche par entreprise local ✓/✗ et on-chain ✓/✗.
- Si `FIREBREAK_DEMO=1` : bouton « Simuler une réécriture du journal » → `POST /api/demo/rewrite` puis re-vérification automatique.

Textes en français. Aucune bibliothèque nouvelle.

## 2. Pilotage de démo

Si `POST /api/demo/step` et `src/firebreak/demo.py` le permettent **sans modifier les étapes existantes**, ajoute à la fin deux étapes optionnelles, actives seulement quand la chaîne est active :
- « Preuves ancrées sur Avalanche » (vérification on-chain, tout vert) ;
- « Réécriture du journal » (rewrite + vérification : local vert, on-chain rouge).

Si ça demande de toucher au déroulé existant, ne le fais pas : documente plutôt l'enchaînement manuel dans `docs/demo.md`.

## 3. `docs/demo.md`

Ajoute une section « Avalanche L1 (optionnel) » : lancement (`FIREBREAK_CHAIN=l1`, prérequis `chain_smoke.py`), chaque clic, ce qu'on voit, la phrase à dire. Phrases proposées :

- « Chaque alerte et chaque journal sont ancrés sur notre L1 Avalanche : un témoin horodaté que ni le fournisseur, ni le client, ni nous ne pouvons réécrire. »
- « Seuls les membres de la chaîne peuvent écrire : une entreprise extérieure ne peut pas déclarer un faux incident pour paralyser un concurrent. »
- « Ici quelqu'un réécrit le journal du fabricant pour effacer qu'il a été prévenu, et recalcule tous les hash. La vérification locale ne voit rien. Avalanche, si. »
- « Aucune donnée commerciale sur la chaîne : uniquement des empreintes. »

## 4. `docs/avalanche/pitch.md`

Une page pour la slide « Pourquoi une blockchain » : les 3 preuves (audit, alertes, incidents), ce qui n'est pas on-chain, pourquoi une L1 dédiée (allowlist des membres, coût, souveraineté du consortium), la leçon TradeLens (on n'impose pas un registre de données commun, seulement des empreintes), et les chiffres réels lus sur la L1 pendant la répétition (nombre de transactions d'une démo, temps de confirmation moyen mesuré via `/api/chain/anchors`).

## Tests

Pas de test UI. `uv run pytest -q` doit rester vert. Vérifie à la main en mode `tester` que le panneau s'affiche, et en mode `off` qu'il est absent.

## Fini quand

- Commit `chain: panneau Avalanche, démo et pitch`.
- Rapport : captures ou description de ce qui s'affiche, et la liste de ce qui reste à faire avant fusion dans `main`.
