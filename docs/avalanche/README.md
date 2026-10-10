# FIREBREAK × Avalanche L1 — plan d'intégration (partie de Mika)

> Branche : `mika/avalanche-l1`. Rien de cette partie ne va sur `main` tant que `uv run pytest -q` n'est pas vert **et** que la démo tourne à l'identique avec `FIREBREAK_CHAIN=off`.

## Pourquoi une blockchain dans Firebreak

Le moteur prouve déjà ses décisions **localement** : journal d'audit chaîné par hash (`audit.py`), alertes signées Ed25519 (`federation.py`). Mais `audit.py` le dit lui-même :

> « la chaîne prouve que le journal n'a pas été modifié par quelqu'un qui ne recalcule pas tous les hash suivants. Pour s'en protéger, il faut ancrer le dernier hash (`head`) à l'extérieur. »

C'est exactement le rôle de la L1 : **un témoin horodaté, partagé par les entreprises, que personne ne peut réécrire après coup.** Trois preuves, et aucune donnée commerciale on-chain :

| Preuve | Question à laquelle elle répond | Sur la chaîne |
|---|---|---|
| **Ancrage d'audit** | « Ce journal est-il bien celui qui existait à 14 h 05, ou a-t-il été réécrit depuis ? » | `head` (sha256) + nombre d'entrées, par entreprise |
| **Ancrage d'alerte** | « Le distributeur a-t-il été prévenu, et quand ? » (litige, assurance, NIS2) | sha256 de l'alerte signée + émetteur + destinataire + type + accusé de réception |
| **Déclaration d'incident** | « Qui a déclaré le fournisseur compromis, depuis quand, et à quelle heure ? » | id de la source + `since` + hash de la déclaration |

Bonus propre à une L1 : un **annuaire des clés publiques Ed25519** des membres, et l'allowlist de la L1 (`TxAllowList`) qui empêche une entreprise extérieure d'écrire, donc de déclarer un faux incident pour paralyser un concurrent.

## Ce qu'on NE met PAS sur la chaîne

Records, montants, RIB, libellés, jetons opaques, taint paths. Les identifiants d'entreprise sont passés en `bytes32 = sha256("firebreak:company:" + id)`.

## Principes non négociables

1. **La chaîne ne décide rien et ne bloque rien.** Le moteur fonctionne à l'identique sans elle. Elle ajoute des preuves.
2. **Jamais bloquante.** Toute écriture on-chain passe par une file en arrière-plan. Une L1 lente ou injoignable → statut `pending` / `failed` dans l'API, jamais une erreur 500 ni une latence ajoutée à `/api/state` (< 200 ms).
3. **Désactivée par défaut.** `FIREBREAK_CHAIN=off` (défaut) → aucun import réseau, aucun appel. `FIREBREAK_DEMO=1` garde son mode « zéro réseau » sauf si `FIREBREAK_CHAIN=l1` est posé explicitement.
4. **Tests sans réseau.** Les contrats sont testés en Python avec une EVM en mémoire (`eth-tester` / `py-evm`). La L1 réelle n'est utilisée que par le script de déploiement et la démo.
5. **Aucun secret dans le dépôt.** Mnémonique et clés dans `.env.local` (ignoré par Git). **Un agent ne lit jamais, n'affiche jamais, ne copie jamais** `.env`, `.env.local` ni le dossier `L1 blockchain/` de Mika.
6. **On ajoute à l'API, on ne casse rien.** Nouveaux endpoints sous `/api/chain/…`, nouveaux champs optionnels ailleurs. `docs/api.md` mis à jour.

## Architecture

```
                 Firebreak (inchangé)                         │      Avalanche L1 (Mika)
                                                              │
  Simulation ──► audit.py (journaux chaînés par hash) ──┐     │
       │                                                │     │
       └──────► federation.py (alertes signées) ────────┤     │
                                                        ▼     │
                       src/firebreak/chain/anchoring.py       │
                       (observe les actions de l'API,         │
                        calcule les hash à ancrer)            │
                                   │                          │
                                   ▼                          │
                       src/firebreak/chain/client.py          │
                       file d'attente + thread d'envoi ───────┼──► FirebreakRegistry.sol
                       NullChain | TesterChain | Web3Chain    │      registerMember / pubkey
                                   │                          │      declareIncident
                                   ▼                          │      anchorAlert / acknowledgeAlert
                       /api/chain/status, /api/chain/anchors, │      anchorAudit
                       /api/audit/verify (+ champ onchain)    │      (events = preuve horodatée)
                                   │                          │
                                   ▼                          │
                       web/index.html : panneau « Avalanche » │
```

## Arborescence ajoutée

```
contracts/
  FirebreakRegistry.sol          # le contrat (un seul)
  build/FirebreakRegistry.json   # ABI + bytecode compilés, versionnés (le serveur n'a pas besoin de solc)
  deployments/l1.json            # adresse, chainId, bloc de déploiement, membres (aucun secret)
src/firebreak/chain/
  __init__.py
  config.py                      # lecture env + .env.local, sans nouvelle dépendance
  ids.py                         # company_id → bytes32, hash d'alerte, hash de déclaration
  accounts.py                    # comptes EVM dérivés du mnémonique (admin + 4 entreprises)
  artifact.py                    # charge contracts/build/FirebreakRegistry.json
  deployer.py                    # déploie + enregistre les membres (scripts, tests, mode tester)
  client.py                      # interface ChainClient + NullChain + Web3Chain + worker
  anchoring.py                   # ce qu'on ancre après chaque action
scripts/
  chain_compile.py               # solc → contracts/build/
  chain_deploy.py                # déploie, enregistre les membres, (allowlist), écrit deployments/l1.json
  chain_smoke.py                 # vérifie RPC, chainId, solde, lecture du contrat
tests/
  test_chain_contract.py         # contrat sur EVM en mémoire
  test_chain_client.py           # client, file, repli, ids
  test_chain_api.py              # endpoints, audit verify onchain, réécriture détectée
docs/avalanche/                  # ce dossier
```

