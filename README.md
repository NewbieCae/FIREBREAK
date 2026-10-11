# finswag — FIREBREAK

Private repo of the finswag project, Team 14 at the Secure Horizons hackathon, Track 3 "Uncharted Frontiers" (FIREBREAK project, a firewall for supply chains).

## The pitch in 3 lines

When a supply-chain partner is compromised, FIREBREAK quarantines
**only the contaminated operations** — found through a dependency graph
with verifiable rules — keeps the rest running, and propagates signed
alerts to partners without disclosing their business data. The AI only
explains decisions already made by the rules — it blocks nothing.

## Architecture

- `src/firebreak/` — engine: `engine.py` (records + BFS propagation,
  seeds by origin/window or alert tokens, `verified`/`released` rules),
  `federation.py` (Ed25519 alerts with opaque tokens), `simulation.py`
  (fixed point + timeline), `audit.py` (hash-chained logs),
  `scenario.py` (4 scenarios: mixed / rib / cert / asn),
  `ingest/` (supplier documents + EPCIS 2.0), `ai.py`
  (deterministic mock, optional Bedrock with mock fallback), `api.py` (FastAPI),
  `chain/` (proof anchoring on an Avalanche L1, optional and non-blocking,
  `FIREBREAK_CHAIN=off|tester|l1`).
- `contracts/` — `FirebreakRegistry.sol` contract (fingerprints of alerts,
  acknowledgements, declarations and logs; writes restricted to members);
  plan and pitch in [docs/avalanche/](docs/avalanche/README.md).
- `web/app/` — **final interface** (control room, HTML/CSS/JS with no build step), served at `/app/`; design in [design.md](design.md).
- `web/index.html` — debug dashboard (Cytoscape, step-by-step replay,
  demo driven by click or right arrow).
- `tests/` — pytest suite (engine, federation, scenarios, timeline, demo).
- `docs/` — [product](docs/firebreak.md), [API contract](docs/api.md),
  [demo script](docs/demo.md), [plan](docs/plan.md),
  [benchmark](docs/benchmark-firebreak.md), [interface brief](docs/brief-ui.md).

## Running the demo

```bash
bash scripts/demo.sh        # uv sync → server :8000 → browser
uv run pytest -q            # tests
uv run python -m firebreak.demo_figures   # the pitch figures (reproducible)
```

Interface: http://localhost:8000/app/ — debug dashboard: http://localhost:8000 — interactive API: http://localhost:8000/docs.

Secrets: see `.env.example` (never a real key in the repo). Without configuration, the signing keys and federation tokens are random on every start.

Variables: `FIREBREAK_DEMO=1` (fixed scenario, mock AI, replay pacing);
`FIREBREAK_AI=bedrock` + `AWS_REGION` + AWS credentials for the Bedrock
explainer ([details](docs/api.md#ai-bedrock-and-mock-fallback)).

## Team coordination

- [goal.md](goal.md) (shared goal and progress),
  [sessions/](sessions/) (one session per member), protocol in
  [AGENTS.md](AGENTS.md).
- [Notion page — brief and coordination](https://app.notion.com/p/3f58c3ea1f5e81e88164e25c35e8475e)

The brief calls for AWS Bedrock and Avalanche Fuji. The chosen product is FIREBREAK (see `goal.md`): Bedrock for the explainer, and a dedicated Avalanche L1 (not Fuji) to anchor the proofs.
