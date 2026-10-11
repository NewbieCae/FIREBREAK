# FIREBREAK — 6-step build plan

> Schedule: code freeze Sunday October 11 at 10:00, first pitch round at 12:00, final later in the day (see `goal.md`). The final interface is built by a colleague; this repo delivers **the product** (engine, API, AI) and a debug dashboard.

## Starting point (October 10, 18:40)

A first foundation already exists in the repo; it has not been reviewed yet:

- `src/firebreak/`: `model.py`, `engine.py` (graph and propagation), `federation.py` (Ed25519-signed alerts), `scenario.py` (4 companies), `simulation.py`, `ai.py` (simulated AI), `api.py` (FastAPI).
- `web/index.html`: debug dashboard (Cytoscape.js).
- `tests/`: 26 tests, all green (`uv run pytest -q`).
- Scenario: 193 records; after "supplier compromised since 14:00", 17 quarantined, 176 keep flowing, 4 gates blocked, propagation all the way to the customer.
- Launch: `uv run uvicorn firebreak.api:app --reload --port 8000`, then http://localhost:8000.

**Known gap:** when an operation is remediated, the release does not propagate to partners. Alerts already sent stay active and each company has to remediate on its own side.

## Overview

| # | Step | Deliverable | Depends on | In parallel? |
|---|---|---|---|---|
| 1 | Consolidate the foundation and freeze the API contract | Reviewed code, `docs/api.md`, CORS, README | — | No, do it first |
| 2 | Full federation and audit log | Signed quarantine release, decision log | 1 | No (touches the engine) |
| 3 | Realistic scenarios and EPCIS import | 3 selectable attacks, EPCIS JSON import | 2 | No (touches the engine) |
| 4 | Timeline and live events | Step-by-step replay, SSE stream to animate the UI | 3 | No |
| 5 | AI: Bedrock and document reading | `BedrockExplainer`, PDF/email → record extraction | 1 | **Yes**, in parallel with 2 to 4 (only `ai.py` and `ingest/` files) |
| 6 | Demo-ready | Demo script, robustness, deployment, freeze | 1 to 5 | No, last |

**Rules shared by all handoffs:**

