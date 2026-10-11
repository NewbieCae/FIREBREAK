# Feuille de démo — Avalanche, qualité, entrées en stock

> Complète `docs/demo.md` (démo principale, interface `/app/`). Ces trois séquences se montrent depuis le **tableau de bord** (`http://localhost:8000/`), panneaux repliables à droite. Chiffres : ceux de l'écran.

## Avant de monter sur scène (machine de Mika, `.env.local` en mode `l1`)

```bash
uv run python scripts/chain_smoke.py          # RPC joignable, chainId 569712, contrat 0xeA4BeAe1… présent
FIREBREAK_DEMO=1 uv run uvicorn firebreak.api:app --port 8000
```
PowerShell : `$env:PYTHONUTF8='1'; $env:FIREBREAK_DEMO='1'; uv run uvicorn firebreak.api:app --port 8000`.
Sans `.env.local` ou sans réseau : `FIREBREAK_CHAIN=tester` (EVM en mémoire) — dans ce cas, ne pas dire « notre L1 ».

**Lancer la démo principale 1 à 2 minutes avant d'ouvrir le panneau Avalanche** : la file d'ancrage doit être vide (~40 s pour la démo complète sur la vraie L1).

## Séquence 1 — Avalanche (30 s), après la démo principale

1. Ouvrir **Avalanche** : pastille verte, liste des ancrages confirmés (liens vers l'explorer).
   « Chaque alerte, chaque accusé, chaque journal est ancré sur notre L1 Avalanche : un témoin horodaté que personne ne peut réécrire. »
2. **Vérifier sur Avalanche** → local ✓, Avalanche ✓.
3. **Simuler une réécriture du journal** → local ✓, Avalanche ✗.
   « Quelqu'un a effacé du journal du fabricant qu'il avait été prévenu, et recalculé tous les hash. La vérification locale ne voit rien. Avalanche, si. »

## Séquence 2 — Entrées en stock (40 s), scénario `mixed`

1. Réinitialiser sur **Attaque mixte**. Ouvrir **Entrées en stock**, entreprise **fabricant**, **Contrôler les réceptions**.
2. Montrer la carte rouge : bobine de la commande BC-9999, **30/100, suspect, en attente** — commande inconnue, certificat hors séquence, RIB modifié.
   « Avant même d'entrer en stock, le lot piégé est noté, expliqué, et mis en attente. »
3. **Refuser** → « signalement qualité signé envoyé au fournisseur ». Le lot et tout ce qui en dépend restent isolés.
4. Carte orange : livraison de 14 h 45, **65/100, doute** (pas de certificat, RIB changé le même jour) → **Accepter** (« certificat reçu par mail »).
   « Les règles proposent, l'humain décide, au cas par cas. »

## Séquence 3 — Rappel qualité (60 s), scénario `recall`

Panneau **Qualité (debug)**, pré-rempli par le scénario.
1. Entreprise **client**, référence `c-gr-03`, motif « casse sur chantier » → **Signaler en amont** (vers le distributeur). « Le client ne connaît pas la bobine : il signale ce qu'il a reçu. »
2. Entreprise **distributeur** → **Confirmer** dans la boîte de réception ; puis référence `d-out-03` → **Signaler en amont** (vers le fabricant).
3. Entreprise **fabricant**, référence `m-ship-03` → **Analyse rappel** : causes possibles, avec le périmètre de chacune. « C'est l'analyste qui choisit. »
4. Référence `COIL-103` → **Lot suspect** : le lot frère LOT-A30, déjà expédié, est isolé aussi ; les autres lots continuent.
5. `COIL-103` → **Signaler en amont** (vers le fournisseur) ; entreprise **fournisseur** → **Confirmer**.
   « À aucun moment le fournisseur n'a été blacklisté. »

## Chiffres mesurés sur la vraie L1 (à citer comme tels)

- Démo complète : 19 preuves, ~38 s, 0 échec. Rappel complet : 25 preuves, ~86 s. Entrées en stock (mixte) : 16 preuves, ~25 s.
- L'interface ne dépend jamais de la chaîne : chaque geste répond en quelques dizaines de millisecondes.
- Démo : un seul validateur (nœud hébergé par le Builder Hub). En production : les validateurs sont les membres du consortium.

## Si ça casse

- Chaîne lente ou injoignable : la démo continue, les ancrages passent « en attente » ou « échec » ; ne pas ouvrir le panneau Avalanche, dire « l'ancrage rattrape ensuite ».
- Plan B en ligne : https://firebreak-zeta.vercel.app (sans Avalanche).
