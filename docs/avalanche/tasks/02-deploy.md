# Task 02 — Deployment on Mika's L1

First read `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md` and the task 01 report.

**This task touches the real L1.** The scripts read the configuration from the environment (`.env.local`); **you do not read that file yourself** and you never display the mnemonic or a private key. If a variable is missing, the script stops with a message saying which one, without displaying any value.

## Accounts

Derived from the mnemonic `FIREBREAK_CHAIN_MNEMONIC` (path `m/44'/60'/0'/0/i`, `eth_account` with HD features enabled):

| i | Role |
|---|---|
| 0 | admin (deploys, registers members, funds the others) |
| 1 | `fournisseur` |
| 2 | `fabricant` |
| 3 | `distributeur` |
| 4 | `client` |

Company ids come from `src/firebreak/scenario.py` (check that they are indeed these four for all scenarios; otherwise, take the union and document it).

## `scripts/chain_smoke.py`

Read-only, risk-free. Displays: RPC reachable, chainId (and comparison with `FIREBREAK_CHAIN_ID`), latest block, **public addresses** and balances of accounts 0 to 4, and if `contracts/deployments/l1.json` exists, that the code is indeed present at the address and that `admin()` responds. Exit code ≠ 0 if anything is wrong.

## `scripts/chain_deploy.py`

1. Checks chainId. Refuses to run if `FIREBREAK_CHAIN_ID` is 43114 (C-Chain mainnet) or if the admin's balance is zero.
2. **Allowlists** (if enabled on the L1, see sheet 00): via the Subnet-EVM precompiles — `ContractDeployerAllowList` `0x0200000000000000000000000000000000000000`, `TxAllowList` `0x0200000000000000000000000000000000000002`, function `setEnabled(address)` and read `readAllowList(address)` (0 = none, 1 = enabled, 2 = admin, 3 = manager). Enables accounts 1 to 4 in `TxAllowList` if they aren't already. Option `--skip-allowlist`. **On Mika's L1, `TxAllowList` is not enabled (checked on 11/10)**: the script detects an empty `0x` response to `readAllowList` and skips the step with a message, without error. If the `avalanche-docs` MCP is available, check these addresses and this behavior before writing the code.
3. Funds accounts 1 to 4 if they have less than `--min-balance` (default 0.5 native token), from the admin.
4. Deploys `FirebreakRegistry` from `contracts/build/FirebreakRegistry.json` (unless `--reuse` and a valid deployment exists).
5. Registers the 4 members: `registerMember(account_i, company_id_bytes32, ed25519_pubkey)`. The Ed25519 key is the one from `Federation.public_keys[cid]` for the same `FIREBREAK_KEY_SEED` as the server; if `FIREBREAK_KEY_SEED` is not set, the script stops and explains that it must be fixed in `.env.local` (otherwise the keys change at every server launch).
6. Writes `contracts/deployments/l1.json`: `chainId`, `address`, `deployBlock`, `deployTx`, `admin` (public address), `members: {company: account}`, `abiSha256`. **No secrets.** This file is committed.
7. Prints a summary with explorer links if `FIREBREAK_CHAIN_EXPLORER_URL` is set.

Both scripts reuse `src/firebreak/chain/config.py` and `ids.py` (task 03). If task 03 isn't done yet, create these two modules minimally with exactly the functions described in sheet 03, and mention it in your report.

## Tests

`tests/test_chain_deploy.py`: runs `chain_deploy` by calling its main function on `EthereumTesterProvider` (allowlist skipped), with the public test mnemonic. Checks the produced deployment file (in a temporary folder) and the 4 registered members.

## Real run

Not by you: Mika runs `uv run python scripts/chain_smoke.py` then `uv run python scripts/chain_deploy.py`. End your report with these two commands and what they should display.

## Done when

- `uv run pytest -q` green.
- Commit `chain: scripts de déploiement et de vérification de la L1`.
