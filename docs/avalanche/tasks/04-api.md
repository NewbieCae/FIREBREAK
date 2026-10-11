# Task 04 — Wiring the chain into the API

First read `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, `docs/api.md`, the task 03 report, then `src/firebreak/api.py` and `src/firebreak/schemas.py`.

## Golden rule

With `FIREBREAK_CHAIN=off`, **all existing responses are identical** to `main`, except for added optional fields set to `null`. Existing tests don't change.

## Wiring in `api.py`

- On load: `chain = get_chain_client(load_chain_config())`, `anchorer = Anchorer(chain)`, `anchorer.on_new_simulation(sim)`.
- After each state-changing action, **under the existing lock** `_lock`, call `anchorer.after_action(sim, "<action>")`: `POST /api/compromise`, `/api/compromise/withdraw`, `/api/records/{id}/remediate`, `/api/demo/step`, confirmed document, EPCIS import. After `POST /api/reset`: `on_new_simulation`.
- `after_action` only enqueues: measure that `/api/state` stays < 200 ms and that `POST /api/compromise` doesn't increase by more than 20 ms in `tester` mode.

## New endpoints (Pydantic models in `schemas.py`)

| Endpoint | Response |
|---|---|
| `GET /api/chain/status` | `ChainStatusOut`: `mode`, `connected`, `chain_id`, `contract`, `explorer_url`, `run_id`, `last_block`, `queue: {pending, sent, confirmed, failed}` |
| `GET /api/chain/anchors?kind=&company=` | `list[AnchorOut]` (fields of `AnchorRecord`, sorted by `created_at`) |
| `POST /api/chain/anchor` | Anchors the heads of all logs now, waits up to 5 s (`flush`), returns the list of anchors created. 409 if `off` mode. |

## Addition to `GET /api/audit/verify`

In each element of `journals`, an optional `onchain` field (null if `off` mode or nothing anchored):

```json
"onchain": {
  "anchored_head": "…", "anchored_entries": 25,
  "block": 1234, "tx_hash": "0x…", "explorer_link": "https://…/tx/0x…",
  "matches": true
}
```

`matches` = the prefix of the local log of length `anchored_entries` has `anchored_head` as its last hash. At the root level, add `onchain_ok: bool | null` (all anchored logs match).

## Rewrite demo — `POST /api/demo/rewrite`

- **Only available if `FIREBREAK_DEMO=1`**, otherwise 404.
- Body: `{"company": "fabricant", "drop_event": "alert_received"}`. Removes the first entry of that type from that company's log **and recomputes all following hashes** so the local chain stays consistent.
- To avoid touching `audit.py`, implement the rewrite in a demo module (`src/firebreak/chain/tamper.py`) that rebuilds an `AuditLog` from the modified entries and replaces it in the ledger. If that isn't possible without modifying `audit.py` or `engine.py`, stop and describe what would need to change (a decision to make with Yann).
- Expected afterwards: `/api/audit/verify` → `ok: true` (local) but `onchain_ok: false`, with `matches: false` for the manufacturer.

## Docs

- `docs/api.md`: "Avalanche L1" section with each endpoint, a real response example (`tester` mode), the `onchain` field, and the environment variables. Bump the contract version (minor).
- `docs/avalanche/README.md`: tick off the task.

## Tests — `tests/test_chain_api.py`

- `off` mode: `/api/chain/status` → `mode: "off"`; `/api/audit/verify` identical to before + `onchain: null`.
- `tester` mode: compromise → `flush` → confirmed anchors (alerts, acknowledgments, declaration, audits) → `verify` with `matches: true` everywhere.
- Rewrite: `FIREBREAK_DEMO=1`, after anchoring, `rewrite` → `ok: true`, `onchain_ok: false`.
- Without `FIREBREAK_DEMO`: `rewrite` → 404.
- The existing end-to-end demo test still passes.

## Done when

- `uv run pytest -q` green.
- Commit `chain: endpoints /api/chain, vérification on-chain de l'audit, démo de réécriture`.
