# Demo sheet — Avalanche, quality, goods receipts

> Complements `docs/demo.md` (main demo, `/app/` interface). These three sequences are shown from the **dashboard** (`http://localhost:8000/`), collapsible panels on the right. Figures: the ones on screen.

## Before going on stage (Mika's machine, `.env.local` in `l1` mode)

```bash
uv run python scripts/chain_smoke.py          # RPC reachable, chainId 569712, contract 0xeA4BeAe1… present
FIREBREAK_DEMO=1 uv run uvicorn firebreak.api:app --port 8000
```
PowerShell: `$env:PYTHONUTF8='1'; $env:FIREBREAK_DEMO='1'; uv run uvicorn firebreak.api:app --port 8000`.
Without `.env.local` or without network: `FIREBREAK_CHAIN=tester` (in-memory EVM) — in that case, do not say "our L1".

**Run the main demo 1 to 2 minutes before opening the Avalanche panel**: the anchoring queue must be empty (~40 s for the full demo on the real L1).

## Sequence 1 — Avalanche (30 s), after the main demo

1. Open **Avalanche**: green dot, list of confirmed anchors (links to the explorer).
   "Every alert, every acknowledgment, every log is anchored on our Avalanche L1: a timestamped witness nobody can rewrite."
2. **Verify on Avalanche** → local ✓, Avalanche ✓.
3. **Simulate a log rewrite** → local ✓, Avalanche ✗.
   "Someone erased from the manufacturer's log the fact that it had been warned, and recomputed every hash. The local check sees nothing. Avalanche does."

## Sequence 2 — Goods receipts (40 s), `mixed` scenario

1. Reset to **Mixed attack**. Open **Stock entries**, company **fabricant**, **Check receipts**.
2. Show the red card: goods receipt BC-9999, **30/100 · suspect · ON HOLD** — unknown order, out-of-sequence certificate, changed bank details.
   "Before it even enters stock, the rigged lot is scored, explained and put on hold."
3. **Reject** → "signed quality report sent to the supplier". The lot and everything depending on it stay isolated.
4. Orange card: 2:45 pm delivery, **65/100 · doubtful · physically checked · to watch** (no certificate, bank details changed the same day), **not put on hold**: it was already physically inspected on receipt.
   "A human check already done counts: we flag the doubt without blocking. Rules propose, humans decide, case by case."
   (To show **Accept**: `cert` scenario, the coil that was weighed but has the fake certificate is on hold — 55/100 —; or reject the rigged coil from the `mixed` scenario as in step 3.)

## Sequence 3 — Quality recall (60 s), `recall` scenario

**Quality (debug)** panel, pre-filled by the scenario.
1. Company **client**, reference `c-gr-03`, reason "broke on site" → **Report upstream** (to the distributor). "The customer doesn't know the coil: it reports what it received."
2. Company **distributeur** → **Confirm** in the inbox; then reference `d-out-03` → **Report upstream** (to the manufacturer).
3. Company **fabricant**, reference `m-ship-03` → **Recall analysis**: possible causes, each with its scope. "The analyst chooses."
4. Reference `COIL-103` → **Suspect lot**: the sibling lot LOT-A30, already shipped, is isolated too; the other lots keep going.
5. `COIL-103` → **Report upstream** (to the supplier); company **fournisseur** → **Confirm**.
   "At no point was the supplier blacklisted."

## Figures measured on the real L1 (quote them as such)

- Full demo: 19 proofs, ~38 s, 0 failures. Full recall: 25 proofs, ~86 s. Goods receipts (mixed): 16 proofs, ~25 s.
- The interface never depends on the chain: every action responds in a few tens of milliseconds.
- Demo: a single validator (node hosted by the Builder Hub). In production: the validators are the consortium members.

## If it breaks

- Chain slow or unreachable: the demo keeps going, anchors go to "pending" or "failed"; don't open the Avalanche panel, say "anchoring catches up afterwards".
- Online plan B: https://firebreak-zeta.vercel.app (without Avalanche).
