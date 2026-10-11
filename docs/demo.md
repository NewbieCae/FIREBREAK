# FIREBREAK demo script — 3 minutes

Launch: `bash scripts/demo.sh` (uv sync → server in demo mode on
:8000 → browser). **The final interface** opens at
http://localhost:8000/app/; each step is done with the mouse, or with the
keyboard's **right arrow** (one press = one step, see "Final interface"
below). The debug dashboard stays at http://localhost:8000 (fallback).

All figures below are produced by a reproducible command — not
copied by hand:

```bash
uv run python -m firebreak.demo_figures
```

Measured output (`mixed` scenario, supplier compromised since 14:00):

```
== Mixed scenario, supplier compromised since 2 pm ==
records_total            = 193
blocked_operations       = 17
flowing_operations       = 176
blocked_share            = 8.8%
gates_blocked            = 4  ['m-lot-X', 'm-pay-X', 'm-ship-X', 'd-out-X']
blocked_payments_eur     = 5210
flowing_payments_eur     = 92102
companies_hit            = 4  ['client', 'distributeur', 'fabricant', 'fournisseur']
signed_alerts            = 3  [('fabricant', 'distributeur'), ('fournisseur', 'fabricant'), ('distributeur', 'client')]
timeline_steps           = 25
audit_intact             = True  (25 entries)
fraudulent_payment       = 5210 € (RIB FR76 1234 5678 9000 0000 0000 666)

== With vs without Firebreak (policy C vs B) ==
B    Without Firebreak blocked  54  healthy blocked  42  leaks 5  gates 18  activity preserved 76.1 %
C    With Firebreak    blocked  17  healthy blocked   0  leaks 0  gates 4  activity preserved 100.0 %
ratio                    = infinite (0 healthy blocked with Firebreak)

== The 6 scenarios ==
mixed  blocked  17/193  gates 4  payments blocked 5210 €
rib    blocked   8/185  gates 1  payments blocked 5210 €
cert   blocked  13/193  gates 4  payments blocked 0 €
asn    blocked  13/190  gates 3  payments blocked 0 €
lot    blocked   0/175  gates 0  payments blocked 0 €
recall blocked   0/175  gates 0  payments blocked 0 €
```

`lot` and `recall` show 0 blocked here because they are quality incidents, not
compromises: their figures come from the quality flow (see [qualite.md](qualite.md)).

## Final interface (`/app/`) — the five steps

A single page. The right arrow moves through the steps; everything stays clickable with the mouse.

| → | Step | On screen | What to say |
|---|---|---|---|
| — | **Idle** | The chain is alive: 4 glass panels, 193 breathing dots, green particles flowing between companies. | "Four companies, 193 operations, everything is running." |
| 1 | **Declare** (coral button at the bottom, "Declare the supplier compromised since 14:00") | Coral wave over Aciers Durand, dots turn red one by one, lines follow the dependencies, sealed envelopes fly downstream, padlocks on irreversible actions; the three figures climb; the feed scrolls on the right. | "17 blocked out of 193. Not 193. The green dots keep flowing: we didn't stop the factory." |
| 2 | **With vs without** | Two panels slide in from the edges. Left: supplier and manufacturer hatched "cut off", 42 healthy blocked, 5 leaks blinking at the distributor and the customer. Right: 17 precise reds, 0, 0. Precision / recall gauges, test bench, JLR and CDK. | "Without us: 54 blocked, 42 for nothing, and 5 leaks. With us: 17, 0, 0." |
| 3 | **Prove** | Drawer on the €5,210 payment: bank details, path from the signed alert (opaque token, verified signature), explanation, recovery plan. | "The graph decides, the AI explains." |
| 4 | **Heal** | Remediation of goods receipt BC-9999 (human approval): amber dot, cascading release down to the customer, signed release alerts. The fraudulent payment stays blocked. | "And partners are notified, without seeing our data." |
| 5 | **Verify** | Toast "Audit logs intact: N entries, 4 hash chains verified."; each panel shows the head of its hash chain. | "Everything is logged and verifiable." |

If you restart the demo: the right arrow starts again from a clean scene on its own (automatic reset if a remediation or a withdrawal left records "released"). With the mouse: **Reset** before each rehearsal.

With Avalanche (`FIREBREAK_CHAIN=tester` or `l1`): an "Avalanche · N anchored" badge appears in the header (click → list of anchors); each company's audit log shows "Anchored on Avalanche, block N: the log matches"; in demo mode, **Simulate a log rewrite (demo)** shows a local chain that is still consistent but no longer matches the anchor. Chain off: none of this appears.

Bonus if there's time: **View as** (top) → Distributor: the other ledgers turn to frosted glass, only signed alerts get through. **Import** → "Invoice with changed bank details": the AI reads the PDF, a human confirms, the invoice arrives in red. **False alarm**: everything turns back to green in a cascade.

