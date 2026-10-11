# Maria: kicking off the interface build (UI/UX)

> Written by Mika's agent (pc2) for Maria. Submission Sunday 12:00, **code freeze at 10:00**, pitches until 17:00.
> This file does not replace `sessions/maria.md` (to be kept up to date by your agent).

## In a nutshell

The engine and the API are delivered. What's missing is **the final interface**: a dark, glassy "incident control room" where a juror clicks and understands on their own. Everything is described in [`docs/brief-ui.md`](brief-ui.md): read it in full, it's the spec. The `web/index.html` dashboard is a debug tool, not to be imitated, but it shows every API call that works.

## Getting started (5 min)

```powershell
git clone git@github.com:Sc4rville/finswag.git   # or git pull if already cloned
cd finswag
uv sync            # or: python -m venv .venv ; .venv\Scripts\pip install -e . pytest httpx tzdata
$env:FIREBREAK_DEMO='1'; $env:PYTHONUTF8='1'
uv run uvicorn firebreak.api:app --port 8000   # then http://localhost:8000
```

On Windows, `PYTHONUTF8=1` avoids test failures (cp1252 encoding).

## What you tell your agent (paste as is)

```
You're working on FIREBREAK, Secure Horizons hackathon, team of 4. I'm Maria.
Submission Sunday 12:00, code freeze at 10:00. My mission: build the final interface (UI/UX).

1. Read in this order: AGENTS.md, goal.md, docs/firebreak.md, docs/brief-ui.md (my spec,
   to follow to the letter), docs/api.md (API contract, we don't break it),
   docs/agents-canal.md (end of file), web/index.html (examples of calls that work).
2. Register in sessions/maria.md and goal.md: task "Final interface (UI/UX)".
   Don't touch the engine (engine, federation, simulation, audit) or api.py: if you need
   a field or an endpoint, write it in docs/agents-canal.md and ask Yann.
3. My files: a web/app/ (or web/ui/) folder and design.md. Don't replace
   web/index.html until the new UI is ready: keep it as a fallback.
4. Deliver in 4 stages, a working demo at the end of each, one commit per stage:
   a) Skeleton: dark background + slow gradient, header (scenario selector, Reset,
      AI indicator), 3 big figures (/api/state counters.global), map of the 4 companies.
   b) Propagation: compromise button, SSE stream /api/events, particles on cross
      edges, precise coral red, animated counters (tabular-nums).
   c) Proof and healing: click on a blocked operation -> exact path + explanation
      (/explain), remediation, release cascade in amber then green, false alarm.
   d) With/without Firebreak (side by side), animated logo (once), consistent icon set,
      skeletons, error toasts in English, prefers-reduced-motion.
5. Non-negotiable design rules: 4 semantic colors (healthy mint green, blocked coral red
   < 15% of the screen, recovery amber, cyan accent), glass = a single recipe, never
   long text on glass, contrast >= 4.5:1, all user-visible text and docs in English
   (decision of Mika on 11/10, whole repo translated), mono for hashes/tokens.
   Record the final choices in design.md.
6. Test for real: start the server, open the page in the browser, run through the
   3-minute demo (section 6 of the brief), check that no error shows up in the console.
7. No heavy dependency: pick whatever is fastest (native HTML/CSS/JS or Vite).
   If a build is needed, commit the output so the server serves it without Node.
8. Keep sessions/maria.md up to date at each stage. No force-push. Short commits in French.
```

## Plan for it now: the Avalanche panel

Mika is integrating an Avalanche L1 blockchain (anchoring of audit logs and alerts) and is adding **optional** endpoints to the API, never blocking:

| Endpoint | For the UI |
|---|---|
| `GET /api/chain/status` | `mode` (off/tester/l1), `connected`, `chain_id`, `queue`: "Avalanche" badge in the header |
| `GET /api/chain/anchors` | list of anchors (type, company, hash, status, `explorer_link`): "Proofs on Avalanche" panel |
| `GET /api/audit/verify` | `onchain` field per log + `onchain_ok`: "anchored on Avalanche" check in the proof view |
| `POST /api/demo/rewrite` | demo: rewrite of a log; local = intact, on-chain = **does not match** |

UI rules: if `mode` is `off` or if `onchain` is `null`, **display nothing** (no empty panel). A `pending` or `failed` status is a normal state, not an error. The detailed contract is in `docs/avalanche/` (branch `mika/avalanche-l1`); Mika wires the panel into `web/index.html` directly, and your design will reuse the same data once the chain is merged.

## Coordination

- Questions, API needs: `docs/agents-canal.md` (append only at the bottom, sign `maria/…`).
- Decision conflict: see `AGENTS.md` and the channel.
- Schedule: playable demo at **9:00** Sunday, polish until the **10:00** freeze, nothing after that.
