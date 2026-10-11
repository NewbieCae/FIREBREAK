# FIREBREAK — Competitor benchmark

> What the market does, what's missing, and what sets us apart.
> Sources: the vendors' official websites, consulted on October 10, 2026. No product tested hands-on.

## In short

The market can tell **which supplier is dangerous**, or **which machine to isolate** in-house.
Nobody says **which specific business operations** (orders, deliveries, payments) were contaminated by a compromised partner's data, or quarantines them without blocking everything else.

## The competitors

### 1. Supplier cyber ratings (TPRM)

| Vendor | What they offer |
|---|---|
| [SecurityScorecard](https://securityscorecard.com) | Outside-in supplier security ratings, continuous monitoring, questionnaires, AI agents (TITAN AI), managed supply chain incident response service (MAX). |
| [Bitsight](https://www.bitsight.com) | Security ratings, continuous third-party monitoring, supply chain exposure (Beacon), dark web intelligence. |
| [UpGuard](https://www.upguard.com) | Supplier risk, attack surface, AI-automated questionnaires. |
| [Black Kite](https://blackkite.com) | Third-party cyber risk, financial risk quantification (Open FAIR), ransomware likelihood. |
| [RiskRecon (Mastercard)](https://www.riskrecon.com) | Cyber ratings, assessments, remediation tracking with suppliers. |
| [Panorays](https://www.panorays.com), [Mitratech Prevalent](https://mitratech.com/products/prevalent/) | Supplier assessment, questionnaires, compliance. |

**Limit:** they reason at the level of **the whole supplier**. They see the company from the outside, not the orders it touched at your end. Their typical answer: "monitor" or "cut off".

### 2. Physical supply chain risk

| Vendor | What they offer |
|---|---|
| [Interos](https://www.interos.ai) | Multi-tier supplier mapping, alerts (cyber, sanctions, tariffs, reputation). |
| [Everstream](https://www.everstream.ai) | Network digital twin, AI alerts, visibility into subcontractors. |
| [Resilinc](https://www.resilinc.com) | Monitoring of supplier disruptions (disasters, shortages, sites). |

**Limit:** they detect that a supplier or a site is **affected**, not that **its data** has corrupted your operations.

### 3. Breach containment (network)

| Vendor | What they offer |
|---|---|
| [Illumio](https://www.illumio.com) | Microsegmentation: isolates machines and network flows to stop an attack from spreading. |
| EDR / XDR (CrowdStrike, SentinelOne…) | Isolation of compromised endpoints and servers. |

**Limit:** containment happens **within a single company**, at the **network and machine** level. A fake delivery confirmation comes through a legitimate channel: the network doesn't see it.

### 4. Data and artifact traceability

| Vendor | What they offer |
|---|---|
| [OpenLineage](https://openlineage.io) | Open source lineage standard: where each dataset comes from, impact analysis. |
| [SLSA](https://slsa.dev), Sigstore, Snyk… | Provenance and integrity of **code** and software packages. |
| TradeLens (Maersk × IBM) | Shared blockchain ledger for maritime shipping. Shut down in early 2023 for lack of ecosystem adoption. |

**Limit:** lineage stays **internal** and **passive** (it explains, it doesn't block). SLSA protects code, not business flows. TradeLens shows that a common ledger imposed on a whole industry is hard to get adopted.

### 5. Threat sharing

| Vendor | What they offer |
|---|---|
| [MISP](https://www.misp-project.org), sector ISACs | Sharing of technical indicators between organizations (IPs, malware, campaigns). |

**Limit:** what's shared is **technical indicators**, not "this operation at your end depends on suspicious data".

## Summary table

| | Supplier ratings | Physical supply chain | Network containment | Lineage / provenance | Threat sharing | **Firebreak** |
|---|---|---|---|---|---|---|
| Level of analysis | Supplier | Supplier / site | Machine / flow | Dataset / code | Indicator | **Business operation** |
| Across companies | Yes | Yes | No | No | Yes | **Yes** |
| Blocks something | No | No | Yes | No | No | **Yes, targeted** |
| Lets healthy traffic through | — | — | Partially | — | — | **Yes** |
| Explainable decision | Rating | Score | Network rules | Graph | — | **Path in the graph** |

## Recommendation

**Our line:**

> Others tell you which supplier is dangerous. Firebreak tells you which orders are affected, quarantines them, and keeps everything else running.

**What sets us apart, in three points:**

1. **Granularity: the operation, not the supplier.** 3 orders affected out of 100, we block 3, not 100. It's our one promise, and we have to prove it in the demo.
2. **A provable decision.** The block comes from a path in the dependency graph that can be shown to an auditor. The AI explains and prepares recovery; it doesn't decide.
3. **Alerts between partners without data leakage.** Each company keeps its data; only signed alerts are exchanged. No common data ledger to impose (the TradeLens lesson): the Avalanche L1 only receives fingerprints, to prove who warned whom and that the logs have not been rewritten.

**Don't:** compete on supplier ratings (saturated market) or present a risk-score chatbot.

**Recommended positioning:** **complement**, not competitor. SecurityScorecard or Bitsight raise the "this supplier is compromised" alert; Firebreak takes over and sorts things out operation by operation.
