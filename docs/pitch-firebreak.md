# Firebreak — pitch, demo and questions (Track 3)

To put in `docs/pitch-firebreak.md`. Golden rule: **the only figures allowed come from `docs/bench-results.md`** (and, for the live demo, from the screen). Always say "in our simulator".

## One-sentence problem
When a partner in a supply chain is compromised, a company doesn't know which operations are contaminated: it either lets everything through or freezes everything. Firebreak isolates only what's affected, at the company and at its partners.

People helped (hypothesis to test): supply chain and IT managers at industrial SMEs, customers and suppliers of large prime contractors.

## Time breakdown (first round: 5 min + 2 min of questions)
| Time | Content |
|---|---|
| 0:00–0:30 | Hook: "A supplier gets hacked. 3 orders out of 100 are affected. Today you either freeze all 100, or let the 3 through." |
| 0:30–1:00 | Why now, for whom |
| 1:00–1:30 | The solution in three ideas |
| 1:30–3:00 | Live demo |
| 3:00–4:00 | The proof: 500 simulated worlds |
| 4:00–4:30 | Limitations, stated before anyone finds them |
| 4:30–5:00 | What's next |

Final (3 min + 3 min of questions): keep the hook, a 60 s demo, a single proof slide (p=0 and p=0.3), one sentence on limitations, one sentence on the future.

## The 8 slides
1. **Title**: Firebreak, the supply chain firewall. One sentence: "Isolate what's contaminated, not the whole business."
2. **The problem**: diagram of four companies, a hacked supplier sends fake confirmations; two bad options (cut everything off / keep going).
3. **Why now**: NIS2 requires security measures for the supply chain and incident handling. Statistics to cite as coming from secondary sources: 41.4% of ransomware attacks reportedly come from third parties (SecurityScorecard, relayed by a market report); 54% of third-party breaches reportedly also reach their suppliers' suppliers (Verizon 2024, relayed by a buyer's guide).
4. **The solution**: provenance graph → declaration (source + date) → propagation → selective quarantine → signed alerts to partners → a human releases → the proofs (alerts, acknowledgments, declarations, log heads) are anchored on an Avalanche L1. Callout: "Rules decide, AI explains, the blockchain proves."
5. **Demo**: screenshot of the interface, with the counters shown large.
6. **The proof**: p=0 / p=0.3 table (see below), one sentence on the trade-off.
7. **Limitations**: everything is simulated; missing dependencies, quantified: at p=0.3, a contaminated irreversible action gets through in 28.4% of worlds with Firebreak versus 5.0% with broad blocking, and lever D (Firebreak + caution, upper bound) brings this rate down to 20.6% (source: `docs/bench-results.md`); cautious origin rule; no validated customer; we don't detect the compromise, we contain it; Avalanche anchoring proves that a log wasn't rewritten after the fact, not that what was written in it was true.
8. **What's next**: pilots, integrations, 6 months, what we need (see below) + team.

## Demo run-through (90 seconds, rehearse 3 times)
Same steps as the final interface (`/app/`, right arrow): the screen-by-screen detail is in `docs/demo.md`. Figures: the ones on screen (`mixed` scenario, reproducible with `uv run python -m firebreak.demo_figures`).

Launch with the blockchain: `FIREBREAK_CHAIN=l1 bash scripts/demo.sh` (real L1, configuration in `.env.local`, `scripts/chain_smoke.py` green beforehand). Without this variable, `scripts/demo.sh` starts with the **chain off** and nothing from Avalanche appears. `FIREBREAK_CHAIN=tester` works without network, but it's an in-memory EVM: in that mode, don't say "our L1".

