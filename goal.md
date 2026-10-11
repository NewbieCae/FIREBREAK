# GOAL — finswag / FIREBREAK

> File **shared by the whole team**. Every agent updates it at the end of each iteration (see `AGENTS.md` → "Team protocol").
> Only change the lines that changed and never erase someone else's work. On a Git conflict, keep both versions.

## Goal

Deliver **FIREBREAK, the supply-chain firewall**, at the Secure Horizons hackathon (Track 3 · Uncharted Frontiers):
a 3-minute demo showing that when a partner is compromised, we block **only the contaminated operations** (3 out of 100, not 100), with a provable decision and signed alerts between companies.

- **Deadline: Sunday 11 October 2026, 12:00: first pitch round** (5 min + 2 min of questions). Finalists pitch again later in the day (3 min + 3 min of questions, see `docs/pitch-firebreak.md`).
- Target code freeze: Sunday **10:00**, then pitch rehearsal until 12:00.
- Idea: `docs/firebreak.md` · Competitors: `docs/benchmark-firebreak.md` · Plan: `docs/plan.md` · API: `docs/api.md`.

## Team

| Member | Session | Role |
|---|---|---|
| Yann | `sessions/yann.md` | Product: engine, API, AI |
| Céline | `sessions/celine.md` | Test bench: quantified proof of effectiveness (`synth.py`, `scripts/bench.py`) |
| Maria | `sessions/maria.md` | to be defined (proposed: pitch slides following `design.md` + testing the interface at 1920×1080) |
| Mika | `sessions/mika.md` | Avalanche L1 (on-chain proofs) and quality scenarios (suspect lot, recall), with two agents (pc1, pc2) |

The final interface (`web/app/`, at `/app/`) is built by Yann, from `docs/api.md` and the `docs/brief-ui.md` brief; design in `design.md`.

## Progress of the 6-step plan

| # | Step | Status | Commit / note |
|---|---|---|---|
| 1 | Consolidate the foundation and freeze the API contract | Done | `37cf8dd` |
| 2 | Full federation and audit log | Done | `5ea8486` |
| 3 | Realistic scenarios and EPCIS import | Done | `6560a9c`, `76711ec` |
| 4 | Timeline and live events (SSE) | Done | `fe5ff07`, `c0476e5` (€ counters = payments only) |
| 5 | AI: Bedrock and document reading | Done | `434abde` |
| 6 | Demo-ready | Done | `9307ad8` — `bash scripts/demo.sh`, script `docs/demo.md`, figures `uv run python -m firebreak.demo_figures` |

Tests: 267 green (`uv run pytest -q`), as of 11 October at 02:50.

Demo figures (mixed scenario, supplier compromised since 14:00; source: `uv run python -m firebreak.demo_figures`): 17 operations blocked out of 193, 4 irreversible actions blocked, €5,210 of fraudulent payment blocked, €92,102 of payments still flowing.
With vs without: without Firebreak (cut off the supplier and its direct customers), 54 operations blocked of which 42 healthy, and 5 contaminated ones still get through to the customer; with Firebreak, 17 blocked, 0 healthy, 0 leaks.

## Next actions

