# Pitch — why Avalanche

## The 3 proofs (30 seconds)

1. **Who warned whom, and when.** Every inter-company alert is
   anchored on our L1: a timestamp nobody can rewrite after the fact.
2. **The log hasn't been touched.** The head of each company's audit log
   is anchored. If someone rewrites their log and recomputes the
   hashes, the local check sees nothing, Avalanche does (demo button).
3. **Only members write.** The contract only accepts the addresses of the
   federation's companies: nobody can declare a fake incident
   to paralyze a competitor.

## What is NOT on-chain

No commercial data: no amounts, no bank details, no lots, no supplier
names. Only fingerprints (hashes), opaque identifiers and
timestamps. The data stays at each company.

## Why a dedicated L1

- A consortium chain: known members, no unpredictable fees, no
  data exposed on a public network.
- Access control decided by the members: the contract only accepts the
  federation's companies.
- **Say it honestly**: in the demo, our L1 has **only one validator**
  (node hosted by Avalanche's Builder Hub) and the contract admin
  is the team. In production, the validators are the consortium
  members: that's what makes the proof independent of any single party.
- Don't promise "sub-second" finality: on our L1,
  a proof is confirmed in 2 to 4 s, including waiting for the receipt (measurements
  below).

## The TradeLens lesson

TradeLens (Maersk / IBM) announced its shutdown at the end of 2022 and closed in early 2023: competitors refused to
hand their flows to a platform controlled by a single player. FIREBREAK
avoids this trap: only proofs go on it, not the data, and the chain is
meant to be validated by the consortium members (in the demo: a single
validator, see above).

## Figures measured on the real L1

The team's Avalanche L1 (chainId 569712, contract
`0xeA4BeAe1262B7BD19e3A18B1245ef100A454F0FC` since 04:00 — "quality report"
type added; the measurements below were taken on the
previous deployment `0x28cE7fcb…`, with the same anchoring code —, explorer
https://2hxmvtcr.firn.gg), measured by pc1 on 11/10 between 01:50 and 03:40:

- **Demo steps respond in 16 ms** (median, max 31 ms): anchoring
  goes into a background queue, off the request path.
- **"mixed" scenario + compromise: 12 proofs** (3 signed alerts,
  3 acknowledgments, declaration, 4 logs), confirmed in ~24 s,
  i.e. ~2 s per transaction. Two runs in a row: 24/24 confirmed.
- **Full demo (6 steps of `/api/demo/step`): 19 proofs**, queue emptied
  ~70 s after the last step (~3.7 s per transaction, sequential sending).
  Two runs: 17/19 then 19/19. The 2 failures in the first run were
  one-off network errors (managed node rate limiting), not
  reproduced; retry fix in progress.
- **"Verify on Avalanche"** (reading the 4 anchored logs): ~3.4 s,
  all matching. **Rewrite of the manufacturer's log**: local check
  "intact", Avalanche check "does not match".
- **`recall` scenario (quality recall, contract `0xeA4B…`, 04:05)**: the
  customer reports a breakage, the distributor confirms and escalates, the manufacturer
  analyzes and declares coil COIL-103 suspect, the supplier confirms.
  20 operations isolated, supplier never declared compromised. **25 proofs
  anchored, 25 confirmed, 0 failures** (logs, alerts, quality reports,
  acknowledgments, declaration); local and Avalanche checks
  matching. The API responds in 0.1 s for the 5 actions; the queue took ~127 s
  to empty (sequential sending, ~5 s per proof) — parallel sending per
  company in progress to reduce this delay.
- **After optimization (04:25, fewer requests per transaction: local
  nonce, fixed gas, cached price)**: full demo **19/19 in ~38 s** (instead
  of ~70 s), `recall` scenario **25/25 in ~86 s** (instead of ~130 s), 0 failures,
  check matching, rewrite detected. The remaining limit is the throughput
  of the hosted node (one block every ~2 s, rejections if too many requests).
- For the pitch: say "a proof is on the chain within a few seconds,
  and the demo never waits for the chain". Start the demo **one minute before**
  showing the Avalanche panel, so the queue is empty.

Measurements on the in-memory EVM (`tester` mode, pc2) for comparison: 19
proofs in ~1.5 s, ~80 ms per transaction. Never present them as
the L1's.

## If we're asked

- *"What if the chain goes down?"* The product works without it, anchoring is
  optional and non-blocking; it catches up afterwards.
- *"Why not a database?"* Whoever controls the database can
  rewrite it: the proof is only worth something if it's out of everyone's reach.
