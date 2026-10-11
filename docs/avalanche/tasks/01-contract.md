# Task 01 — `FirebreakRegistry` contract + compilation + tests

First read `docs/avalanche/README.md` and `docs/avalanche/tasks/RULES.md`.

## Goal

A single Solidity contract, small and readable, that serves as a timestamped witness for Firebreak. Compiled from Python, tested on an in-memory EVM. No network access.

## Dependencies to add (dev group)

`uv add --dev py-solc-x "eth-tester[py-evm]"` and `uv add web3` — stable versions published at least 7 days ago. `web3` is also used by tasks 02 and 03.

## The contract — `contracts/FirebreakRegistry.sol`

- `pragma solidity 0.8.24;`, compiled with **`evmVersion: "paris"`** (no `PUSH0`, compatible with any Subnet-EVM L1). If the `avalanche-docs` MCP is available, check the EVM version supported by Subnet-EVM and note it in your report.
- No OpenZeppelin dependency: everything fits in ~150 lines.

### State

```solidity
address public admin;
struct Member { bytes32 companyId; bytes32 ed25519PubKey; bool active; }
mapping(address => Member) public members;            // EVM account → company
mapping(bytes32 => address) public accountOf;         // companyId → EVM account
mapping(bytes32 => bytes32) public pubKeyOf;          // companyId → Ed25519 public key (32 bytes)

struct AlertRecord { bytes32 fromCompany; bytes32 toCompany; uint8 alertType; uint64 anchoredAt; uint64 ackAt; }
mapping(bytes32 => AlertRecord) public alerts;        // alertHash → record

struct AuditAnchor { bytes32 head; uint32 entries; uint64 anchoredAt; }
mapping(bytes32 => mapping(bytes32 => AuditAnchor)) public latestAudit; // runId → companyId → latest anchor
```

### Functions

| Function | Who | Effect |
|---|---|---|
| `constructor()` | — | `admin = msg.sender` |
| `registerMember(address account, bytes32 companyId, bytes32 pubKey)` | admin | creates or updates an active member; rejects a `companyId` already linked to another account |
| `deactivateMember(address account)` | admin | `active = false` |
| `declareIncident(bytes32 runId, bytes32 sourceCompany, uint64 since, bytes32 declarationHash)` | active member | event `IncidentDeclared(runId, declarer, sourceCompany, since, declarationHash, block.timestamp)` |
| `withdrawIncident(bytes32 runId, bytes32 sourceCompany, bytes32 declarationHash)` | active member | event `IncidentWithdrawn(...)` |
| `anchorAlert(bytes32 runId, bytes32 alertHash, bytes32 toCompany, uint8 alertType)` | active member = sender | rejects an already anchored `alertHash`; `alertType` 0 = taint, 1 = release; stores; event `AlertAnchored(runId, alertHash, from, to, alertType, block.timestamp)` |
| `acknowledgeAlert(bytes32 alertHash)` | active member = recipient | rejects if unknown or already acknowledged; event `AlertAcknowledged(alertHash, to, block.timestamp)` |
| `anchorAudit(bytes32 runId, bytes32 head, uint32 entries)` | active member | rejects if `entries` < last anchor of the same run (a log doesn't get shorter); stores; event `AuditAnchored(runId, company, head, entries, block.timestamp)` |
| `transferAdmin(address)` | admin | — |

- `runId`: identifier of a demo session (one `reset` = a new run), so that multiple demos don't get mixed up.
- Custom Solidity errors (`error NotAdmin(); error NotMember(); …`) rather than strings.
- All events have their key fields `indexed` (runId, companyId, alertHash).

## Compilation — `scripts/chain_compile.py`

- Installs the requested solc version via `py-solc-x` if missing, compiles with the optimizer (200 runs) and `evmVersion: "paris"`.
- Writes `contracts/build/FirebreakRegistry.json`: `{"contractName", "abi", "bytecode", "solcVersion", "evmVersion", "sourceSha256"}`. This file is **committed** (the server won't need solc).
- Idempotent: rerunning without a source change doesn't modify the file.

## Tests — `tests/test_chain_contract.py`

On `EthereumTesterProvider` (web3 + eth-tester), loading `contracts/build/FirebreakRegistry.json`. At minimum:

- admin registers 4 members; a non-admin cannot register;
- a non-member can neither declare nor anchor (that's the "no outsider declares a fake incident" argument);
- `anchorAlert` by the sender → `alerts(hash)` filled, event emitted; re-anchoring the same hash → revert;
- `acknowledgeAlert` only by the recipient; double acknowledgment → revert;
- `anchorAudit`: stores, rejects a decreasing number of entries, accepts a new `runId` starting from zero;
- deactivated member → no more writes;
- a test that checks that `contracts/build/…json` does match the current source (`sourceSha256`), so we don't forget to recompile.

## Done when

- `uv run python scripts/chain_compile.py` produces the JSON.
- `uv run pytest -q` green (all tests in the repo).
- Commit `chain: contrat FirebreakRegistry, compilation et tests` on `mika/avalanche-l1`.
- Report: exact signatures of the functions and events (task 03 depends on them), solc version, bytecode size.