## Debug dashboard — one click on "Demo: next step →" = one step

| Click | API action | On screen | What to say |
|---|---|---|---|
| 1 | `POST /api/demo/step` → reset `mixed` | Green graph: 4 columns (Aciers Durand → Mécano Précision Loire → Logidis Rhône → Bâtiments Azur), 193 operations, counters at zero. | "Here's a normal supply chain on an ordinary day: orders, certificates, shipments, payments." |
| 2 | step 1 → `compromise` | 25 timeline steps: records turn red one by one, alerts travel as dotted lines between companies, counters update live. **"Replay" button** to watch the propagation again. | "The supplier has been compromised since 14:00. Firebreak blocks 17 operations out of 193 — 8.8% — and lets the other 176 run. The €5,210 payment to the changed bank account is blocked." |
| 3 | step 2 → `GET /api/compare` | **Split screen**: on the left "Without Firebreak" (cut-off perimeter in grey/red, orange leaks to the distributor and the customer), on the right "With Firebreak" (17 precise reds, zero collateral). Banner: bench figures over 500 chains + real-world examples JLR/CDK. | "Without Firebreak, you cut off the supplier and its direct customers: 54 operations blocked, 42 of them healthy — a whole afternoon of production halted — and 5 contaminated operations still leak to the customer. With Firebreak: 17 blocked, all contaminated, zero healthy blocked, zero leaks. Over 500 simulated chains, that's 9.6 healthy operations blocked versus 43.2 — 4.5 times less collateral damage, with better recall (source: `docs/bench-results.md`)." |
| 4 | step 3 → explain `m-pay-X` | Panel: plain-language explanation + contamination path `m-inv-X → m-pay-X` + remediation plan. | "Every block can be proven: this payment depends on the invoice received after 14:00. It's not an AI score, it's the graph." |
| 5 | step 4 → remediate `m-gr-X` (human approval) | `m-gr-X` turns blue (`released`); the release propagates: downstream nodes turn green again, signed "release" alerts go to the distributor and the customer. | "Remediation releases everything that only depended on it — and partners are notified by signed alerts, without ever seeing their commercial data." |
| 6 | step 5 → audit verify | "Logs: intact" — 25 entries in total, hash-chained in each company's log. | "Everything is logged and verifiable: an auditor can replay every decision." |

Clicking again stays at the end of the demo ("Demo finished…").

## Fallback answers if you're questioned

- **Stop rule**: `m-gr-08` (physically inspected receipt) stays green
  despite a contaminated seed — the `verified` rule stops propagation.
- **Other scenarios** (selector at the top): `rib` (8 blocked, 1 gate,
  €5,210), `cert` (13 blocked, lot genealogy LOT-901/902 + ASM-950),
  `asn` (13 blocked, phantom stock all the way to the site schedule).
- **API**: http://localhost:8000/docs — everything the dashboard does is
  documented in [api.md](api.md).

## Avalanche L1 (optional)

No existing step changes. The chain only turns on if you ask for it.

**Launch** (no network, in-memory EVM):
`FIREBREAK_DEMO=1 FIREBREAK_CHAIN=tester bash scripts/demo.sh`.
On the real L1: `FIREBREAK_CHAIN=l1` once `scripts/chain_smoke.py` is green
(configuration in `.env.local`, never committed). Also set
`FIREBREAK_KEY_SEED` and `FIREBREAK_PAIR_SECRET`.

| Click | What you see | What you say |
|---|---|---|
| Open the "Avalanche" panel (right column) | green dot, chainId, contract, anchoring queue | "Every alert and every log is anchored on our Avalanche L1: a timestamped witness, out of reach of whoever holds the log." (If asked: in the demo, a single validator; in production, the consortium members.) |
| The demo's "compromise" step | `alert`, `ack`, `incident`, `audit` anchors switch to *confirmed* with a block number | "Only chain members can write: an outside company can't declare a fake incident to paralyze a competitor." |
| "Verify on Avalanche" | for each company: local ✓, Avalanche ✓ | "No commercial data on the chain: only fingerprints." |
| "Simulate a log rewrite" | local ✓, **Avalanche ✗** for the manufacturer | "Here someone rewrites the manufacturer's log to erase the fact that it was warned, and recomputes every hash. The local check sees nothing. Avalanche does." |

The rewrite button requires `FIREBREAK_DEMO=1`. After a rewrite,
"Reset" starts again from a clean log (new `run_id`). If the L1 is
slow or down, anchors stay `pending` or `failed`: the demo
keeps going, the chain is never blocking. The demo steps are not
modified: the sequence above is done by hand.
