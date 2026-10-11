# FIREBREAK — API contract

Contract version: **1.4.0** (frozen at 1.0.0 in step 1 of the [plan](plan.md); step 2 added federated releases, declaration withdrawal and the audit log; step 3 added scenarios, lot genealogy and EPCIS import, without removing anything; 1.3.0 adds `truth.ids` to `/api/compare` and serves the final UI at `/app/` and sample documents at `/samples/`; 1.4.0 (Avalanche part) adds `/api/chain/*`, the optional `onchain` field of `/api/audit/verify` and `/api/demo/rewrite`). Later steps may **add** fields or endpoints, but never remove or rename them without updating this document.

- Base: `http://localhost:8000`. All endpoints live under `/api`.
- Interactive OpenAPI schema: http://localhost:8000/docs (raw JSON: `/openapi.json`). Response models are defined in `src/firebreak/schemas.py`.
- CORS open for development: `http://localhost:5173`, `http://localhost:3000` (and their `127.0.0.1` equivalents).
- State is in memory and shared by all clients: a `POST /api/reset` resets everything for everyone.

The examples below are real server responses, truncated (`…`).

## Vocabulary

| Term | Meaning |
|---|---|
| **record** | A business operation in a company's ledger: order, advance shipping notice (`asn`), certificate, invoice, payment, production lot, shipment… |
| **seed** | A directly suspect record: issued by a source declared compromised after the `since` time, or received from a partner that flagged it in a valid signed alert. |
| **contamination** | A record is contaminated as soon as one of its `inputs` is. The engine follows these dependencies step by step. |
| **alert** | A signed (Ed25519) message from one company to a partner. It contains only opaque tokens: no label, no amount, no payload. Two types: `taint` (this data is contaminated) and `release` (it no longer is). The type is part of what is signed. |
| **release** | Exit from quarantine. When a record already flagged to a partner becomes clean again (remediation, declaration withdrawal), the sender sends a signed `release` alert; the partner verifies it, removes the tokens, recomputes and releases downstream in turn. A `release` with an invalid signature is rejected: downstream stays blocked. |
| **audit log** | A per-company, append-only, hash-chained list of events. See [`GET /api/audit`](#get-apiaudit). |

### Record statuses (`status`)

| Value | Meaning |
|---|---|
| `ok` | Depends on no suspect data: the operation proceeds. |
| `quarantined` | Depends on suspect data: the operation is blocked. `taint_path` gives the proof. |
| `released` | Unblocked by a remediation (`POST …/remediate`). Will never be contaminated again and **stops propagation**: its descendants go back to `ok` if they depended only on it. |

### Key record fields

| Field | Meaning |
|---|---|
| `gate` | `true` = irreversible action (payment, shipment, production start). A quarantined gate is counted in `gates_blocked`. |
| `verified` | `true` = confirmed by a trusted source (e.g. physical inspection on receipt). Never contaminated, stops propagation. |
| `origin` | Company that issued the data. Differs from `company` for a record received from a partner. |
| `token` | Opaque token (sha256 hex, 64 characters) of a record received from a partner; `null` for an internal record. |
| `inputs` | Records **in the same ledger** this one depends on. Cross-company links are in `edges` with `cross: true`. |
| `taint_path` | Shortest path from the seed to this record, within the company's ledger (`null` if not contaminated). A record received contaminated via an alert starts its own path. |
| `ts` | ISO 8601 timestamp without time zone, Paris time. |

### Counters (`counters`)

`counters.global` (all companies) and `counters.per_company.<id>` have the same shape:

| Field | Meaning |
|---|---|
| `total` | Number of records. |
| `quarantined` | Blocked records. |
| `ok` | Records proceeding normally (`total - quarantined - released`). |
| `released` | Records unblocked by remediation. |
| `gates_blocked` | Blocked irreversible actions. |
| `amount_blocked` | Amount of blocked **payments** (€): sum of `payload.amount` over quarantined `kind == "payment"` records. |
| `amount_flowing` | Amount of **payments that proceed** (€): `kind == "payment"` records in `ok` + `released`. |

"Operations that proceed" on screen = `ok + released`. Only `kind == "payment"` records count toward the `amount_*` totals — an invoice and its received copy carry the same amount, so counting them would count the same euros several times; the payment is the operation where money actually moves.

## Errors

All errors have the same shape: `{"detail": "<message in English>"}` (a string, never a list).

| Code | When | Example |
|---|---|---|
| 400 | Action refused | `{"detail": "invalid action: hack"}`, `{"detail": "record not quarantined"}` |
| 404 | Unknown company, record or route | `{"detail": "unknown record: nope"}`, `{"detail": "Not Found"}` |
| 422 | Invalid request body | `{"detail": "invalid request — since: Field required"}` |

## Endpoints

| Method | Path | Response |
|---|---|---|
| GET | `/api/state` | Full state |
| POST | `/api/compromise` | Full state after propagation |
| POST | `/api/compromise/withdraw` | Full state after cascading releases |
| GET | `/api/records/{id}/explain` | Explanation and recovery plan |
| POST | `/api/records/{id}/remediate` | Full state after recomputation |
| POST | `/api/reset` | Initial state of the chosen scenario (also clears pending documents) |
| GET | `/api/scenarios` | List of scenarios |
| POST | `/api/ingest/epcis?company=<id>` | Records imported from a GS1 EPCIS 2.0 document + full state |
| GET | `/api/audit?company=<id>` | A company's audit log |
| GET | `/api/audit/verify` | Hash chain verification |
| POST | `/api/ingest/document?company=<id>` | Record proposal read from a document |
| POST | `/api/ingest/document/{proposal_id}/confirm` | Full state after the record is added |

### `GET /api/state`

Full state: companies, records, edges, counters, alerts, declarations.

```bash
curl localhost:8000/api/state
```

```json
{
  "companies": [
    {"id": "fournisseur", "name": "Aciers Durand", "role": "Steel supplier", "gs1_prefix": "3012345"},
    …
  ],
  "records": [
    {"id": "f-asn-01", "company": "fournisseur", "origin": "fournisseur", "kind": "asn",
     "ts": "2026-10-10T08:30:00", "label": "ASN order BC-1001", "inputs": [],
     "gate": false, "verified": false, "payload": {"bc": "BC-1001", …}, "token": null,
     "status": "ok", "taint_path": null},
    …
  ],
  "edges": [
    {"source": "m-asn-01", "target": "m-gr-01", "cross": false},
    {"source": "f-asn-01", "target": "m-asn-01", "cross": true},
    …
  ],
  "counters": {
    "global": {"total": 193, "quarantined": 0, "ok": 193, "released": 0, "gates_blocked": 0},
    "per_company": {"fournisseur": {"total": 28, …}, …}
  },
  "alerts": [],
  "declarations": [],
  "scenario": {
    "id": "mixed", "label": "Mixed attack",
    "description": "The compromised supplier sends a fake shipping notice, …",
    "compromise": {"company": "fournisseur", "since": "2026-10-10T14:00:00"},
    "incident": null
  }
}
```

- `edges`: `cross: false` = dependency within one ledger (`input → record`); `cross: true` = a record sent from one company to another (outgoing record → received copy).
- `alerts[]`: `{"type", "from", "to", "tokens_count", "verified", "issued_at"}`, in order of issue. `type` = `"taint"` (contamination) or `"release"`. `verified` = signature accepted by the recipient (`false` = forged alert, rejected).
- `declarations[]`: `{"ledger", "source", "since"}` — ledger `ledger` considers `source` compromised since `since`.
- `scenario`: scenario loaded by the last `POST /api/reset` (see [Scenarios](#scenarios)). `compromise` gives the declaration to send to `POST /api/compromise` for the demo.
- `companies[].gs1_prefix`: GS1 company prefix, used by the EPCIS import to recognize the owner of a location (SGLN / GLN).
- Lots: a record representing a lot carries `payload.lot`; a production start (`kind: "production_lot"`) also carries `payload.input_lots`, the lots consumed (like an EPCIS TransformationEvent). Its `inputs` are the records of those lots: a lot made with a contaminated lot is contaminated.

### `POST /api/compromise`

Declares a company compromised since a given time. The company and its direct partners record the declaration; the rest of the chain is notified by signed alerts, hop by hop, until it stabilizes.

Several companies can be declared. Re-declaring the same company with a different time keeps **the earliest** (a later time is logged but has no effect).

Body: `{"company": "<id>", "since": "<ISO 8601 date>"}`. A date without time zone is read as Paris time; a date with a time zone (e.g. `2026-10-10T12:00:00Z`, which is what `new Date().toISOString()` returns) is converted.

```bash
curl -X POST localhost:8000/api/compromise \
  -H 'Content-Type: application/json' \
  -d '{"company": "fournisseur", "since": "2026-10-10T14:00:00"}'
```

```json
{
  "counters": {
    "global": {"total": 193, "quarantined": 17, "ok": 176, "released": 0, "gates_blocked": 4},
    "per_company": {
      "fournisseur":  {"total": 28, "quarantined": 4, "ok": 24, "released": 0, "gates_blocked": 0},
      "fabricant":    {"total": 103, "quarantined": 8, "ok": 95, "released": 0, "gates_blocked": 3},
      "distributeur": {"total": 36, "quarantined": 3, "ok": 33, "released": 0, "gates_blocked": 1},
      "client":       {"total": 26, "quarantined": 2, "ok": 24, "released": 0, "gates_blocked": 0}
    }
  },
  "alerts": [
    {"type": "taint", "from": "fabricant", "to": "distributeur", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"type": "taint", "from": "fournisseur", "to": "fabricant", "tokens_count": 4, "verified": true, "issued_at": "2026-10-10T15:00:00"},
    {"type": "taint", "from": "distributeur", "to": "client", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:01:00"}
  ],
  "declarations": [
    {"ledger": "fournisseur", "source": "fournisseur", "since": "2026-10-10T14:00:00"},
    {"ledger": "fabricant", "source": "fournisseur", "since": "2026-10-10T14:00:00"}
  ],
  "records": [
    …,
    {"id": "m-pay-X", "company": "fabricant", "origin": "fabricant", "kind": "payment",
     "ts": "2026-10-10T15:10:00", "label": "Invoice payment F-9999 (modified RIB)",
     "inputs": ["m-inv-X"], "gate": true, "verified": false,
     "payload": {"amount": 5210, "rib": "FR76 1234 5678 9000 0000 0000 666"},
     "token": null, "status": "quarantined", "taint_path": ["m-inv-X", "m-pay-X"]},
    …
  ],
  …
}
```

Errors: 404 if the company is unknown, 422 if `company` or `since` is missing or malformed.

### `GET /api/records/{id}/explain`

Explanation (in English) and recovery plan for a record, whatever its status. The explanation is produced by the AI (Bedrock or a deterministic template, see [AI](#ai-bedrock-and-mock-fallback)); it never decides on blocking.

```bash
curl localhost:8000/api/records/m-pay-X/explain
```

```json
{
  "record": {"id": "m-pay-X", "status": "quarantined", "taint_path": ["m-inv-X", "m-pay-X"], …},
  "path": [
    {"id": "m-inv-X", "company": "fabricant", "origin": "fournisseur", "kind": "invoice",
     "label": "Invoice received F-9999", "token": "edccd2dc…42a7e", "status": "quarantined", …},
    {"id": "m-pay-X", …}
  ],
  "explanation": "\"Invoice payment F-9999 (modified RIB)\" is quarantined: it depends, directly or indirectly, on \"Invoice received F-9999\" (fournisseur, 14:19), issued within the declared compromise window. Contamination path: \"Invoice received F-9999\" → \"Invoice payment F-9999 (modified RIB)\". Impact: a payment is blocked (5210 €). Suspicious bank details (RIB changed).",
  "remediation_plan": [
    {"action": "revalidate", "label": "Revalidate the data",
     "rationale": "Compare the received document with the original source (purchase order, certificate) to confirm it is authentic."},
    {"action": "human_approval", "label": "Human approval", "rationale": "…"},
    {"action": "trusted_source", "label": "Restart from a trusted source", "rationale": "…"}
  ],
  "source": "mock"
}
```

- `source`: `"bedrock"` if the response comes from Bedrock, `"mock"` otherwise (default mode, or fallback after a Bedrock error).
- `path`: the records of `taint_path`, in order, in the same format as `records` (empty if the record is not contaminated).
- `remediation_plan[].action`: one of the three actions accepted by `/remediate`.

Error: 404 if the record is unknown.

### `POST /api/records/{id}/remediate`

Unblocks a quarantined record: it becomes `released`, then everything is recomputed. Its descendants that depended only on it go back to `ok`, including at partners: signed `release` alerts travel hop by hop down to the client. The remediation is logged with `actor: "humain"`.

Body: `{"action": "revalidate" | "human_approval" | "trusted_source"}`.

```bash
curl -X POST localhost:8000/api/records/m-gr-X/remediate \
  -H 'Content-Type: application/json' -d '{"action": "human_approval"}'
```

Response: the full state, like `/api/state`. After compromise then remediation of `m-gr-X`:

```json
{
  "counters": {"global": {"total": 193, "quarantined": 9, "ok": 183, "released": 1, "gates_blocked": 1}, …},
  "alerts": [
    …the 3 taint alerts…,
    {"type": "release", "from": "fabricant", "to": "distributeur", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:02:00"},
    {"type": "release", "from": "distributeur", "to": "client", "tokens_count": 1, "verified": true, "issued_at": "2026-10-10T15:03:00"}
  ],
  …
}
```

`m-lot-X`, `m-ship-X`, `d-ship-X`, `d-gr-X`, `d-out-X`, `c-ship-X` and `c-gr-X` go back to `ok`. The payment to the fraudulent bank account (`m-pay-X`) stays blocked: it does not depend on `m-gr-X`.

Errors: 404 if the record is unknown; 400 if the action is invalid or the record is not quarantined.

### `POST /api/compromise/withdraw`

Withdraws a company's declaration (false alarm) everywhere it is recorded, then recomputes. Records that are no longer suspect leave quarantine and `release` alerts go downstream. Other declarations stay active. An already remediated record stays `released`.

Body: `{"company": "<id>"}`.

```bash
curl -X POST localhost:8000/api/compromise/withdraw \
  -H 'Content-Type: application/json' -d '{"company": "fournisseur"}'
```

Response: the full state. After compromise then withdrawal: `quarantined: 0`, `declarations: []`, and 3 verified `release` alerts are added to the 3 `taint` alerts.

Errors: 404 if the company is unknown; 400 `{"detail": "no active declaration for fournisseur"}`; 422 if `company` is missing.

### `POST /api/reset`

Rebuilds a scenario (no declarations, no alerts, empty audit logs, all records `ok`). Optional body:

```bash
curl -X POST localhost:8000/api/reset -H 'Content-Type: application/json' -d '{"scenario": "cert"}'
```

Without a body: `mixed` (193 records). Response: the full state, with `scenario`. An unknown id returns 422 `{"detail": "invalid request — scenario: Input should be 'mixed', 'rib', 'cert', 'asn', 'lot' or 'recall'"}`.

### `GET /api/scenarios`

```json
[
  {"id": "mixed", "label": "Mixed attack", "description": "…",
   "compromise": {"company": "fournisseur", "since": "2026-10-10T14:00:00"}, "incident": null},
  {"id": "rib", "label": "RIB fraud", …},
  {"id": "cert", "label": "Fake quality certificate", …},
  {"id": "asn", "label": "Fake shipping notice", …},
  {"id": "lot", "label": "Defective lot", …, "incident": {"type": "lot", "company": "fabricant", "lot": "COIL-104", "reason": "…"}},
  {"id": "recall", "label": "Recall from a finished product", …, "incident": {"type": "recall", "company": "fabricant", "target": "LOT-503", "suspect_lot": "COIL-103", "reason": "…"}}
]
```

### `GET /api/audit`

A company's append-only audit log (`company` parameter required). Each entry:

| Field | Meaning |
|---|---|
| `index` | Position in the log, starting at 0. |
| `ts` | **Scenario** time (simulated clock that starts at 15:00 and advances one minute per alert round), not real time. |
| `company` | Company that owns the log. |
| `event` | See the table below. |
| `actor` | `"humain"` (declaration, withdrawal, remediation, document confirmation) or `"règle"` (anything the engine decides on its own). |
| `details` | Event-specific content. |
| `prev_hash` | `hash` of the previous entry (64 zeros for the first). |
| `hash` | `sha256(prev_hash + canonical JSON of the entry without "hash")`, sorted JSON, no whitespace, UTF-8. |

| `event` | `details` |
|---|---|
| `declaration` | `source`, requested `since`, `effective_since` (the earliest kept) |
| `declaration_withdrawn` | `source`, withdrawn `since` |
| `alert_sent` | `type`, `from`, `to`, `tokens`, `issued_at`, `signature` |
| `alert_received` | same + `verified` (bool) and `outcome` (`"applied"` or `"rejected: invalid signature"`) |
| `quarantine` | `record`, `rule`, `taint_path`, `gate`. `rule`: `source_compromise` (issued by a declared source, after `since`), `alerte_verifiee` (token flagged by a partner), `dependance` (depends on a contaminated record) |
| `remediation` | `record`, `action`, `taint_path` at remediation time |
| `release` | `record`, `reason`: quarantine exit decided by the engine (after upstream remediation, received release or withdrawal) |
| `document_confirmed` | `record`, `proposal`, `origin`, `kind`, `inputs`, `extraction_source` (`mock` or `bedrock`), `confidence`: document read then confirmed (`POST /api/ingest/document/{id}/confirm`) |
| `epcis_import` | `records` (ids added), `events` (events in the document), `ignored` (number ignored): EPCIS import (`POST /api/ingest/epcis`) |

A company's log contains only its own records and opaque tokens: never a partner's identifiers or data.

```bash
curl 'localhost:8000/api/audit?company=distributeur'
```

```json
{
  "company": "distributeur",
  "head": "d70487f0…6e466",
  "entries": [
    {"index": 0, "ts": "2026-10-10T15:01:00", "company": "distributeur", "event": "alert_received", "actor": "règle",
     "details": {"type": "taint", "from": "fabricant", "to": "distributeur", "tokens": ["bddf56ee…17dd"],
                 "issued_at": "2026-10-10T15:00:00", "signature": "10d47c40…3c0d", "verified": true, "outcome": "applied"},
     "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000", "hash": "d66c9dc9…b519"},
    {"index": 1, "ts": "2026-10-10T15:01:00", "company": "distributeur", "event": "quarantine", "actor": "règle",
     "details": {"record": "d-ship-X", "rule": "alerte_verifiee", "taint_path": ["d-ship-X"], "gate": false},
     "prev_hash": "d66c9dc9…b519", "hash": "35cae586…7bc8"},
    …
  ]
}
```

Errors: 404 if the company is unknown; 422 if `company` is missing.

### `GET /api/audit/verify`

Recomputes all hash chains (or a single one with `?company=<id>`) and reports whether they are intact.

```json
{
  "ok": false,
  "first_broken": {"company": "distributeur", "index": 2},
  "journals": [
    {"company": "fournisseur", "ok": true, "entries": 6, "first_broken_index": null, "head": "eb3ef24b…b280"},
    {"company": "distributeur", "ok": false, "entries": 10, "first_broken_index": 2, "head": "d70487f0…6e466"},
    …
  ]
}
```

- `ok`: all verified chains are intact. `first_broken`: `null` in that case.
- `first_broken_index`: first entry whose `index`, `prev_hash` or `hash` no longer matches. A modified, deleted or moved entry is detected.
- Limitation: the chain proves no entry was modified **without recomputing all subsequent hashes**. To guard against that case too, `head` must be published elsewhere: that is the role of Avalanche anchoring (section [Avalanche L1](#avalanche-l1-proof-anchoring), `onchain` field), active only if `FIREBREAK_CHAIN` is `tester` or `l1`.

Error: 404 if the company is unknown.

### `GET /api/timeline`

Step-by-step replay of **the last action** (`POST /api/compromise`, `…/compromise/withdraw`, `…/records/{id}/remediate`, or a confirmed ingestion). Steps are read from the chained audit logs: the timeline changes none of the engine's results, it instruments them. Empty (`{"steps": []}`) right after a reset.

```json
{"steps": [
  {"n": 1, "ts": "2026-10-10T15:00:00", "type": "declaration",
   "company": "fournisseur", "record": null, "parent": null, "gate": false,
   "label": null, "rule": null, "alert": null,
   "counters": {"quarantined": 0, "gates_blocked": 0,
                "amount_blocked": 0.0, "amount_flowing": 97312.0},
   "text": "fournisseur declared compromised since 2026-10-10 14:00 (ledger fournisseur)."},
  {"n": 13, "ts": "2026-10-10T15:00:00", "type": "gate_blocked",
   "company": "fabricant", "record": "m-pay-X", "parent": "m-inv-X",
   "gate": true, "label": "Invoice payment F-9999 (modified RIB)",
   "rule": "dependance", "alert": null,
   "counters": {"quarantined": 10, "gates_blocked": 1,
                "amount_blocked": 5210.0, "amount_flowing": 92102.0},
   "text": "Irreversible action blocked: \"Invoice payment F-9999 (modified RIB)\" (5210 €) (fabricant)."}
]}
```

| `type` | Meaning |
|---|---|
| `declaration` | A compromise declaration recorded on this ledger (`company` = ledger, the source is in `text`). |
| `seed` | Record contaminated directly by a rule: `rule` = `source_compromise` (declared origin, `ts` within the window) or `alerte_verifiee` (token from a verified alert). |
| `quarantine` | Record contaminated through a dependency; `parent` = the contaminated record it derives from. |
| `gate_blocked` | Quarantine of a `gate` (irreversible action). |
| `alert_sent` / `alert_received` | Signed alert issued / received and verified. `alert.links` gives the `[sent_record, received_record]` pairs for the tokens — the `cross: true` edges to animate. `alert.verified` = `false` if the signature is rejected. |
| `release` | Record released from quarantine on recomputation (no longer depends on suspect data). |
| `remediation` | Human remediation action (the record becomes `released`). |
| `withdrawal` | Declaration withdrawn (false alarm). |

- `counters` gives the impact **cumulated at this step**: replaying the steps in order reproduces the final state of `/api/state` (including release cascades after remediation or withdrawal).
- `text` is an English sentence ready for display.

### `GET /api/events?speed=<s>`

Streams the same sequence as **Server-Sent Events** (`text/event-stream`): one `data:` event per step (same JSON payload as a `/api/timeline` entry), preceded by a `: firebreak replay` comment; the stream closes at the end of the sequence. `speed` = pause in seconds between events (default `0.5`, `0` for all at once, max `10`).

```js
const es = new EventSource('/api/events?speed=0.8');
es.onmessage = (e) => {
  const step = JSON.parse(e.data);
  console.log(step.n, step.type, step.text);
  // step.counters = {quarantined, gates_blocked, amount_blocked, amount_flowing}
  // amount_* = amount of payments (kind == "payment") blocked / proceeding
  // step.alert.links = [[sent_record, received_record], …] → cross edges to animate
};
// the stream closes on its own at the end of the sequence
```

The final state rebuilt by applying the steps in order is identical to `GET /api/state` (checked by `tests/test_timeline.py`).

### `GET /api/compare`

**With vs without Firebreak**, measured on the current simulation and its active declarations (400 `{"detail": "no active declaration"}` if there are none). Two policies compared against the **same ground truth**:

- **Ground truth**: records actually contaminated — BFS from the records **issued** by the source in its own ledger (`origin == company`) after `since`, along recorded dependencies (`inputs` + cross-company shipments); a `verified` record is never contaminated and stops propagation. Independent of statuses (remediation does not change it).
- **`without` (policy B, "without Firebreak")**: for each declaration, cut off the source and its **direct customers** (those who received its data) — every record in their ledgers with `ts >= since` is blocked. `scope` gives this perimeter per source.
- **`with` (policy C, "with Firebreak")**: the records currently `quarantined`.

Same metrics function on both sides: `blocked`, `healthy_blocked` (blocked outside the truth = collateral), `leaked`/`leaked_ids` (contaminated but not blocked = leaks), `gates_blocked`, `payments_blocked_eur`/`payments_flowing_eur` (payments only), `activity_preserved_pct` (share of healthy operations not blocked), `precision`, `recall` (null when undefined), `companies_hit`, `blocked_ids`.

```json
{"declarations":[{"company":"fournisseur","since":"2026-10-10T14:00:00"}],
 "truth":{"contaminated":17,"ids":["c-gr-X","c-ship-X",…],"definition":"Truly tainted records: …"},
 "without":{"title":"Without Firebreak","policy":"B",
   "subtitle":"Cut off the supplier and its direct customers since 2 pm",
   "scope":{"fournisseur":["fabricant","fournisseur"]},
   "blocked":54,"healthy_blocked":42,"leaked":5,
   "leaked_ids":[{"id":"c-gr-X","label":"Site receipt LOT-999","company":"client"},…],
   "gates_blocked":18,"payments_blocked_eur":16910,"payments_flowing_eur":80402,
   "activity_preserved_pct":76.1,"precision":0.222,"recall":0.706,
   "companies_hit":["fabricant","fournisseur"],"blocked_ids":["f-asn-08",…]},
 "with":{"title":"With Firebreak","policy":"C",
   "subtitle":"Freeze only the tainted operations",
   "blocked":17,"healthy_blocked":0,"leaked":0,"leaked_ids":[],
   "gates_blocked":4,"payments_blocked_eur":5210,"payments_flowing_eur":92102,
   "activity_preserved_pct":100.0,"precision":1.0,"recall":1.0,
   "companies_hit":["client","distributeur","fabricant","fournisseur"],"blocked_ids":[…]},
 "healthy_blocked_ratio":null,
 "bench":{"p_values":["0.0","0.1","0.2","0.3"],"seeds_per_group":500,
   "command":"uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3",
   "groups":{"p0.0:B":{"seeds":500,"healthy_blocked_mean":43.182,"leaks_mean":0.662,"recall_mean":0.985,"activity_preserved_mean":0.838},
             "p0.0:C":{"seeds":500,"healthy_blocked_mean":9.616,"leaks_mean":0.0,"recall_mean":1.0,"activity_preserved_mean":0.964},…}},
 "real_world":[{"name":"Jaguar Land Rover","date":"September 2025","text":"…","source":"https://www.reuters.com/…"},{…}]}
```

- `truth.ids`: ids of the true contaminated perimeter (added in 1.3.0). A record in `blocked_ids` that is absent from `truth.ids` is a collateral block: the UI can hatch it without recomputing anything.
- `healthy_blocked_ratio` = `without.healthy_blocked / with.healthy_blocked` (`null` if 0 — the comparison is then "infinite").
- `bench`: aggregate of `bench/results.csv` (mean per seed, policies B and C, at `p=0` and at the highest `p` present); `null` if the file is missing.
- `real_world`: real examples of total shutdowns, with source links.

### `POST /api/ingest/document?company=<id>`

Reads a supplier document received by company `company` (purchase order, shipping notice, invoice, bank details change) and returns a record **proposal**. Nothing is added to the ledger before `…/confirm`.

Body: the raw file, one of:

| Content-Type | Content |
|---|---|
| `application/pdf` | PDF with text (a scan without text is refused) |
| `message/rfc822` | `.eml` email (headers + text body) |
| `text/plain` | Pasted text |
| `application/json` | `{"text": "<email text>"}` |

Optional parameter `received_at` (ISO 8601): time the document was received. Default: now, Paris time. This is the time compared against the compromise window. Max size: 2 MB.

On the UI side: `fetch(url, {method: "POST", body: file, headers: {"Content-Type": file.type}})`.

```bash
curl 'localhost:8000/api/ingest/document?company=fabricant&received_at=2026-10-10T16:00:00' \
  -H 'Content-Type: application/pdf' --data-binary @assets/samples/facture-rib-modifie.pdf
```

```json
{
  "id": "doc-01", "status": "pending", "source": "mock", "confidence": 0.9, "missing": [],
  "record": {
    "id": "m-doc-01", "company": "fabricant", "origin": "fournisseur", "kind": "invoice",
    "ts": "2026-10-10T16:00:00", "label": "Received invoice F-9999 — new bank details",
    "inputs": [], "gate": false,
    "payload": {"amount": 5210, "rib": "FR76 1234 5678 9000 0000 0000 666",
                "previous_rib": "FR76 3000 4028 3798 7654 3210 085",
                "bank_details_change": true, "references": ["F-9999", "BC-9999"],
                "dates": ["2026-10-10", "2026-10-12"], "rib_unknown_for_origin": true}
  }
}
```

- `record.kind`: `purchase_order`, `asn`, `invoice`, `bank_details_change`, or `null` if not recognized.
- `record.origin`: issuer recognized by its name in the document, or `null`.
- `record.payload`: only the fields found are present (`references` and `dates` always, possibly empty). `bank_details_change: true` if the document announces new bank details (RIB) **or** if the RIB has never been seen for this issuer in the ledger (`rib_unknown_for_origin: true`).
- `confidence` (0 to 1): in mock mode, share of the expected fields found for this type, capped at 0.9; in Bedrock mode, the confidence given by the model.
- `missing`: fields expected for this type but absent (e.g. `["amount"]`).

Errors: 404 if the company is unknown; 400 if the document is empty, too large, or an unreadable or text-less PDF; 422 if the JSON has no `text` field.

### `POST /api/ingest/document/{proposal_id}/confirm`

Adds the proposed record to the ledger, then recomputes everything: the record goes through the same rules as the others (issued by a compromised source after `since` → quarantine).

Optional body: `{"origin": "<id>", "inputs": ["<record id in the same ledger>", …]}` to correct the issuer or attach the document to existing records.

```bash
curl -X POST localhost:8000/api/ingest/document/doc-01/confirm
```

The confirmation is written to the ledger's audit log (`event: "document_confirmed"`, `actor: "humain"`, with the extraction source and confidence).

Response: the full state. After compromising the supplier since 14:00, the invoice above arrives as `quarantined` with `taint_path: ["m-doc-01"]` (18 blocked out of 194).

Errors: 404 if the proposal is unknown; 400 if it is already confirmed, if the issuer or type is not recognized, or if an `inputs` entry does not exist in the ledger.

Sample documents in `assets/samples/`: `facture-rib-modifie.pdf` (invoice F-9999 with new bank details), `avis-expedition.eml` (BC-1009), `bon-de-commande.txt` (BC-7001, from the distributor to the manufacturer).

### `POST /api/ingest/epcis?company=<id>`

Imports a **GS1 EPCIS 2.0** document (JSON / JSON-LD) into the ledger of `company`. The data is structured: no confirmation step; records are added immediately, then go through the same rules as the others (recomputation and alerts). Example: [`assets/samples/epcis-sample.json`](../assets/samples/epcis-sample.json) (11 events, manufacturer's ledger).

```bash
curl -X POST 'localhost:8000/api/ingest/epcis?company=fabricant' \
  -H 'Content-Type: application/json' --data @assets/samples/epcis-sample.json
```

```json
{
  "events": 11,
  "imported": [
    {"id": "m-epcis-01", "company": "fabricant", "origin": "fournisseur", "kind": "asn",
     "ts": "2026-10-10T09:00:00", "label": "Shipping notice Aciers Durand — COIL-12",
     "inputs": [], "gate": false, "verified": false,
     "payload": {"epcis": {"event_id": "urn:uuid:…", "type": "ObjectEvent", "biz_step": "shipping", …},
                 "epc_inputs": ["urn:epc:class:lgtin:3012345.012345.COIL-12"],
                 "epc_outputs": ["urn:epc:class:lgtin:3012345.012345.COIL-12"], "lot": "COIL-12"},
     "token": null, "status": "ok", "taint_path": null},
    …
    {"id": "m-epcis-08", "kind": "production_lot", "label": "Transformation COIL-77 + COIL-12 → LOT-801",
     "inputs": ["m-epcis-05", "m-epcis-02"], "gate": true,
     "payload": {…, "lot": "LOT-801", "input_lots": ["COIL-77", "COIL-12"]}, …},
    …
  ],
  "ignored": [],
  "state": {…}
}
```

Supported subset (everything else is ignored and listed in `ignored`, with `index`, `type` and `reason`):

| EPCIS element | Handling |
|---|---|
| Document | `type: "EPCISDocument"` and `epcisBody.eventList` required (otherwise 400). 1,000 events max. |
| `ObjectEvent` | Objects = `epcList` + `quantityList[].epcClass`, consumed and produced (nothing produced if `action: "DELETE"`). |
| `AggregationEvent` | Consumes `childEPCs` / `childQuantityList` (and `parentID`), produces `parentID` and the children. |
| `TransformationEvent` | Consumes `inputEPCList` / `inputQuantityList`, produces `outputEPCList` / `outputQuantityList` → `kind: "production_lot"`, `payload.input_lots`. |
| `AssociationEvent`, `TransactionEvent`, `errorDeclaration` | Ignored. |
| `eventTime` | Converted to Paris time; missing or invalid → ignored. Events are processed in `eventTime` order. |
| `bizLocation` (else `readPoint`) | `origin` = the company whose `gs1_prefix` starts the identifier (`urn:epc:id:sgln:…` or Digital Link `/414/`). No location: the importing company. Unknown location: ignored. |
| `bizStep` (URN, URL or bare term) | `shipping` → `shipment` (`asn` if done by a partner), `receiving` / `accepting` → `goods_receipt`, `inspecting` → `quality_check`, `storing` → `stock_entry`, `packing` → `packing`, other → `epcis_event`. |
| `disposition`, `sourceList`, `destinationList`, `eventID` | Copied into `payload.epcis`. |

Rules:

- `inputs` = the last record that produced each consumed object, including records from a previous import (`payload.epc_outputs`);
- `gate: true` for a shipment or transformation performed by the company itself;
- `verified: true` for a `conformant` inspection (`inspecting`) performed by the company itself: it stops propagation;
- lots: `payload.lot` = lot of the first LGTIN class produced (`urn:epc:class:lgtin:…` or Digital Link `/10/`).

After importing the example and then compromising the supplier since 14:00: 7 of the 11 imported records are blocked (`m-epcis-03` to `06`, the transformation `m-epcis-08` → LOT-801, the palletizing and the shipment). The conformant inspection of COIL-78 (`m-epcis-07`) protects LOT-802 (`m-epcis-09`). The import is written to the audit log (`event: "epcis_import"`).

Errors: 404 if the company is unknown; 400 if it is not an EPCIS document.

## Avalanche L1 (proof anchoring)

Optional and **never blocking**: the chain decides nothing, it anchors fingerprints (never business data). Disabled by default (`FIREBREAK_CHAIN=off`): existing responses are unchanged, only optional fields are `null`. Writes go through a background send queue; a `pending` or `failed` anchor is never an HTTP error.

Variables: `FIREBREAK_CHAIN` (`off` · `tester` in-memory EVM · `l1`), `FIREBREAK_CHAIN_RPC_URL`, `FIREBREAK_CHAIN_ID`, `FIREBREAK_CHAIN_EXPLORER_URL`, `FIREBREAK_CHAIN_MNEMONIC`, `FIREBREAK_CHAIN_DEPLOYMENT`. With the chain active, also set `FIREBREAK_KEY_SEED` and `FIREBREAK_PAIR_SECRET`.

What is anchored after each action: each signed alert (by the sender) then its acknowledgment (by the recipient); each incident declaration or withdrawal; the head (`head`) and length of each modified audit log.

### `GET /api/chain/status`

```json
{"mode": "tester", "connected": true, "chain_id": 1337, "contract": "0x…", "explorer_url": null,
 "run_id": "9f3c…", "last_block": 14, "queue": {"pending": 0, "sent": 0, "confirmed": 14, "failed": 0}}
```

In `off` mode: `mode: "off"`, `connected: false`, queue at zero.

### `GET /api/chain/anchors?kind=&company=`

List sorted by `created_at`. `kind`: `audit`, `alert`, `incident`, `ack`. `status`: `pending`, `sent`, `confirmed`, `failed`.

```json
[{"id": 1, "kind": "alert", "company": "fournisseur", "hash": "0x…", "status": "confirmed",
  "tx_hash": "0x…", "block": 3, "error": null, "created_at": "2026-10-11T01:30:00+00:00",
  "explorer_link": null}]
```

### `POST /api/chain/anchor`

Anchors the head of all logs now, waits up to 5 s, and returns the anchors created. **409** if the chain is disabled.

### Addition to `GET /api/audit/verify`

Each item in `journals` carries `onchain` (`null` if the chain is disabled or nothing is anchored); the root carries `onchain_ok` (`null` or boolean):

```json
"onchain": {"anchored_head": "…", "anchored_entries": 25, "block": 12, "tx_hash": "0x…",
            "explorer_link": null, "matches": true}
```

`matches`: the local log truncated to `anchored_entries` entries has `anchored_head` as its last hash.

If a confirmed anchor exists but the on-chain read fails after 3 retries (lagging node, 429), `onchain` is `{"unreadable": true, "matches": null}` and `onchain_ok` stays `null`: this is never interpreted as tampering.

### `POST /api/demo/rewrite` (only with `FIREBREAK_DEMO=1`, otherwise 404)

Body `{"company": "fabricant", "drop_event": "alert_received"}`. Deletes the first entry of that type from the log and **recomputes all hashes**: `/api/audit/verify` returns `ok: true` (the local chain is consistent) but `onchain_ok: false` (the log no longer matches the anchor). 400 if there is no entry of that type.

## Quality: suspect lot, recall, upstream report

Quality incident = no compromise: a lot is isolated on human decision, and the supplier is not declared compromised (its other lots, invoices and payments proceed). Scenarios `lot` and `recall` (`incident` key in `scenario`). All routes return 404 (unknown company or reference) or 400 (invalid state) with `{"detail": …}`.

| Route | Body / parameters | Response |
|---|---|---|
| `POST /api/lots/suspect` | `{"company", "lot", "reason"}`: `lot` = lot number or record id | the full state; the lot and its dependents are quarantined, signed alerts to customers |
| `POST /api/lots/suspect/withdraw` | `{"company", "lot"}` | the full state; cascading release (400 if the lot is not suspect) |
| `GET /api/recall?company=&ref=` | `ref` = lot or record of the product at issue | read-only: `{"company", "target", "candidates": [{"record", "label", "kind", "lot", "origin", "received", "impact_records", "impact_gates", "impact_partners"}]}` |
| `POST /api/reports` | `{"company", "ref", "reason"}` | list of signed reports (one per upstream partner) `{"id", "from", "to", "reason", "tokens_count", "records", "verified", "status", "issued_at"}`; blocks nothing |
| `GET /api/reports?company=` | without `company`: all | reports sent or received |
| `POST /api/reports/{id}/decision` | `{"company": recipient, "decision": "confirm"\|"reject"}` | the updated report (`status` `confirmed`/`rejected`); `confirm` isolates the records at issue and alerts their customers |

Audit events added: `lot_suspect`, `lot_suspect_withdrawn`, `quality_report_sent`, `quality_report_received`, `quality_report_decided`. Timeline step types: `lot_suspect`, `lot_suspect_withdrawn`, `report_sent`, `report_received`, `report_decided`. Alert type `report` added.

## Inbound stock control

When a delivery is received, a **trust score out of 100** cross-checks the company's master data (supplier records, parts and bills of materials, open orders) against what arrives (shipping notice, certificate, received invoices, alerts). Checks are deterministic and each one is explained; the score starts at 100 and each failed check subtracts its penalty. Bands: `confiance` (≥ 80), `doute` (60–79), `suspect` (< 60). **Below 80: hold** on the receipt and everything that depends on it, until a human decides. Exception: a receipt already physically checked (`verified`, `physically_checked: true`) is held only below 60; in the `doute` band it is flagged without being blocked. Demo master data: the manufacturer's (orders BC-1001…1010, except unknown BC-9999).

| Route | Body / parameters | Response |
|---|---|---|
| `GET /api/inbound/{receipt_id}/check?company=` | — | read-only: `{"receipt", "label", "supplier", "lot", "order", "score", "band", "hold", "physically_checked", "status", "checks": [{"id", "label", "ok", "penalty", "detail"}], "explanation"}` |
| `POST /api/inbound/screen` | `{"company", "receipt_id"?}` (without `receipt_id`: all receipts from a partner) | list of these same objects; receipts below the threshold get `status: "en_attente"` (quarantine of the receipt and its dependents) |
| `POST /api/inbound/{receipt_id}/decision` | `{"company", "decision": "accept"\|"reject", "reason"}` | `{"receipt", "decision", "status", "reports"}`; `accept` lifts the hold and makes the receipt trusted (`verified`), `reject` keeps it isolated and sends a signed quality report to the supplier (`reports`); 400 if already handled |

`checks[].id`: `order` (purchase order), `part` (part number and bill of materials), `qty`, `date`, `cert` (certificate present, lot and grade), `cert_no` (sequence), `lot` (format, duplicate), `rib` (supplier record), `alerts`. `status`: `non_controle`, `en_attente`, `accepte`, `refuse`. Audit events: `inbound_hold`, `inbound_accepted`, `inbound_rejected` (same names as step types). Avalanche anchoring: hold and rejection → `declareIncident`, acceptance → `withdrawIncident` (fingerprint `sha256("inbound:" + company + "|" + receipt)`).
## AI: Bedrock and mock fallback

The AI **never decides on blocking**. It explains (`/explain`), proposes a recovery plan and extracts data from documents. Extracted data enters the ledger only after human confirmation, and then goes through the graph rules.

| Variable | Default | Role |
|---|---|---|
| `FIREBREAK_AI` | `mock` | `bedrock` to use AWS Bedrock, `mock` for offline templates and regexes. |
| `FIREBREAK_BEDROCK_MODEL` | `anthropic.claude-3-haiku-20240307-v1:0` | Bedrock model or inference profile id (Converse API). |
| `AWS_REGION` | — | Bedrock region, e.g. `eu-west-3`. |
| AWS credentials | — | Standard boto3 chain: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, `AWS_PROFILE`, role… Never in the repo, never logged. |

```bash
FIREBREAK_AI=bedrock AWS_REGION=eu-west-3 AWS_PROFILE=hackathon \
  uv run uvicorn firebreak.api:app --port 8000
```

Automatic fallback to mock, with `source: "mock"` in the response and a warning in the server logs (cause only, no credentials), if:

- credentials or region are missing, or boto3 raises an error;
- Bedrock does not respond within 8 s;
- the response is not a valid JSON object;
- the explanation proposes an action other than `revalidate`, `human_approval`, `trusted_source`;
- the extraction returns a type or issuer outside the list, or a RIB, reference or date that does not appear in the document.

The explanation prompt contains only the record, the records of its `taint_path` and the rules applied (seed, propagation, gate…), not the rest of the ledger. The extraction prompt contains the document text (12,000 characters max) and the list of companies.

## Scenarios

Four companies: `fournisseur` (Aciers Durand) → `fabricant` (Mécano Précision Loire) → `distributeur` (Logidis Rhône) → `client` (Bâtiments Azur). All scenarios share the same morning: 7 clean deliveries before 14:00 (from coil received to customer payment) and internal operations. The supplier is compromised since 14:00; only the attack changes. Figures after `{"company": "fournisseur", "since": "2026-10-10T14:00:00"}` (checked by `tests/test_scenarios.py`):

| `id` | Attack | Records | Blocked | Irreversible actions blocked | What stops propagation |
|---|---|---|---|---|---|
| `mixed` (default) | Fake ASN, fake certificate and invoice with modified bank details | 193 | 17 | `m-lot-X`, `m-pay-X`, `m-ship-X`, `d-out-X` | Receipt BC-1008 physically inspected (`m-gr-08`) |
| `rib` | Bank details change email → supplier record modified → payment | 185 | 8 | `m-pay-X` | Call-back to the known number for invoice F-3008 (`m-call-08`): its payment proceeds |
| `cert` | Fake quality certificate on a real coil (COIL-210) | 193 | 13 | `m-lot-901`, `m-asm-950`, `m-ship-950`, `d-out-950` | Weighed receipt of COIL-210 (`m-gr-X`): the coil exists, only the certificate is fake. LOT-902 (other coils) and its shipment proceed |
| `asn` | Fake shipping notice (COIL-299 does not exist) | 190 | 13 | `m-lot-X`, `m-ship-X`, `d-out-X` | Receipt COIL-108 physically inspected (`m-gr-08`): LOT-908 proceeds |

- `rib` stays at the manufacturer: no physical goods go downstream.
- `cert` shows lot genealogy: LOT-901 is made with COIL-210, then subassembly ASM-950 with LOT-901 and LOT-902. ASM-950 is blocked all the way to the client; only LOT-902 proceeds.
- `asn` blocks production started on phantom stock, the reservation at the distributor and the client's site schedule.

### `mixed` scenario details

The supplier is compromised since 14:00 and sends a fake shipping notice, a fake certificate and an invoice with modified bank details. A legitimate delivery received after 14:00 is physically inspected (`m-gr-08`, `verified: true`): it stops propagation.

After `{"company": "fournisseur", "since": "2026-10-10T14:00:00"}`: 17 records blocked out of 193, 176 proceed, 4 irreversible actions blocked (`m-lot-X`, `m-pay-X`, `m-ship-X`, `d-out-X`), contamination reaching the client.
