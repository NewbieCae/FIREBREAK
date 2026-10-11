# FIREBREAK × Avalanche L1 — integration plan (Mika's part)

> Branch: `mika/avalanche-l1`. Nothing from this part goes to `main` until `uv run pytest -q` is green **and** the demo runs identically with `FIREBREAK_CHAIN=off`.

## Why a blockchain in Firebreak

The engine already proves its decisions **locally**: hash-chained audit log (`audit.py`), Ed25519-signed alerts (`federation.py`). But `audit.py` says it itself:

> "the chain proves the log was not modified by someone who doesn't recompute all the following hashes. To protect against that, the last hash (`head`) must be anchored externally."

That's exactly the L1's role: **a timestamped witness, shared by the companies, that nobody can rewrite after the fact.** Three proofs, and no commercial data on-chain:

| Proof | Question it answers | On the chain |
|---|---|---|
| **Audit anchor** | "Is this log really the one that existed at 14:05, or has it been rewritten since?" | `head` (sha256) + number of entries, per company |
| **Alert anchor** | "Was the distributor warned, and when?" (disputes, insurance, NIS2) | sha256 of the signed alert + sender + recipient + type + acknowledgment |
| **Incident declaration** | "Who declared the supplier compromised, since when, and at what time?" | source id + `since` + declaration hash |

Bonus: a **directory of the members' Ed25519 public keys**, and access control in the contract (`onlyMember`) that prevents an outside company from declaring a fake incident to paralyze a competitor. (Mika's L1 does not have `TxAllowList` enabled, checked on 11/10: filtering is therefore done at the contract level, not the chain level. Enabling the allowlist would require recreating the L1: keep it for the "vision" slide.)

## What we DO NOT put on the chain

Records, amounts, bank details, labels, opaque tokens, taint paths. Company identifiers are passed as `bytes32 = sha256("firebreak:company:" + id)`.

## Non-negotiable principles

1. **The chain decides nothing and blocks nothing.** The engine works identically without it. It adds proofs.
2. **Never blocking.** Every on-chain write goes through a background queue. A slow or unreachable L1 → `pending` / `failed` status in the API, never a 500 error or added latency on `/api/state` (< 200 ms).
3. **Disabled by default.** `FIREBREAK_CHAIN=off` (default) → no network import, no call. `FIREBREAK_DEMO=1` keeps its "zero network" mode unless `FIREBREAK_CHAIN=l1` is set explicitly.
4. **Tests without network.** Contracts are tested in Python with an in-memory EVM (`eth-tester` / `py-evm`). The real L1 is only used by the deployment script and the demo.
5. **No secrets in the repo.** Mnemonic and keys in `.env.local` (ignored by Git). **An agent never reads, never displays, never copies** `.env`, `.env.local` or Mika's `L1 blockchain/` folder.
6. **We add to the API, we don't break anything.** New endpoints under `/api/chain/…`, new optional fields elsewhere. `docs/api.md` updated.

## Architecture

```
                 Firebreak (unchanged)                        │      Avalanche L1 (Mika)
                                                              │
  Simulation ──► audit.py (hash-chained audit logs) ────┐     │
       │                                                │     │
       └──────► federation.py (signed alerts) ──────────┤     │
                                                        ▼     │
                       src/firebreak/chain/anchoring.py       │
                       (observes the API actions,             │
                        computes the hashes to anchor)        │
                                   │                          │
                                   ▼                          │
                       src/firebreak/chain/client.py          │
                       queue + sender thread ─────────────────┼──► FirebreakRegistry.sol
                       NullChain | TesterChain | Web3Chain    │      registerMember / pubkey
                                   │                          │      declareIncident
                                   ▼                          │      anchorAlert / acknowledgeAlert
                       /api/chain/status, /api/chain/anchors, │      anchorAudit
                       /api/audit/verify (+ onchain field)    │      (events = timestamped proof)
                                   │                          │
                                   ▼                          │
                       web/index.html: "Avalanche" panel      │
```

## Added file tree

```
contracts/
  FirebreakRegistry.sol          # the contract (only one)
  build/FirebreakRegistry.json   # compiled ABI + bytecode, versioned (the server does not need solc)
  deployments/l1.json            # address, chainId, deployment block, members (no secrets)
src/firebreak/chain/
  __init__.py
  config.py                      # reads env + .env.local, no new dependency
  ids.py                         # company_id → bytes32, alert hash, declaration hash
  accounts.py                    # EVM accounts derived from the mnemonic (admin + 4 companies)
  artifact.py                    # loads contracts/build/FirebreakRegistry.json
  deployer.py                    # deploys + registers the members (scripts, tests, tester mode)
  client.py                      # interface ChainClient + NullChain + Web3Chain + worker
  anchoring.py                   # what gets anchored after each action
scripts/
  chain_compile.py               # solc → contracts/build/
  chain_deploy.py                # deploys, registers the members, (allowlist), writes deployments/l1.json
  chain_smoke.py                 # checks RPC, chainId, balance, contract read
tests/
  test_chain_contract.py         # contract on an in-memory EVM
  test_chain_client.py           # client, queue, fallback, ids
  test_chain_api.py              # endpoints, on-chain audit verify, rewrite detected
docs/avalanche/                  # this folder
```