- [x] Step 4: timeline and SSE stream (`/api/timeline`, `/api/events`, "Replay" button).
- [x] Final interface wired to the API (`docs/api.md`), following the `docs/brief-ui.md` brief (Yann) — `web/app/`, served at http://localhost:8000/app/ (`bash scripts/demo.sh` opens it): the 8 screens of the brief, bonuses included (import, partner view), Avalanche proofs if the chain is active, the 5 actions on the right arrow. Tested at 1440×900 and 1920×1080 on the 4 scenarios.
- [x] Step 6: demo mode (`FIREBREAK_DEMO=1`, `/api/demo/step`, right arrow), script `docs/demo.md`, end-to-end test.
- [x] Test bench: sensitivity sweeps (size 5/8/12 companies with 60 operations each, off-federation noise 0/10/30%) before freezing the figures (Céline) — "Sensitivity" section of `docs/bench-results.md`, data in `bench/sensitivity.csv`. **The 4 conclusions of the defence sheet hold** (C < B in collateral at every size, ratio 4.5× to 9×, growing with size; C recall 100% at p=0; at p=0.3, C below B in recall; D catches leaks whatever the noise, but 7 healthy blocked per leak caught at 30% noise). Main figures and `bench/results.csv` unchanged byte for byte.
- [x] Test bench v2: leaked gates, worst case / 5th percentile, breakdown by compromised company, policy D "Firebreak + caution", limits written by the script (Céline). **⚠️ Published figures changed on 11/10** (all companies drawn + 10% off-federation receipts): p=0 → Firebreak 9.6 healthy blocked versus 43.2 for B (4.5× fewer), recall 100% versus 98.5%, 0 irreversible action leaked; p=0.3 → recall C 93.4%, D 97.9%. `docs/bench-results.md`, `docs/fiche-defense.md`, the example in `docs/api.md` and `tests/test_compare.py` are up to date; `/api/compare` reads the CSV.
- [x] Defense sheet: one page in English, final version for submission (`docs/fiche-defense.md`): threat, mechanism, bench + system test results, known limitations, ATT&CK/NIS2 only where relevant (Yann, 11/10 12:25).
- [x] "With vs without Firebreak" wow effect: split screen ("With vs without" button + step 3 of the demo), `/api/compare`, Céline's test bench, sourced JLR and CDK cases (Yann).
- [x] Avalanche merged into `main` (Yann, 02:30). Left for Mika: `read_audit_anchor` bug (`unreadable` status, 3 attempts) and real measurements in `docs/avalanche/pitch.md`, directly on `main`.
- [x] Vercel deployment of the interface and the API (Yann): https://firebreak-zeta.vercel.app, `vercel deploy --prod` from the root.
- [x] Quality scenarios in both directions (Mika): suspect lot without blacklisting the supplier, recall analysis from a finished product, signed quality report sent upstream with a case-by-case decision; `lot` and `recall` scenarios, API (`docs/api.md`), debug panel, Avalanche anchoring. Validated on the real L1 (25 proofs, 0 failures). 295 tests green.
- [x] Show the quality flow (`lot`, `recall`) in the final interface `/app/` (Yann): guided actions in the dock ("Step 2/6 · Distributor"), recall analysis drawer, lot release; "With vs without" hidden on these scenarios (no declaration to compare).
- [x] Visual redesign of `/app/` in keynote style (Yann): black, grainy horizon, no boxes, Geist, new logo; `design.md` rewritten.
- [x] Optimised anchoring submission (Mika, pc2): demo 19/19 in ~40 s, recall 25/25 in ~80 s on the real L1.
- [x] Inbound stock control (Mika): trust score /100 for each receipt (order, part, quantity, date, certificate, lot, bank details (RIB), alerts), put on hold below 80, human decision (accept / refuse + report to the supplier). On all 3 attacks, the rigged lot is stopped at receipt. API, anchoring, debug panel; demo sheet `docs/demo-avalanche-qualite.md`. Rehearsal on the real L1 at 08:40: 60 proofs, 0 failures.
- [ ] Code freeze at 10:00: `demo-freeze` tag (Yann).
- [ ] Pitch and slides (build on `docs/benchmark-firebreak.md`).
- [ ] Notion: invite the 3 teammates with edit access (to be done by hand via Share).

## Decisions

- 10/11 12:05 (Yann): English demo video with voice-over ready in `assets/video/firebreak-demo-en.mp4` (3 min 20); silent French version in `assets/video/firebreak-demo.mp4`.
- 11/10 (Mika): the whole repo (docs, scripts, user-visible texts) is translated into English; user-visible texts and docs are in English from now on (see `AGENTS.md`).
- 11/10 05:55 (Yann): to redeploy on Vercel when the last commit is not Yann's (otherwise Vercel blocks it): `git archive HEAD | tar -x -C <folder>`, copy `.vercel/` into it, then `vercel deploy --prod` from that folder. Reminder: on Vercel, state lives in memory per instance; a multi-step flow can get lost if two requests land on two instances, hence the local demo as the priority.
- 11/10 04:50 (Yann): new interface design, to be reused in the slides: black background `#050506`, healthy in neutral white, coral = blocked, amber = recovery, blue `#6e95ff` = proof; Geist font; logo = grid of dots cut by a bar. Everything is in `design.md`.
- 11/10 03:45 (Mika): we do not blacklist a supplier over a quality problem: we isolate the lot at fault, case by case, on a human decision; alerts go both ways (downstream: signed alerts; upstream: signed quality reports).

