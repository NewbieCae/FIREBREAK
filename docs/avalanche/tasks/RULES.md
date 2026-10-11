# Common rules — agents working on the Avalanche part

Read in full before any action. When in doubt, these rules take precedence over the task sheet.

## Context

- Repo: `finswag` (FIREBREAK project, hackathon). Read `docs/firebreak.md`, then `docs/avalanche/README.md`, then your task sheet.
- The engine (`engine.py`, `federation.py`, `simulation.py`, `scenario.py`, `audit.py`) belongs to Yann. **You don't modify it**, unless your sheet explicitly asks you to, and then only the strict minimum.
- The API contract is in `docs/api.md`: **we add, we don't remove or rename anything.**

## Git

- You work **only** on the `mika/avalanche-l1` branch. Check with `git branch --show-current` before starting and before each commit.
- At the start: `git fetch origin && git rebase origin/main`. On a conflict in `uv.lock`, take the `origin/main` version then rerun `uv lock`. For any other conflict, keep both contributions; if it's a product decision, stop and flag it.
- Small commits, message in French, `chain:` prefix (e.g. `chain: contrat FirebreakRegistry + tests`).
- **Forbidden**: `git push --force`, pushing to `main`, modifying another member's `sessions/`, modifying `AGENTS.md`, `.claude/`, `messages.md`. Only push the branch if the sheet asks you to.
- Don't use `scripts/team-sync.sh` or `scripts/messages.py`: they push to `main`.

## Secrets

- **Never read, never display, never copy**: `.env`, `.env.local`, any file in the `L1 blockchain/` folder, any `*MNEMONIC*`, `*PRIVATE_KEY*`, `*KEY_SEED*`, `*PAIR_SECRET*` variable.
- The code reads these values from the environment; it never logs them, never puts them in any API response, error message or test.
- In tests: the public Hardhat/Foundry test mnemonic (`test test test test test test test test test test test junk`) only.
- Before each commit: `git diff --cached` must contain no private key, no real mnemonic, and no RPC URL containing an API token.

## Code

- Python 3.12, `uv`. Run: `uv run pytest -q`. **All tests must stay green**, including other people's.
- User-visible texts and docs in English (decision of Mika on 11/10, whole repo translated); code, identifiers, file names in English.
- New dependency: only those listed in your sheet, stable version published at least 7 days ago, added with `uv add`.
- `FIREBREAK_CHAIN=off` by default: with this setting, no network module (`web3`) is imported and the API's behavior is strictly identical to `main`.
- No network calls in tests. The real L1 is only touched by the `scripts/chain_*.py` scripts run by hand.

## Mika's Windows machine (`mika/pc1`)

Found on 11/10 at 01:00: without these settings, tests fail on Windows even though they pass on Linux.

- `uv` is in `~/.local/bin`: start each command with `export PATH="$HOME/.local/bin:$PATH"`.
- The project venv is `finswag/.venv` on **Python 3.12** (if unspecified, uv picks 3.15). If recreating it: `uv sync --python 3.12`.
- **`PYTHONUTF8=1`** is mandatory: otherwise `scripts/bench.py` crashes on the cp1252 console.
- `tzdata` is now a project dependency on Windows (`tzdata; sys_platform == "win32"`, added on 11/10): `uv sync` installs it, `--no-sync` is no longer needed.
- `safe-pysha3` (pulled in by `eth-hash[pysha3]`) requires a Visual Studio compiler: it is neutralized via `[tool.uv] override-dependencies` in `pyproject.toml`, and `eth-hash` uses `pycryptodome` instead.
- Test command on this machine: `PYTHONUTF8=1 uv run pytest -q` → 231 green as of 11/10 01:55.
- `py-evm` only publishes beta versions (`0.12.1b1`) and `eth-tester` depends on it: accepted exception to the "stable versions" rule, for the dev group only. Prefer the latest **non-beta** version of `eth-tester` that resolves.

## End of task

1. `uv run pytest -q` green (paste the summary in your report).
2. Docs updated if your sheet asks for it (`docs/api.md`, `docs/avalanche/README.md`).
3. Commit on `mika/avalanche-l1`.
4. Short final report: what's done, what isn't, what the next task needs to know, and any assumption made.