1. **Idle**: "0 operations blocked / 193 keep going". Say: "Four companies, a chain that's running."
2. **Declare** (supplier compromised since 14:00): the contamination spreads, the counters climb. Read out the number blocked, the irreversible actions blocked, the euros blocked, the euros that keep flowing.
3. **With vs without**: same attack; without Firebreak you block broadly and contaminated operations still leak.
4. **Prove**: click on the blocked payment, **exact path** back to the source, signed alert with opaque tokens (no commercial data). "The graph decides, the AI explains."
5. **Heal**: a human approves the remediation, the release cascades to partners through signed alerts.
6. **Verify**: audit logs intact. If the chain is on: "Anchored on Avalanche, block N", then **Simulate a log rewrite** → local ✓, Avalanche ✗. "The local check sees nothing. Avalanche does."
7. Safety net: if the screen crashes, play the recorded **demo video**, or the online plan B (https://firebreak-zeta.vercel.app, simulated AI). Also keep **Replay** ready. Bonus if there's time: **False alarm** (withdrawal of the declaration, everything turns back to green: "a human stays in control").

## The proof (reproduce as is)
Source: `docs/bench-results.md`, 500 worlds, 5 companies, 300 operations per world. A alert only, B blocking the supplier and its direct customers, C Firebreak.

| | A | B | C Firebreak |
|---|---|---|---|
| Healthy wrongly blocked, p=0 | 0 | 43.2 | **9.6** |
| Worlds with a leak, p=0 | 100% | 24.6% | **0%** |
| Recall, p=0 / p=0.3 | 0% | 98.5% | 100% / 93.4% |

To say: "In our simulator, with all dependencies tracked, Firebreak lets nothing through and blocks 4.5 times fewer healthy operations than broad blocking." The trade-off when dependencies are invisible is stated on the next slide (Limitations).

Not to say: "the advantage grows with the length of the chain" as if it were a discovery. The size sweep shows a gap going from 4.5x to 9x, but the generator densifies relationships as the chain grows (1.16 then 2.29 direct customers per company): part of the gap comes from the model. Keep it for questions, with this caveat.

D ("Firebreak + caution"): optional, upper bound. It catches leaks, but the cost rises with noise (about 1.8 healthy operations blocked per leak caught with no noise, 3.1 at 10%, 7.0 at 30%).

## What's next (slide 8) — hypotheses, present them as such
- **Months 1–2: two pilots** with industrial SMEs or their prime contractors, in "unilateral" mode: track what comes in from a supplier without requiring it to install anything.
- **Months 2–4: connectors** to existing flows (EPCIS, EDI, ERP), document reading (emails, shipping notices).
- **Months 3–5: measurement on real data**: replay 90 days of operations to show what would have been isolated during a past incident.
- **Months 4–6: network mode** (signed alerts between partners) and NIS2 mapping.
- **What we need**: two or three pilot partners, access to anonymized real flows, a compliance opinion.
- First target customers (hypothesis): mid-sized industrial subcontractors subject to their prime contractors' security requirements; supply chain software vendors who would want to integrate it.

## Likely questions and answers
1. **"Why not a supplier rating tool?"** They say which supplier is risky; we say which operations are contaminated and we isolate them. They're complementary: the compromise declaration can come from one of these tools.
2. **"Resilinc or Interos already do this."** They link an event to parts and open orders and send alerts. To our knowledge, they mostly target disruptions, and alert rather than isolate. Our case: false data injected, automatic and selective quarantine, signed alerts between partners. We haven't tested their products.
3. **"What if your graph is incomplete?"** That's our main limitation and we quantify it: with 30% of dependencies invisible, recall drops to 93.4% and 28.4% of worlds let an irreversible action through. Levers: extracting dependencies from documents, missing-provenance rule (option D).
4. **"Who is responsible if you block wrongly?"** The decision comes from deterministic rules, with the path in the graph: it can be challenged and replayed. Release remains a human approval; the AI never decides.
5. **"Where's the AI?"** It reads messy documents, explains the impact and proposes a recovery plan. It neither isolates nor releases. (Don't announce any measurement of the AI's effect until the extractor has been evaluated on test documents.)
6. **"How do you know a partner is compromised?"** We don't detect it: the declaration comes from a known incident, a rating tool or a partner. Our contribution is what happens next.
7. **"Can a false alert freeze my business?"** An alert only carries tokens for the sender's data: it can only quarantine what depends on that data, and a human can lift it. Signatures are verified; keys are neither written in the code nor guessable. On Avalanche, the contract only accepts federation members: an outside company can't declare a fake incident.
8. **"Why a blockchain?"** Our audit log is hash-chained, but whoever holds it can rewrite it by recomputing every hash. So we anchor on a consortium Avalanche L1 the fingerprints of logs, alerts, acknowledgments and incident declarations: you can prove after the fact who was warned, and when (disputes, insurance, NIS2), without depending on whoever holds the log. In the demo, honestly: a single validator (hosted by Avalanche's Builder Hub) and a single contract admin account, held by the team; in production, the validators are the consortium members. No commercial data on the chain, only fingerprints. The chain decides nothing and blocks nothing: if it goes down, Firebreak keeps going and anchoring catches up afterwards. Details: `docs/avalanche/pitch.md`.
   - **"What about TradeLens?"** TradeLens (Maersk × IBM, shutdown announced end of 2022, closed early 2023) asked the whole industry to hand its data to a platform controlled by a single player. We do the opposite: data stays at each company, only proofs go on the chain, and in production the consortium members validate it (in the demo, a single validator).
   - **"Why not a shared database?"** Whoever controls the database can rewrite it: the proof is only worth something if it's out of everyone's reach.
9. **"Who would pay?"** Hypothesis to test: industrial SMEs under pressure from their prime contractors (NIS2), and vendors who would integrate it. We don't have a validated customer.
10. **"Are your figures real?"** No: they come from our simulator, which is reproducible (`scripts/bench.py`, 500 worlds). They describe our model, not a real company.

## Never say
- "Nobody has done it" · "in a real company" · "NIS2 compliant" (say "helps demonstrate") · "perfect detection" · any figure that isn't in `docs/bench-results.md` or on screen.
- "The blockchain blocks" or "detects the attack" (it proves, it decides nothing) · "our data is on the blockchain" (only fingerprints) · "on our L1" if the demo runs in `tester` mode · "finality in under a second" (measured on our L1: about 2 s per proof, receipt included; 12 anchors in about 24 s, two demos in a row without failure) · "no single player holds the chain" or "known validators" as long as the L1 has only one validator. These times are "measured on our demo", not bench figures.
