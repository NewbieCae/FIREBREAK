# FIREBREAK — The supply chain firewall

**Track 3 · Uncharted Frontiers** — Cyber defense × AI × Industry

> When a partner is compromised, isolate what's contaminated, not the whole business.

## In one sentence

Firebreak stops a compromise at one company from spreading to its customers, suppliers and partners, by quarantining **only the contaminated operations** and letting everything else run.

## The problem

Companies in the same supply chain exchange data continuously: orders, stock levels, delivery confirmations, catalog updates. If one of them is compromised, it can inject false information into its partners' processes.

Fictional example: four interconnected companies. A hacked supplier sends fake delivery confirmations and falsified stock levels. This data feeds orders, payments and shipments at its partners, who treat it as reliable.

Faced with this, partners today have only two options: cut everything off with the supplier and paralyze the business, or keep going and let the attack through.

## What exists, and what's missing

Supplier risk management already exists. [SecurityScorecard](https://securityscorecard.com), for example, offers supply chain monitoring and incident response.

These tools answer the question **"which supplier is dangerous?"**. Firebreak answers a finer question: **"which specific operations were contaminated by this supplier's data?"**.

> If an attack hits 3 orders out of 100, why block all 100?

## How it works

1. **Traceability.** Each company installs a lightweight component that records the provenance of business events: which source each piece of data comes from, and which operations used it.
2. **Dependency graph.** These records form a graph linking each operation to the data it depends on.
3. **Compromise declaration.** When a source is declared compromised, Firebreak walks the graph starting from that source.
4. **Targeted containment.** Firebreak:
   - identifies the operations that depend, directly or indirectly, on the suspect data;
   - quarantines those operations;
   - lets independent operations through; they remain authorized.
5. **Partner alerts.** Firebreak sends signed alerts to the affected partners, without disclosing their commercial data.
6. **Remediation.** The AI prepares a recovery plan for each quarantined operation: revalidation, human approval or recovery from a trusted source.

## Key principle: rules that decide, an AI that explains

- **The technical core is a dependency graph**, not a chatbot assigning risk scores.
- **The blocking decision relies on verifiable rules**: an operation is quarantined because it depends on a compromised source, and the exact path in the graph can be shown.
- **The blockchain proves**: fingerprints of alerts, acknowledgments, declarations and audit logs are anchored on an Avalanche L1. This makes it possible to prove who warned whom, and when, and that no log was rewritten after the fact. No commercial data is written there, and the chain decides nothing.
- **The AI plays a supporting role**: it interprets documents (purchase orders, shipping notices, supplier emails), explains the impact of the incident and proposes recovery actions.

Result: containment that is auditable, explainable, and preserves business continuity.
