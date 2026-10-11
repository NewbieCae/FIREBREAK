# FIREBREAK — Defense sheet

**Secure Horizons hackathon · Team 14 · Track 3 "Uncharted Frontiers"** — the supply chain firewall.

## 1. The threat
Companies in a supply chain feed each other's processes with data: orders, stock levels, delivery notices, bank details, certificates. When one partner is compromised, or ships a defective lot, the bad data spreads to its customers and suppliers, which trust it, and ends in payments, shipments and production runs that can't be undone. Partners today have two options: cut the supplier off and stop their own business, or keep going and let the contamination through. *(MITRE ATT&CK: Supply Chain Compromise T1195, Trusted Relationship T1199, Transmitted Data Manipulation T1565.002.)*

## 2. How FIREBREAK works
1. **Provenance.** Each company records where each piece of data comes from and which operations use it. Together these records form a dependency graph.
2. **Selective quarantine.** When a source is declared compromised from a given time, a deterministic engine walks the graph and quarantines **only** the operations that depend on that source, directly or indirectly. Everything else keeps running. Each quarantine shows the exact path in the graph that triggered it.
3. **Signed alerts to partners.** Affected partners get Ed25519-signed alerts carrying only opaque tokens, never commercial data. A forged or altered alert is rejected.
4. **Recovery.** A quarantine is lifted only through remediation (revalidation, a trusted source, or human approval). Every decision is written to a hash-chained audit log.
5. **Tamper-evident proof.** Fingerprints of alerts, acknowledgements, declarations and logs are anchored on a dedicated Avalanche L1. No business data goes on-chain, and the chain decides nothing.
6. **AI assists, rules decide.** AWS Bedrock (Claude, Converse API) reads documents (purchase orders, shipping notices, emails), explains the impact in plain language and drafts a recovery plan. It never quarantines or releases anything. If Bedrock fails or times out (8 s by default), deterministic templates take over.
7. **Quality incidents too.** The same graph isolates one defective lot instead of the whole supplier, and a signed quality report can travel upstream from customer to supplier. The recipient always decides.

## 3. What we tested, and the results
**Test bench** (`scripts/bench.py`): 500 random synthetic worlds per setting, 5 companies, ~300 operations each. Any company can be the compromised one, and 10% of receipts come from outside the federation. *p* is the share of real dependencies that are **not recorded**. Policies compared on the same worlds: B = block the supplier and its direct partners (today's practice), C = FIREBREAK.

| Metric (mean per world) | B — block partners | C — FIREBREAK |
|---|---|---|
| Healthy operations wrongly blocked (p = 0) | 43.2 | **9.6** (4.5× fewer) |
| Healthy activity preserved (p = 0) | 83.8% | **96.4%** |
| Precision (p = 0) | 44% | **78%** |
| Recall (p = 0 / 0.1 / 0.3) | 98.5% (fixed) | **100%** / 98.0% / 93.4% |
| Irreversible actions leaked (p = 0) | 0.07 | **0** |

Alert-only lets every contaminated operation through (11.1 irreversible actions per world). Full tables, confidence intervals and per-company breakdowns are in `docs/bench-results.md`.

**Running system:** 327 automated tests pass (engine, signatures, audit chain, API, chain client, document reading). On the demo scenario, the quarantine of 17 operations takes about 20 ms through the HTTP API. Anchoring on our Avalanche L1 runs in the background (2 to 4 s per proof); the quarantine never waits for it. In the quality-recall scenario, 25 of 25 proofs were confirmed. In a tamper test, we rewrote a company's log and recomputed its hashes: the local check still said "intact", the on-chain check flagged the mismatch.

## 4. Known limitations
- **Simulated data only.** The figures come from our generator, not from a real company. We have no validated customer yet.
- **FIREBREAK only sees what is recorded.** With 10–30% of dependencies missing, its recall falls below broad blocking (93.4% vs 98.5% at p = 0.3, worst world 66%), and 28% of worlds let at least one contaminated irreversible action through. It trades a little recall for 4.5–5.4× less collateral damage; it doesn't beat broad blocking on every metric.
- **Cautious origin rule.** All 9.6 healthy operations blocked at p = 0 come from one rule: any data from the compromised source after the declared time is quarantined, even if it repeats earlier or verified data.
- **No detection.** The trigger is a compromise declaration or a received alert. Spotting the intrusion itself is out of scope.
- **Demo infrastructure.** Our L1 has a single validator and the team is the contract admin: a demonstrator, not independent trust. In production, the consortium members would be the validators. The demo uses the template fallback by default; automated tests check Bedrock against a fake client, not a live account.

## 5. Accountability
The blocking decision comes from deterministic rules with a visible graph path, so it can be challenged and replayed. Releasing a quarantine stays a human decision; the AI never decides. The audit log and on-chain anchors help *demonstrate* who warned whom and when, which supports NIS2 supply-chain and incident-handling duties (Art. 21, Art. 23). We do not claim compliance.