- First read `docs/firebreak.md` (the idea), `docs/benchmark-firebreak.md` (the positioning) and this plan.
- Stack: Python 3.12, uv, FastAPI, networkx, `cryptography`, pytest. No new dependency without a reason; stable versions, released at least 7 days ago.
- User-facing text and docs in English (Mika's decision on 11/10, whole repo translated); code and identifiers in English.
- Non-negotiable principle: **blocking is decided by rules on the graph, never by the AI.** The AI explains and proposes.
- Companies never read each other's data. Only opaque tokens and signed alerts are exchanged.
- `uv run pytest -q` must stay green. Each step adds its own tests.
- Do not modify `CLAUDE.md`, `AGENTS.md` or `sessionyann.md`. Commit + push at the end of the step.

---

## Handoff 1 — Consolidate the foundation and freeze the API contract

```text
Project: FIREBREAK, finswag repo (hackathon, repo freeze Sunday 12:00).
Read docs/firebreak.md, docs/benchmark-firebreak.md and docs/plan.md before starting.

Context: a first foundation exists (src/firebreak/, web/index.html, tests/, 26 green tests),
written in one go and never reviewed. A colleague will build the final interface on top of the API:
the contract must be clean and stable from now on.

To do:
1. Review all of src/firebreak/ and tests/ looking for defects. Check these first:
   - propagation follows the rules exactly: seeds = records whose origin == source and ts >= since,
     plus those whose token appears in a verified alert; a record is tainted if one of its
     inputs is, unless it is verified or released (in which case it stops propagation);
   - taint_path is correct and recomputation is deterministic and idempotent;
   - no ledger reads another ledger's records directly;
   - alerts contain only tokens (no payload, no label, no amount).
   Fix what is wrong and add one test per bug found.
2. Freeze the API contract:
   - Pydantic response models for /api/state, /explain, /remediate (response_model), so that
     the OpenAPI (/docs) is usable by the colleague;
   - CORS open for development (localhost:5173 and localhost:3000);
   - keep the /api prefix, consistent JSON errors {"detail": ...}.
3. Write docs/api.md: each endpoint with a real request and response example
   (truncated), the meaning of the statuses (ok, quarantined, released), of the gate and
   verified fields, and of the counters.
4. README: "Running the project" section (uv sync, uvicorn, tests, dashboard and /docs URLs).
5. Remove the httpx deprecation warning from the tests if trivial, otherwise leave it.

Do not change the scenario's behavior: the test tests/test_scenario.py::test_exact_quarantined_set
must stay green with the same expected set, unless there is a proven bug (justify it in the report).

Done when: pytest green; server running on port 8000; curl of /api/state and of
POST /api/compromise OK; docs/api.md written. Commit + push.
Report: bugs found and fixed, pytest output, counters after compromise.
```

## Handoff 2 — Full federation and audit log

```text
Project: FIREBREAK, finswag repo. Read docs/firebreak.md, docs/plan.md and docs/api.md.
The foundation (step 1) is reviewed and the API contract is frozen: do not break existing endpoints,
add fields or endpoints if needed and update docs/api.md.

Goal: make the response complete across companies and provable to an auditor
(KPMG / compliance angle).

1. Federated quarantine release. Today, if the manufacturer remediates m-gr-X, the records received
   downstream (d-ship-X, c-ship-X) stay quarantined because the alerts already sent stay active.
   To implement:
   - a new signed "release" alert type (same canonical format and Ed25519 signature as
     taint alerts, with a field type: "taint" | "release"), sent when an outgoing
     record is no longer tainted after recomputation;
   - the recipient verifies the signature, removes these tokens from its seeds, recomputes and propagates
     downstream in turn, until things stabilize;
   - a release with an invalid signature is rejected and logged.
2. Append-only audit log per company: compromise declaration,
   alert sent or received (verified or not), quarantine (with the rule and the taint_path),
   remediation (action, timestamp, actor: "humain" or "règle"), release. Each entry is hash-chained
   to the previous one (sha256 of the previous entry + current entry), so we can
   prove the log has not been modified.
   Endpoints: GET /api/audit?company=..., GET /api/audit/verify (recomputes the chain and returns
   ok or the index of the first broken entry).
3. Multiple declarations: allow declaring several compromised sources, or the same one with a
   different time (keep the earliest). Endpoint to withdraw a declaration (false alarm),
   which triggers cascading releases.

Required tests: valid release → downstream released all the way to the customer; forged release → rejected,
downstream still quarantined; valid then tampered audit chain → verify detects the index;
withdrawal of a declaration → back to the initial state (zero quarantine).
Done when: pytest green, docs/api.md up to date, debug dashboard still working. Commit + push.
```

## Handoff 3 — Realistic scenarios and EPCIS import

```text
Project: FIREBREAK, finswag repo. Read docs/firebreak.md, docs/plan.md, docs/api.md.

Goal: show that FIREBREAK works on physical supply chains and builds on a
standard the industry knows (GS1 EPCIS 2.0), instead of a home-made format.

1. Three attack scenarios, selectable via POST /api/reset {"scenario": "..."}:
   - "rib": invoice with modified bank details (RIB) → payment blocked (the finance case);
   - "cert": fake quality certificate → non-compliant production lot quarantined,
     along with that lot's shipments all the way to the customer;
   - "asn": fake advance shipping notice → phantom receipt and production started on non-existent stock.
   The current scenario (the three attacks mixed) becomes "mixed" and remains the default.
   Each scenario: deterministic, between 100 and 150 records, less than 15% quarantined, at least
   one gate blocked, at least one verified record that stops propagation. Expected quarantine
   set hard-coded in the tests, reasoned out and not copied from the output.
2. Lot genealogy: model transformation (consumed lots → produced lot) as
   in an EPCIS TransformationEvent, so a tainted lot taints the lots made with it.
3. EPCIS import: module src/firebreak/ingest/epcis.py that reads an EPCIS 2.0 JSON-LD document
   (ObjectEvent, AggregationEvent, TransformationEvent; fields eventTime, bizStep,
   inputEPCList/outputEPCList, sourceList/destinationList) and converts it into a ledger's records.
   Provide a sample in assets/samples/epcis-sample.json and an endpoint
   POST /api/ingest/epcis?company=.... Only handle the useful subset, documented in docs/api.md.

Tests: one test per scenario (exact set), one lot genealogy test, one EPCIS import
test on the sample. Done when: pytest green, the three scenarios visible in the dashboard
(add a selector), docs/api.md up to date. Commit + push.
```

## Handoff 4 — Timeline and live events

```text
Project: FIREBREAK, finswag repo. Read docs/plan.md and docs/api.md.

Goal: the demo must show contamination spreading step by step, from one company to
the next, not a graph that turns red all at once. The colleague building the UI needs an
event stream.

1. Step-by-step replay: propagation and federation produce an ordered list of steps
   (declaration, seed, contamination of a record with its parent, alert sent, alert verified,
   gate quarantined, release…). Each step has a number, a type, a company, record
   ids, a simulated timestamp. Do not duplicate logic: instrument the existing
   engine (callback or event log), without changing its results.
2. Endpoints:
   - GET /api/timeline → the full list of steps of the last action;
   - GET /api/events (Server-Sent Events) → streams the steps live, with a
     ?speed= parameter to slow the replay down for the demo.
3. Debug dashboard: "Replay" button that animates the steps (nodes turning red one
   by one, alert "traveling" along the cross-company edge).
4. Document the event format in docs/api.md, with an example of consuming SSE
   in JavaScript (EventSource) for the colleague.

Tests: the final state rebuilt from the timeline is identical to /api/state; the order
is causal (a record is tainted only after its parent, an alert is received only after being
sent); minimal SSE test with TestClient.
Done when: pytest green, replay visible in the dashboard. Commit + push.
```

## Handoff 5 — AI: Bedrock and document reading (in parallel with 2 to 4)

```text
Project: FIREBREAK, finswag repo. Read docs/firebreak.md, docs/plan.md, docs/api.md.
Only modify src/firebreak/ai.py, src/firebreak/ingest/documents.py (new), their tests and
the minimum wiring in api.py: other steps are working on the engine in parallel.

Absolute rule: the AI never decides a block. It explains, proposes and extracts data;
any extracted data goes through the graph rules like any other record.

1. BedrockExplainer: implement the existing Explainer interface (explain, remediation_plan) with
   AWS Bedrock via boto3 (Converse API). Model configurable via the environment variable
   FIREBREAK_BEDROCK_MODEL, region via AWS_REGION. Selection: FIREBREAK_AI=bedrock|mock (mock by
   default). On error, timeout (8 s) or missing credentials: automatic fallback to
   MockExplainer, and the response indicates source: "mock" or "bedrock".
   The prompt receives only the record, its taint_path and the rules applied; it must
   produce an explanation in English and a recovery plan chosen from the existing actions
   (revalidate, human_approval, trusted_source). If the response is not valid JSON or proposes
   an action outside the list, reject it and use the mock.
2. Document reading: POST /api/ingest/document?company=... accepts a PDF or the text of a supplier
   email (purchase order, shipping notice, invoice, bank details change) and returns a proposed
   record (kind, label, payload: amount, RIB, references, dates) with a confidence score.
   The record is added to the ledger only after confirmation (POST .../confirm). Mock version based
   on regular expressions, Bedrock version if FIREBREAK_AI=bedrock.
   Put 3 sample documents in assets/samples/ (including an invoice with modified bank details).
3. Never log AWS credentials. No secrets in the repo.

Tests: everything in mock mode, Bedrock simulated by a fake client (no network calls in tests);
fallback to the mock on error; rejection of an off-list action; extraction of the 3 samples.
Done when: pytest green, docs/api.md up to date (AI section + environment variables). Commit + push.
```

## Handoff 6 — Demo-ready

```text
Project: FIREBREAK, finswag repo. Read docs/firebreak.md, docs/benchmark-firebreak.md,
docs/plan.md, docs/api.md. Steps 1 to 5 are delivered.

Goal: a 3-minute demo that cannot crash, and the pitch numbers.

1. Demo mode: FIREBREAK_DEMO=1 → default scenario, AI guaranteed in mock (no network
   dependency), replay speed tuned for the stage, endpoint POST /api/demo/step that advances the demo
   by one notch (to drive it by click from the UI or a keyboard).
2. Demo script in docs/demo.md: each click, what is shown on screen, the line to say,
   and the real numbers read from the API (blocked operations, operations that keep flowing, blocked
   gates, companies affected, amount of the fraudulent payment blocked). The numbers must
   come from a reproducible command, not be copied by hand.
3. Robustness: end-to-end test that runs exactly the demo script via the API
   (reset → compromise → replay → explain → remediate → federated release → audit verify); response
   time of /api/state measured (< 200 ms on the scenario); reliable reset between two runs.
4. One-command launch: scripts/demo.sh (uv sync, starts the server, opens the browser).
   Optional if time allows: minimal Dockerfile.
5. Final README: 3-line pitch, architecture, launch, links to docs/.
6. Freeze: git tag demo-freeze once everything is green.

Done when: end-to-end test green, docs/demo.md with real numbers, scripts/demo.sh tested
from a clean clone. Commit + push + tag.
```
