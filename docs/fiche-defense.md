# Defense sheet — FIREBREAK (Team 14, Track 3)

> Figures from test bench v2 (`scripts/bench.py`, 500 worlds × 4 values of p), **regenerated on 11/10**: the v1 figures (49.5 / 11.4…) are obsolete. **Check before submission**: `uv run python scripts/bench.py`, then compare with `docs/bench-results.md`.

## Threat addressed
A partner in a supply chain is compromised and injects false data (delivery confirmations, stock levels, bank details) into the processes of its customers and suppliers. Today partners have only two options: cut everything off with it, or keep going and let the contamination through.

## What FIREBREAK does
- Each company records the provenance of its operations (what depends on what) in a dependency graph.
- When a source is declared compromised since a given point in time, the engine walks the graph, quarantines **only** the operations that depend on it, and lets the others through. Each quarantine shows the exact path in the graph.
- Affected partners receive **signed (Ed25519)** alerts that contain only opaque tokens, never commercial data. A forged alert is rejected.
- Every decision is written to a hash-chained audit log; a release goes through remediation (revalidation, human approval or trusted source).
- **Rules decide, AI assists**: it reads documents, explains the impact and proposes a recovery plan. It never isolates or releases anything on its own.

## NIST CSF 2.0 functions covered
| Function | What the project brings |
|---|---|
| Identify | Provenance and dependency graph between operations and companies |
| Detect | Receipt of a compromise declaration or a signed alert from a partner (detecting the compromise itself is not our contribution) |
| Respond | Selective quarantine, signed alerts to partners, recovery plan |
| Recover | Signed release, remediation, resumption of independent operations |
| Govern | Chained audit log, explainable decision path |

## Frameworks (check identifiers on attack.mitre.org before submission)
- MITRE ATT&CK: Supply Chain Compromise (T1195), Trusted Relationship (T1199), Data Manipulation (T1565).
- Regulation cited as context, without claiming compliance: NIS2 (supply chain security, incident handling). The audit log *helps demonstrate* decisions.

## Metrics (simulator, 500 random worlds, 4 levels of unrecorded dependencies)
Four policies compared on the same world: A alert only, B blocking the supplier and its direct partners, C FIREBREAK, D FIREBREAK + caution (C, plus quarantining receipts with no recorded provenance at direct partners). The compromised company is drawn among the 5, end customer included; 10% of receipts come from outside the federation (legitimate, no token).

| | A | B | C (FIREBREAK) | D (+ caution) |
|---|---|---|---|---|
| Healthy wrongly blocked (p=0) | 0 | 43.2 | 9.6 | 11.7 |
| Healthy activity preserved (p=0) | 100% | 83.8% | 96.4% | 95.6% |
| Precision (p=0) | n/a | 44% | 78% | 75% |
| Contaminated irreversible actions that get through (p=0, per world) | 11.1 | 0.07 | 0 | 0 |
| Worlds with at least one leak (p=0) | 100% | 24.6% | 0% | 0% |
| Recall at p = 0 / 0.1 / 0.2 / 0.3 | 0% | 98.5% (regardless of p) | 100 / 98.0 / 95.7 / 93.4% | 100 / 99.4 / 98.6 / 97.9% |
| Recall at p = 0.3: 5th percentile / worst case | — | 91.2 / 72.9% | 79.2 / 66.0% | 90.0 / 78.6% |

Detection time: not measured (the trigger is a declaration or a received alert; we don't detect).
Response time, measured on our demo (`mixed` scenario, not a bench figure): quarantine of the 17 operations in about 20 ms via the HTTP API (2 ms median without network, chain off, 20 runs); anchoring of each proof on our Avalanche L1 in about 2 s, in the background, without delaying the quarantine (12 anchors in about 24 s, 0 failures over two demos).

## Known limitations (say them before the jury finds them)
- Everything is simulated; the figures come from our model, not from a real company.
- FIREBREAK only sees recorded dependencies: when 10 to 30% are missing, its average recall drops below that of broad blocking (B), for 4.5 to 5.4 times less collateral damage. With 30% of dependencies missing, 28% of worlds let at least one contaminated irreversible action through. It's a trade-off, not a crushing win.
- At p=0, FIREBREAK still blocks healthy operations, and all of them come from the origin rule: any data attributed to the compromised source after the declared date is blocked, even if it copies earlier or verified data.
- Policy D exploits the "missing provenance" signal (receipt with no token or link). The simulator assumes an untracked shipment always leaves an unattributed receipt: its figures are an upper bound.
- The trigger is a declaration or a received alert; we don't detect the compromise.
- No validated customer to date.

## Who is responsible if the system gets it wrong
The blocking decision comes from deterministic, traceable rules (path in the graph): it can be challenged and replayed. Releasing a quarantine remains a human approval; the AI never decides.
