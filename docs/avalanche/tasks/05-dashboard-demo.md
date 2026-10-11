# Task 05 — Dashboard, demo script and pitch material

First read `docs/avalanche/README.md`, `docs/avalanche/tasks/RULES.md`, `docs/api.md` (Avalanche section), `docs/demo.md`, then `web/index.html`.

## 1. "Avalanche" panel in `web/index.html`

`web/index.html` is Yann's debug dashboard: add a **collapsible** panel, without touching the rest of the layout or the existing behavior. It only shows if `GET /api/chain/status` responds with `mode != "off"`.

- Header: green/red `connected` dot, chainId, contract address (shortened, explorer link), shortened `run_id`, queue counters.
- List of anchors (`/api/chain/anchors`, refreshed every 2 s): icon per `kind`, company, shortened hash, status (badge), `tx` link to the explorer.
- On each existing animated alert (dotted lines between companies): when the corresponding anchor is `confirmed`, show a small "anchored · block N" badge.
- "Verify on Avalanche" button → `/api/audit/verify`, shows local ✓/✗ and on-chain ✓/✗ per company.
- If `FIREBREAK_DEMO=1`: "Simulate a log rewrite" button → `POST /api/demo/rewrite` then automatic re-check.

User-visible texts in English (decision of Mika on 11/10, whole repo translated). No new library.

## 2. Demo control

If `POST /api/demo/step` and `src/firebreak/demo.py` allow it **without modifying the existing steps**, add two optional steps at the end, active only when the chain is active:
- "Proofs anchored on Avalanche" (on-chain check, all green);
- "Log rewrite" (rewrite + check: local green, on-chain red).

If that requires touching the existing sequence, don't do it: document the manual sequence in `docs/demo.md` instead.

## 3. `docs/demo.md`

Add an "Avalanche L1 (optional)" section: launch (`FIREBREAK_CHAIN=l1`, prerequisite `chain_smoke.py`), each click, what you see, the line to say. Suggested lines:

- "Every alert and every log is anchored on our Avalanche L1: a timestamped witness that neither the supplier, nor the customer, nor we can rewrite."
- "Only chain members can write: an outside company can't declare a fake incident to paralyze a competitor."
- "Here someone rewrites the manufacturer's log to erase the fact that it was warned, and recomputes every hash. The local check sees nothing. Avalanche does."
- "No commercial data on the chain: only fingerprints."

## 4. `docs/avalanche/pitch.md`

One page for the "Why a blockchain" slide: the 3 proofs (audit, alerts, incidents), what isn't on-chain, why a dedicated L1 (member allowlist, cost, consortium sovereignty), the TradeLens lesson (we don't impose a shared data registry, only fingerprints), and the real figures read on the L1 during rehearsal (number of transactions in a demo, average confirmation time measured via `/api/chain/anchors`).

## Tests

No UI test. `uv run pytest -q` must stay green. Check by hand in `tester` mode that the panel shows, and in `off` mode that it's absent.

## Done when

- Commit `chain: panneau Avalanche, démo et pitch`.
- Report: screenshots or a description of what's displayed, and the list of what remains to do before merging into `main`.
