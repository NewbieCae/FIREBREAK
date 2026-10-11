# Task 00 — Setup (Mika, by hand)

This sheet is **not** for an agent: it involves secrets and installing tools on Mika's machine.

## 1. Tools on the machine (Windows)

Finding on 11/10: `uv`, `forge` and Python ≥ 3.12 are missing; only Python 3.6 is installed.

- [ ] Install `uv` (it also installs Python 3.12 for the project):
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  Then reopen the terminal, and in `finswag/`: `uv sync` then `uv run pytest -q` → everything must be green **before** starting the agents.
- Foundry is **not** needed: we compile and test the contract from Python (`py-solc-x`, `eth-tester`), to stay within the team's stack.

## 2. L1 info (not secret) — fill in here

| Info | Value |
|---|---|
| EVM chainId | `569712` (checked on 11/10: `eth_chainId` → `0x8b170`) |
| RPC URL | `https://nodes-prod.43.207.73.245.sslip.io/ext/bc/2HxMVTcRc1ZmgN18oemXZPSMnarWoWMA8H1g48orwbEuqxSBks/rpc` (node managed by the Builder Hub) |
| Explorer | `https://2hxmvtcr.firn.gg` |
| Blockchain ID | `2HxMVTcRc1ZmgN18oemXZPSMnarWoWMA8H1g48orwbEuqxSBks` |
| Subnet ID (P-Chain) | `mbgwkeduUWKyJ7taabLPyiWKFHvPiDDfyhqA9fXKyZgthzTMT` |
| Validator Manager (on the C-Chain) | `0xf8fbe4674a555fd34ea7ba0c3ec1ffed6cc482fb` |
| Validator node | `NodeID-DfVkATxNoiQcbqCwJoy4nApEqJWnRhN7D` (only one: if this node goes down, the L1 stops) |
| Created with | Builder Hub console |
| Native token symbol | to be confirmed |
| `TxAllowList` enabled? | **No** (checked on 11/10: `readAllowList` on `0x02…02` → `0x`). Any account with gas can send transactions; access control is done in the contract (`onlyMember`). |
| `ContractDeployerAllowList` enabled? admin = ? | to be confirmed (same) |
| Public address of account 0 (admin, the one holding the tokens) | to be confirmed: 0x… |

## 3. `.env.local` file at the root of `finswag/` (ignored by Git)

Create `.env.local` by hand with this content. The mnemonic is that of the wallet **dedicated to the hackathon**; it must not control any real funds.

```
# Federation: set these two values (any long random string)
# so the Ed25519 keys stay stable between two server launches.
# Required: the public keys are registered on-chain at deployment.
FIREBREAK_KEY_SEED=...
FIREBREAK_PAIR_SECRET=...

# Avalanche L1 — off (default) | tester (in-memory EVM) | l1 (real L1)
FIREBREAK_CHAIN=l1
FIREBREAK_CHAIN_RPC_URL=...
FIREBREAK_CHAIN_ID=...
FIREBREAK_CHAIN_EXPLORER_URL=...
# Account 0 = admin (holds the tokens), 1..4 = fournisseur, fabricant, distributeur, client
FIREBREAK_CHAIN_MNEMONIC=...
FIREBREAK_CHAIN_DEPLOYMENT=contracts/deployments/l1.json
```

To generate the two federation secrets: `python -c "import secrets; print(secrets.token_hex(32))"` (twice).

Check: `git check-ignore -v .env.local` must respond (file ignored).

## 4. Avalanche MCP (optional, useful for agents)

Gives agents up-to-date Avalanche docs (precompiles, EVM version, tools):
```bash
claude mcp add --transport http avalanche-docs https://build.avax.network/api/mcp
```

## 5. Let the team know

`AGENTS.md` says "no branches". Tell Yann that the Avalanche part lives on `mika/avalanche-l1`, disabled by default, and will only be merged when green. Message to send with `scripts/messages.py send yann "…"` (it pushes to `main`, that's intended).

## Done when

- `uv run pytest -q` green on the branch.
- The table in §2 is filled in.
- `.env.local` exists and is ignored.
