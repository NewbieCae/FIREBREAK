# Task 03 — Python client and anchoring

First read `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, the task 01 report, then `src/firebreak/audit.py`, `src/firebreak/federation.py` and `src/firebreak/simulation.py` (read-only).

## Goal

A `src/firebreak/chain/` layer that turns Firebreak's actions into on-chain writes, **without ever slowing down or breaking** the engine or the API.

## `config.py`

- `load_chain_config() -> ChainConfig` (frozen dataclass): reads the variables from `docs/avalanche/README.md` from `os.environ`, after loading `.env.local` at the root **if it exists** with a small homemade parser (`CLE=valeur`, `#` lines ignored, doesn't overwrite a variable already present). No new dependency.
- `mode` ∈ `off | tester | l1`, default `off`. Unknown value → `off` + warning.
- `__repr__` never shows the mnemonic.

## `ids.py` (pure functions)

- `company_id(cid: str) -> bytes`: `sha256(b"firebreak:company:" + cid)`, 32 bytes.
- `run_id() -> bytes`: 32 random bytes, one per simulation.
- `alert_hash(alert: Alert) -> bytes`: `sha256(json canonique de alert.payload() + "|" + alert.signature)`. Same canonicalization as `federation._canonical` (reimplement it identically rather than importing a private name, and add a test comparing the two).
- `declaration_hash(company, since_iso, declarer) -> bytes`.
- `hex32(b: bytes) -> str`: `0x` + 64 hex.

## `client.py`

```python
class ChainClient(Protocol):
    mode: str
    def submit(self, op: ChainOp) -> AnchorRecord: ...      # non-blocking: enqueues, returns status="pending"
    def anchors(self) -> list[AnchorRecord]: ...
    def status(self) -> dict: ...
    def read_audit_anchor(self, run_id: bytes, company: str) -> dict | None: ...  # on-chain read, short timeout
    def flush(self, timeout: float) -> None: ...             # for tests and POST /api/chain/anchor
```

- `ChainOp`: `kind` (`audit` | `alert` | `ack` | `incident` | `incident_withdrawn`), `company` (who signs the tx), contract arguments.
- `AnchorRecord`: `id`, `kind`, `company`, `hash` (hex), `status` (`pending` | `sent` | `confirmed` | `failed`), `tx_hash`, `block`, `error` (short, no secrets), `created_at`, `explorer_link`.
- **`NullChain`** (`off` mode): `submit` returns a record with `status="disabled"` and does nothing. Does not import `web3`.
- **`Web3Chain`** (`tester` and `l1` modes): a **single sender thread** consumes a `queue.Queue`. One account per company (derived from the mnemonic as in task 02; tests: public mnemonic); per-account nonce management; `wait_for_transaction_receipt` with timeout; 2 attempts then `failed`. Every exception is caught and stored in `error`. `tester` uses `EthereumTesterProvider` and deploys the contract + registers the members at startup (handy for developing without an L1).
- `get_chain_client(config) -> ChainClient`: factory based on the mode. In `l1` mode, if the RPC is unreachable or the chainId doesn't match, returns a client whose `status()["connected"]` is `false` and whose `submit` calls all end up `failed` — never an exception at server startup.

## `anchoring.py`

```python
class Anchorer:
    def __init__(self, client: ChainClient): ...
    def on_new_simulation(self, sim) -> None              # new run_id, remembers the positions
    def after_action(self, sim, action: str) -> None      # called by the API after compromise / withdraw / remediate / reset / demo step
```

`after_action`:
1. For each **new** alert in `sim.federation.alerts` since the last call: `anchorAlert` signed by the sender; if the alert is `verified` on the recipient's side, `acknowledgeAlert` signed by the recipient.
2. For each **new** `declaration` / `declaration_withdrawn` audit entry: `declareIncident` / `withdrawIncident`.
3. For each log whose length has changed: `anchorAudit(run_id, head, entries)` signed by the company.
4. Only reads public simulation data; modifies nothing.

## Tests — `tests/test_chain_client.py`

- `config`: default `off`; `.env.local` read without overwriting the environment; `repr` without mnemonic.
- `ids`: stability, length, `alert_hash` identical for the same alert, different if the signature changes.
- `NullChain`: does not import `web3` (check `sys.modules` in a subprocess).
- `Web3Chain` in `tester` mode: after `build_simulation` + `declare_compromise` + `Anchorer.after_action` + `flush`, alerts are anchored and acknowledged, the log heads read on-chain equal the local `head` values.
- Failure: a fake provider that raises → `failed` records, no exception propagated, the API (if tested) stays fast.

## Done when

- `uv run pytest -q` green.
- Commit `chain: client, file d'envoi et ancrage des alertes et journaux`.
- Report: how to wire `Anchorer` into `api.py` (exact call points) for task 04.