## Configuration (`.env.local`, jamais versionné — modèle complet dans [la fiche 00](tasks/00-setup.md))

| Variable | Rôle |
|---|---|
| `FIREBREAK_CHAIN` | `off` (défaut) · `tester` (EVM en mémoire, pour dev/tests) · `l1` (vraie L1) |
| `FIREBREAK_CHAIN_RPC_URL` | URL RPC de la L1 de Mika |
| `FIREBREAK_CHAIN_ID` | chainId de la L1 (vérifié au démarrage, refus si différent) |
| `FIREBREAK_CHAIN_EXPLORER_URL` | base de l'explorer, pour les liens `…/tx/<hash>` (optionnel) |
| `FIREBREAK_CHAIN_MNEMONIC` | mnémonique du wallet de test dédié (compte 0 = admin, 1..4 = entreprises) |
| `FIREBREAK_CHAIN_DEPLOYMENT` | chemin du fichier de déploiement (défaut `contracts/deployments/l1.json`) |
| `FIREBREAK_KEY_SEED`, `FIREBREAK_PAIR_SECRET` | déjà utilisés par `federation.py` ; **doivent être fixés** quand la chaîne est active, sinon les clés Ed25519 changent à chaque lancement et ne correspondent plus à celles enregistrées on-chain |

## Contrat ajouté à l'API (résumé, détail dans la tâche 04)

| Endpoint | Rôle |
|---|---|
| `GET /api/chain/status` | `mode`, `connected`, `chain_id`, `contract`, `explorer_url`, `last_block`, `queue` (pending/sent/failed) |
| `GET /api/chain/anchors` | Liste des ancrages : `kind` (audit/alert/incident/ack), `company`, `hash`, `status`, `tx_hash`, `block`, `explorer_link`, `ts` |
| `POST /api/chain/anchor` | Force l'ancrage immédiat des têtes de journaux |
| `GET /api/audit/verify` | **Ajout** par journal : `onchain: {anchored_head, anchored_entries, block, tx_hash, matches}` (null si chaîne off) |
| `POST /api/demo/rewrite` | Démo uniquement (`FIREBREAK_DEMO=1`) : réécrit un journal **en recalculant tous les hash** — la vérification locale dit OK, l'ancrage on-chain dit NON |

## Le moment fort de la démo

1. Compromission → les alertes et les journaux sont ancrés : le panneau Avalanche affiche les transactions, liens vers l'explorer.
2. « Un attaquant, ou un employé, réécrit le journal du fabricant pour effacer qu'il a été prévenu à 14 h 05, et recalcule tous les hash. » → `POST /api/demo/rewrite`.
3. Vérification locale : **intègre** (la réécriture est cohérente). Vérification on-chain : **ne correspond pas** au hash ancré au bloc N. La fraude est prouvée par un témoin que personne ne contrôle.

## Ordre des tâches

| # | Fiche | Dépend de | Parallélisable |
|---|---|---|---|
| 00 | [Mise en place](tasks/00-setup.md) | — | **Mika, à la main** (outillage + infos L1) |
| 01 | [Contrat FirebreakRegistry](tasks/01-contract.md) | 00 | — |
| 02 | [Déploiement sur la L1](tasks/02-deploy.md) | 01 | avec 03 |
| 03 | [Client Python et ancrage](tasks/03-chain-client.md) | 01 (ABI) | avec 02 |
| 04 | [API](tasks/04-api.md) | 03 | — |
| 05 | [Dashboard, démo et pitch](tasks/05-dashboard-demo.md) | 04 (+ 02 pour la vraie L1) | — |

Chaque fiche est autonome : un agent la lit avec ce README et [les règles communes](tasks/RULES.md), et rien d'autre n'est nécessaire.

## Questions ouvertes pour Mika

- chainId, URL RPC et explorer de la L1 (à mettre dans `.env.local` et dans la fiche 00).
- Precompiles activés : `TxAllowList` ? `ContractDeployerAllowList` ? Le compte admin y est-il admin ?
- Le mnémonique du `.env` est-il celui à utiliser (compte 0 = celui qui a les AVAX) ?
- Fusion dans `main` : avant le gel de 10 h, ou présenter la L1 comme une démo séparée si la fusion est trop risquée ?

## Répartition entre agents (validée le 11/10 à 01 h 05, voir `docs/agents-canal.md` sur `main`)

| Agent | Branche | Fichiers |
|---|---|---|
| `mika/pc1` (intégrateur, décide en dernier) | `mika/avalanche-l1` | `pyproject.toml`, `uv.lock`, `src/firebreak/chain/{__init__,config,ids,accounts,artifact,deployer}.py`, `contracts/`, `scripts/chain_*.py`, `tests/test_chain_{contract,deploy,ids}.py` — tâches 01 et 02 |
| `mika/pc2` | `mika/avalanche-l1-api` | `src/firebreak/chain/{client,anchoring,tamper}.py`, `src/firebreak/api.py`, `schemas.py`, `docs/api.md`, `web/index.html`, `docs/demo.md`, `tests/test_chain_{client,api}.py` — tâches 03, 04, 05 |

Le contrat d'interface exact des modules de pc1 est dans le message `mika/pc1 → mika/pc2 · 01:05` du canal.
