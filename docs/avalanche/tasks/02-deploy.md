# Tâche 02 — Déploiement sur la L1 de Mika

Lis d'abord `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md` et le rapport de la tâche 01.

**Cette tâche touche la vraie L1.** Les scripts lisent la configuration depuis l'environnement (`.env.local`) ; **tu ne lis pas ce fichier toi-même** et tu n'affiches jamais le mnémonique ni une clé privée. Si une variable manque, le script s'arrête avec un message qui dit laquelle, sans afficher de valeur.

## Comptes

Dérivés du mnémonique `FIREBREAK_CHAIN_MNEMONIC` (chemin `m/44'/60'/0'/0/i`, `eth_account` avec les fonctions HD activées) :

| i | Rôle |
|---|---|
| 0 | admin (déploie, enregistre les membres, finance les autres) |
| 1 | `fournisseur` |
| 2 | `fabricant` |
| 3 | `distributeur` |
| 4 | `client` |

Les ids d'entreprise viennent de `src/firebreak/scenario.py` (vérifie qu'ils sont bien ces quatre-là pour tous les scénarios ; sinon, prends l'union et documente).

## `scripts/chain_smoke.py`

Lecture seule, sans risque. Affiche : RPC joignable, chainId (et comparaison avec `FIREBREAK_CHAIN_ID`), dernier bloc, **adresses publiques** et soldes des comptes 0 à 4, et si `contracts/deployments/l1.json` existe, que le code est bien présent à l'adresse et que `admin()` répond. Code de sortie ≠ 0 si quelque chose ne va pas.

## `scripts/chain_deploy.py`

1. Vérifie chainId. Refuse de tourner si `FIREBREAK_CHAIN_ID` est 43114 (C-Chain mainnet) ou si le solde de l'admin est nul.
2. **Allowlists** (si activées sur la L1, voir la fiche 00) : via les precompiles Subnet-EVM — `ContractDeployerAllowList` `0x0200000000000000000000000000000000000000`, `TxAllowList` `0x0200000000000000000000000000000000000002`, fonction `setEnabled(address)` et lecture `readAllowList(address)` (0 = aucun, 1 = enabled, 2 = admin, 3 = manager). Active les comptes 1 à 4 dans `TxAllowList` s'ils ne le sont pas. Option `--skip-allowlist`. Si le MCP `avalanche-docs` est disponible, vérifie ces adresses et ce comportement avant d'écrire le code.
3. Finance les comptes 1 à 4 s'ils ont moins de `--min-balance` (défaut 0,5 jeton natif), depuis l'admin.
4. Déploie `FirebreakRegistry` depuis `contracts/build/FirebreakRegistry.json` (sauf si `--reuse` et qu'un déploiement valide existe).
5. Enregistre les 4 membres : `registerMember(account_i, company_id_bytes32, ed25519_pubkey)`. La clé Ed25519 est celle de `Federation.public_keys[cid]` pour le même `FIREBREAK_KEY_SEED` que le serveur ; si `FIREBREAK_KEY_SEED` n'est pas défini, le script s'arrête et explique qu'il faut le fixer dans `.env.local` (sinon les clés changent à chaque lancement du serveur).
6. Écrit `contracts/deployments/l1.json` : `chainId`, `address`, `deployBlock`, `deployTx`, `admin` (adresse publique), `members: {company: account}`, `abiSha256`. **Aucun secret.** Ce fichier est versionné.
7. Imprime un résumé avec les liens explorer si `FIREBREAK_CHAIN_EXPLORER_URL` est défini.

Les deux scripts réutilisent `src/firebreak/chain/config.py` et `ids.py` (tâche 03). Si la tâche 03 n'est pas encore faite, crée ces deux modules a minima avec exactement les fonctions décrites dans la fiche 03, et signale-le dans ton rapport.

## Tests

`tests/test_chain_deploy.py` : déroule `chain_deploy` en appelant sa fonction principale sur `EthereumTesterProvider` (allowlist sautée), avec le mnémonique de test public. Vérifie le fichier de déploiement produit (dans un dossier temporaire) et les 4 membres enregistrés.

## Exécution réelle

Pas par toi : Mika lance `uv run python scripts/chain_smoke.py` puis `uv run python scripts/chain_deploy.py`. Termine ton rapport par ces deux commandes et ce qu'elles doivent afficher.

## Fini quand

- `uv run pytest -q` vert.
- Commit `chain: scripts de déploiement et de vérification de la L1`.