## Configuration (`.env.local`, never committed — full template in [sheet 00](tasks/00-setup.md))

| Variable | Role |
|---|---|
| `FIREBREAK_CHAIN` | `off` (default) · `tester` (in-memory EVM, for dev/tests) · `l1` (real L1) |
| `FIREBREAK_CHAIN_RPC_URL` | RPC URL of Mika's L1 |
| `FIREBREAK_CHAIN_ID` | chainId of the L1 (checked at startup, refused if different) |
| `FIREBREAK_CHAIN_EXPLORER_URL` | explorer base URL, for `…/tx/<hash>` links (optional) |
| `FIREBREAK_CHAIN_MNEMONIC` | mnemonic of the dedicated test wallet (account 0 = admin, 1..4 = companies) |
| `FIREBREAK_CHAIN_DEPLOYMENT` | path of the deployment file (default `contracts/deployments/l1.json`) |
| `FIREBREAK_KEY_SEED`, `FIREBREAK_PAIR_SECRET` | already used by `federation.py`; **must be fixed** when the chain is active, otherwise the Ed25519 keys change at every launch and no longer match those registered on-chain |

## API contract additions (summary, details in task 04)

| Endpoint | Role |
|---|---|
| `GET /api/chain/status` | `mode`, `connected`, `chain_id`, `contract`, `explorer_url`, `last_block`, `queue` (pending/sent/failed) |
| `GET /api/chain/anchors` | List of anchors: `kind` (audit/alert/incident/ack), `company`, `hash`, `status`, `tx_hash`, `block`, `explorer_link`, `ts` |
| `POST /api/chain/anchor` | Forces immediate anchoring of the log heads |
| `GET /api/audit/verify` | **Added** per log: `onchain: {anchored_head, anchored_entries, block, tx_hash, matches}` (null if chain off) |
| `POST /api/demo/rewrite` | Demo only (`FIREBREAK_DEMO=1`): rewrites a log **recomputing every hash** — the local check says OK, the on-chain anchor says NO |

## The demo's big moment

1. Compromise → alerts and logs are anchored: the Avalanche panel shows the transactions, with links to the explorer.
2. "An attacker, or an employee, rewrites the manufacturer's log to erase the fact that it was warned at 14:05, and recomputes every hash." → `POST /api/demo/rewrite`.
3. Local check: **intact** (the rewrite is consistent). On-chain check: **does not match** the hash anchored at block N. The fraud is proven by a witness nobody controls.

## Task order

| # | Sheet | Depends on | Parallelizable |
|---|---|---|---|
| 00 | [Setup](tasks/00-setup.md) | — | **Mika, by hand** (tooling + L1 info) |
| 01 | [FirebreakRegistry contract](tasks/01-contract.md) | 00 | — |
| 02 | [Deployment on the L1](tasks/02-deploy.md) | 01 | with 03 |
| 03 | [Python client and anchoring](tasks/03-chain-client.md) | 01 (ABI) | with 02 |
| 04 | [API](tasks/04-api.md) | 03 | — |
| 05 | [Dashboard, demo and pitch](tasks/05-dashboard-demo.md) | 04 (+ 02 for the real L1) | — |

Each sheet is self-contained: an agent reads it along with this README and [the common rules](tasks/RULES.md), and nothing else is needed.

## Open questions for Mika

- chainId, RPC URL and explorer of the L1 (to put in `.env.local` and in sheet 00).
- Precompiles enabled: `TxAllowList`? `ContractDeployerAllowList`? Is the admin account an admin on them?
- Is the mnemonic in `.env` the one to use (account 0 = the one holding the AVAX)?
- Merge into `main`: before the 10:00 freeze, or present the L1 as a separate demo if the merge is too risky?

## Split between agents (approved on 11/10 at 01:05, see `docs/agents-canal.md` on `main`)

| Agent | Branch | Files |
|---|---|---|
| `mika/pc1` (integrator, has the final say) | `mika/avalanche-l1` | `pyproject.toml`, `uv.lock`, `src/firebreak/chain/{__init__,config,ids,accounts,artifact,deployer}.py`, `contracts/`, `scripts/chain_*.py`, `tests/test_chain_{contract,deploy,ids}.py` — tasks 01 and 02 |
| `mika/pc2` | `mika/avalanche-l1-api` | `src/firebreak/chain/{client,anchoring,tamper}.py`, `src/firebreak/api.py`, `schemas.py`, `docs/api.md`, `web/index.html`, `docs/demo.md`, `tests/test_chain_{client,api}.py` — tasks 03, 04, 05 |

The exact interface contract of pc1's modules is in the message `mika/pc1 → mika/pc2 · 01:05` in the channel.