- 11/10 04:00 (Yann): readable messaging. On display, the agent summarises each message in 1 to 3 simple sentences. On sending, a short, human message in proper sentences; technical terms are allowed if they stay concise, but no inventory of paths, routes or identifiers (details go in docs/). See AGENTS.md, Messaging section.
- 11/10 03:50 (Céline): Track 3 validated by the organisers. Schedule: first pitch at 12:00, final later in the day for the finalists.

- 11/10 03:30 (Céline): chain figures quoted = those of the real L1 (≈ 2 s per proof, 12 anchorings in ≈ 24 s), announced as "measured on our demo"; we say "a single validator in the demo, the consortium members in production"; the line "irreversible actions at p=0.3" moves from the Proof slide to the Limits slide.

- 11/10 02:50 (Céline): the pitch owns the blockchain. `docs/pitch-firebreak.md` (question 8, slides 4 and 7, demo run-through aligned with the 5 actions of `/app/` and with 193 operations), `docs/firebreak.md`, `docs/benchmark-firebreak.md`, `docs/api.md` (log limit → Avalanche anchoring), README: "the rules decide, the AI explains, the blockchain proves". TradeLens: shutdown announced end of 2022, closed early 2023.

- 11/10 02:50 (Yann): interface + API deployed on Vercel: **https://firebreak-zeta.vercel.app** (single Python function `api/index.py`, simulated AI, chain off). Backup plan for the demo if the laptop fails. State in memory per instance: hit "Reset" before the demo.
- 11/10 02:30 (Yann): Mika's Avalanche part (`mika/avalanche-l1`) is **merged into `main`** (267 tests green). Disabled by default (`FIREBREAK_CHAIN=off`), contract deployed on the test L1 (`contracts/deployments/l1.json`). API contract 1.4.0. The `mika/*` branches are integrated: everyone starts again from `main`.
- 11/10 (Yann): final interface in native HTML/CSS/JS in `web/app/`, served by the API at `/app/` (no Node, no build, self-hosted fonts). API contract 1.3.0: `truth.ids` added to `/api/compare`.
- 11/10 (Céline): bench v2 — the compromised company is drawn from all of them (end customer included); policy D = C + "missing provenance" signal read from the engine state only, presented as an upper bound; 10% legitimate off-federation receipts added as noise.

- Track 3 announced to the organisers, on 10 October.

- 10/10: test bench — ground truth = descendants, through all real dependencies, of the records issued by the compromised company after `since`, `verified` excluded (same semantics as the engine).

- 10/10: we build FIREBREAK, designed for Track 3, instead of the Track 1 options of the initial brief.
- 10/10: stack Python 3.12 + uv + FastAPI + networkx; simulated AI by default, Bedrock as an option.
- 10/10: blocking is decided by rules on the graph, never by the AI.
- 11/10: no branches, everything on `main`, pull at the start and push at the end of every iteration; conflicts arbitrated by the agent (`AGENTS.md` → "Git conflicts"). The team talks via `messages.md` (`scripts/messages.py`).

## Blockers

- [x] Test bench: seeded generator + 3 policies + CSV (Céline) — v1 figures obsolete (4.3×, 11.4 versus 49.5, 91.6%), replaced by v2 above. Reproduce: `uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3`
- [x] Signing keys and PAIR_SECRET in federation.py: stop deriving them from the name / stop hard-coding them (secrets from env or drawn per process, Céline, 11/10)
- [x] Remove e-mail addresses and mailbox details from AGENTS.md and docs/brief.md, then decide what to do with the history — historique : copie propre pour le jury (dépôt FIREBREAK) (Céline, 11/10)
- [x] README: switch to Track 3, conflict markers pushed to main resolved (Céline, 11/10)
- [x] Confirm the official switch Track 1 → Track 3 with the organisers: validated by the organisers (confirmed by Céline on 11/10, the note was missing)
