# finswag project context

## Team protocol — EVERY AGENT THAT OPENS THIS REPO MUST READ THIS

Four people work on this repo at the same time, each with their own agent (Claude Code, Devin, Codex…): **Yann, Céline, Maria, Mika**. Everyone works directly on `main`. Communication goes through versioned files:

| File | Role | Who writes it |
|---|---|---|
| `goal.md` | Shared goal, plan progress, next actions, decisions, blockers | Everyone |
| `sessions/<member>.md` | What each member has done, is doing now, will do next, and what they need | Only that member's agent |
| `docs/plan.md` | 6-step build plan and handoffs | Updated when the plan changes |
| `messages.md` | Team messaging: we talk to each other through the repo | Everyone, via `scripts/messages.py send` |

### Who am I?

The member is identified by `scripts/team-sync.sh whoami`. It checks, in this order: the `FINSWAG_MEMBER` variable, then `git config finswag.member`, then the Git e-mail and name. If it finds no one, **ask the user for their first name**, then run `git config finswag.member <yann|celine|maria|mika>`.

### Every iteration (mandatory)

1. **At the start**: sync (`git fetch && git rebase --autostash @{u}`), read `goal.md` and your own session. Look at the other sessions before touching a shared area.
2. **During**: before taking a task from `goal.md`, put your first name on it (`- [ ] … (Maria)`) and push right away, so that two people never work on the same task.
3. **At the end of every real iteration, before handing back** (Yann's rule from 11/10: **pull at the start, push at the end, every time, for everyone**):
   - update `sessions/<member>.md`: "Where I am", "In progress", "Next step", "Needs from others", plus a dated line at the top of the "Log";
   - update `goal.md`: tick what is done, adjust the progress table, add decisions and blockers;
   - commit then push to `main` (`scripts/team-sync.sh sync` does it, with a guard against secrets).
4. **Never edit another member's session.** In `goal.md`, only change the lines concerned. On a Git conflict, keep both contributions.

### The automatic hook

`.claude/settings.json` wires `scripts/team-sync.sh` into Claude Code and Devin CLI. Devin also reads the hooks in `.claude/`.

- **Session start and every message**: pull, plus a reminder of the member and the protocol.
- **End of turn**: if code changed without `sessions/<member>.md` and `goal.md` being updated, the hook asks the agent to update them (only once). Then it commits, rebases onto `origin/main` and pushes. If it finds a secret, it does not commit. On a conflict with a teammate, it does not push and says so.
- **Codex and other agents without hooks** apply this protocol by hand and end each iteration with `bash scripts/team-sync.sh sync`.

### Common rules

- Read `goal.md`, `docs/firebreak.md` and `docs/plan.md` before coding. The API contract is in `docs/api.md`: do not break an existing endpoint.
- `uv run pytest -q` must stay green before every push.
- No secrets in the repo: keys go in `.env.local`, which is ignored.
- User-visible texts and docs are in English (Mika's decision on 11/10: the whole repo was translated).

### Messaging — `messages.md`, we talk through the repo

- **Read**: on every turn, the `team-sync.sh start` hook hands the agent the unread messages addressed to the member (`tous` or their first name). The agent **summarises them at the top of its reply**, before anything else: "From Mika (03:57):" then 1 to 3 sentences in plain English about what changes and what is expected of the user. No raw quotes and no technical inventory. A technical term, file name or route is allowed if it serves the meaning and fits in a proper sentence. Without a hook (Codex, human): `python3 scripts/messages.py deliver` at the start of the iteration.
- **Write**: when the user says "send a message to Maria", "tell everyone that…", "ask Yann…", the agent runs `python3 scripts/messages.py send <tous|yann|celine|maria|mika> "text"`. The script commits and pushes on its own. Several recipients: `yann,mika`. **The message is short and readable by a human**: simple sentences, only the essentials (what is done, what is expected of the other person). Technical terms are allowed if they stay concise and are part of a proper sentence. What is forbidden is an inventory: lists of paths, routes or identifiers. Details go in `docs/`; if needed, the message just says where to look.
- **Never edit an existing message.** The file is `merge=union` (`.gitattributes`): two people appending at the same time do not create a conflict.
- **On Yann's machine** a cron job (`python3 scripts/messages.py poll`) checks every minute and sends a desktop notification. Anyone can install the same: `crontab -e` then `* * * * * cd <repo> && python3 scripts/messages.py poll`.

### Git conflicts — no branches, the agent arbitrates

Decision of 11/10: everyone pushes to `main`, no branches or pull requests. Conflicts are resolved by the agent of whoever pushes second.

- **Avoid conflicts rather than resolve them.** Everyone works in their own area (engine in `src/firebreak/`, interface in its own folder). Two people on the same file at the same time is where things break. Push often, in small commits: a 3-line conflict resolves itself, a 200-line conflict after 2 hours without pushing does not.
- **Shared files (`goal.md`, `docs/`)**: add lines, do not rewrite. On a conflict, keep both contributions.
- **When the hook says "conflict, not pushed"**: ask your agent to run `git fetch && git rebase @{u}`, resolve, run `uv run pytest -q`, then push. Green tests = good merge. Red tests = failed merge, not necessarily the code.
- **The agent does not decide alone** when it is not a text conflict but a product choice: two versions of the same function, or an endpoint change in `docs/api.md` that the interface uses. It asks the question, and the two people decide together.
- **Never `git push --force`** on `main`. It is the one way to lose someone else's work.
- The root stays clean: every file goes in the right folder (`docs/`, `assets/`, `scripts/`, `src/`, `tests/`, `web/`).

## Notion — current state

A "finswag" Notion page is used for scoping and coordination (private). Teammate invitations and contact details are **not** kept in this repo: they stay in Notion or in the team mailbox. Reuse the existing page; do not create a new one.

The organisers' brief is summarised in `docs/brief.md`. Tracks A/B/C/D from the initial brief are proposals, not decisions; the chosen product is FIREBREAK (see `goal.md`). The GitHub repo is private.
