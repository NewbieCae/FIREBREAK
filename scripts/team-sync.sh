#!/usr/bin/env bash
# team-sync.sh — team synchronisation for coding agents (Claude Code, Devin CLI).
#
#   whoami   → member id (yann|mika|celine|maria) or exit 1
#   start    → SessionStart / UserPromptSubmit hooks: sync + reminder in context
#   stop     → Stop hook: reminder (block) if sessions/<m>.md / goal.md were forgotten, else commit+push
#   sync     → manual version (Codex / humans): commit+push with a readable status
#
# Never makes the hook fail (exit 0), never acts outside a git work tree,
# never commits/pushes a secret. Sync is serialised by flock on
# <git-common-dir>/auto-commit-sync.lock (same approach as hooks/auto-commit.sh).

set -u
MEMBERS="yann mika celine maria"
CMD="${1:-}"

# ---------------------------------------------------------------- utilities

in_work_tree() { git rev-parse --is-inside-work-tree >/dev/null 2>&1; }

member_valid() { case " $MEMBERS " in *" $1 "*) return 0 ;; esac; return 1; }

whoami_member() {
  local m
  for m in "${FINSWAG_MEMBER:-}" "$(git config --get finswag.member 2>/dev/null)"; do
    [ -n "$m" ] || continue
    m=$(printf '%s' "$m" | tr 'A-Z' 'a-z' | tr -d '[:space:]')
    member_valid "$m" && { printf '%s' "$m"; return 0; }
  done
  local id
  id="$(git config user.email 2>/dev/null) $(git config user.name 2>/dev/null)"
  id=$(printf '%s' "$id" | tr 'A-Z' 'a-z')
  case "$id" in
    *yann*|*scarville*|*sc4rville*|*makzume*) printf 'yann'; return 0 ;;
    *celine*|*fofana*|*newbiecae*)           printf 'celine'; return 0 ;;
    *maria*|*magraku*|*gracia*)             printf 'maria'; return 0 ;;
    *mika*|*codol*)                         printf 'mika'; return 0 ;;
  esac
  return 1
}

rebase_in_progress() {
  [ -d "$(git rev-parse --git-path rebase-merge 2>/dev/null)" ] || \
  [ -d "$(git rev-parse --git-path rebase-apply 2>/dev/null)" ]
}

upstream_ref() { git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null; }

on_branch() { git symbolic-ref --short -q HEAD >/dev/null 2>&1; }

json_context() { # $1 = hookEventName, $2 = text
  python3 -c 'import json,sys
print(json.dumps({"hookSpecificOutput":{"hookEventName":sys.argv[1],"additionalContext":sys.argv[2]}},ensure_ascii=False))' "$1" "$2"
}

json_block() { # $1 = reason
  python3 -c 'import json,sys
print(json.dumps({"decision":"block","reason":sys.argv[1]},ensure_ascii=False))' "$1" "$1"
}

stdin_json_field() { # $1 = field, $2 = default; reads STDIN_JSON
  printf '%s' "$STDIN_JSON" | python3 -c 'import json,sys
try: v=json.load(sys.stdin).get(sys.argv[1],sys.argv[2])
except Exception: v=sys.argv[2]
print("true" if v is True else "false" if v is False else v)' "$1" "$2" 2>/dev/null
}

# ---------------------------------------------------------------- secret guard
# (taken from hooks/auto-commit.sh — never commit/push a key)

SECRET_RE='(^|[^A-Za-z0-9])(AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}([^A-Za-z0-9]|$)|xox[baprs]-[A-Za-z0-9-]{10,})|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
ENV_SECRET_RE=$'\t''[[:space:]]*(export[[:space:]]+)?[a-z0-9_]*(key|secret|token|password|passwd)[a-z0-9_]*[[:space:]]*=[[:space:]]*["'"'"']?[a-z0-9_./+=-]{16,}["'"'"']?[[:space:]]*$'

secret_files() { # stdin: git diff → files where an ADDED line carries a secret
  local added
  added=$(awk '/^\+\+\+ /{f=substr($0,7); next} /^\+/{print f "\t" substr($0,2)}')
  [ -n "$added" ] || return 0
  { printf '%s\n' "$added" | grep -E "$SECRET_RE"
    printf '%s\n' "$added" | grep -iE "$ENV_SECRET_RE" | grep -E '=.*[0-9]'
  } | grep -v 'auto-commit:allow' | cut -f1 | sort -u | tr '\n' ' '
}

# ----------------------------------------------------------- conflict guard
# Never commit/push an unresolved conflict: "unmerged" index entries
# and added <<<<<<< / ||||||| / >>>>>>> markers.
# A lone "=======" is deliberately ignored (Markdown setext underline).
# An intended line is marked "team-sync:allow".

MARKER_RE='(<{7}|>{7}|\|{7})( |$)'   # marker at the START of an added line
MARKER_TAB=$(printf '\t')           # the awk extraction yields "file<TAB>line"

unmerged_files() { # files really in conflict in the index (before any git add)
  git diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' '
}

marker_files() { # stdin: git diff → files where an ADDED line carries a marker
  awk '/^\+\+\+ /{f=substr($0,7); next} /^\+/{print f "\t" substr($0,2)}' \
    | grep -v 'team-sync:allow' | grep -E "${MARKER_TAB}${MARKER_RE}" \
    | cut -f1 | sort -u | tr '\n' ' '
}

conflict_files() { # $1 = unmerged entries collected BEFORE git add -A (the add would "resolve" them)
  local after
  after=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | marker_files)
  printf '%s\n%s\n' ${1:-x} ${after:-x} | sed '/^x$/d' | sort -u | tr '\n' ' ' | sed 's/ *$//'
}

# Re-run under a lock (only one fetch/rebase at a time on the shared tree).
# If the lock is not acquired within 10 s, re-run with TEAM_SYNC_LOCK=skip:
# another turn is already syncing the same tree, we can exit without losing anything.
if [ -z "${TEAM_SYNC_LOCK:-}" ]; then
  if in_work_tree && command -v flock >/dev/null 2>&1; then
    gcd=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
          || git rev-parse --git-common-dir 2>/dev/null)
    if [ -n "$gcd" ]; then
      flock -E 75 -w 10 "$gcd/auto-commit-sync.lock" \
            env TEAM_SYNC_LOCK=1 "$0" "$@"
      rc=$?
      if [ "$rc" = 75 ]; then
        TEAM_SYNC_LOCK=skip "$0" "$@"
        exit $?
      fi
      exit "$rc"
    fi
  fi
fi
# TEAM_SYNC_LOCK=1: lock held. =skip: not acquired. Unset: no flock
# on this machine → treat the lock as held (otherwise nothing would run).
HAVE_LOCK=0; [ "${TEAM_SYNC_LOCK:-1}" = "1" ] && HAVE_LOCK=1

# fetch + rebase --autostash onto upstream. Returns 0 ok / 1 conflict / 2 network / 3 skipped.
SYNC_OUT=""; CONFLICT_FILES=""
sync_pull() {
  local upstream
  upstream=$(upstream_ref) || { SYNC_OUT="no upstream"; return 3; }
  [ -n "$upstream" ] || { SYNC_OUT="no upstream"; return 3; }
  if rebase_in_progress; then SYNC_OUT="rebase already in progress"; return 3; fi
  SYNC_OUT=$(git fetch --quiet 2>&1) || { SYNC_OUT="network/remote unreachable"; return 2; }
  # Already up to date (upstream is contained in HEAD): no rebase. A rebase
  # would flatten a local merge (e.g. a teammate's branch) into conflicts.
  if git merge-base --is-ancestor "$upstream" HEAD 2>/dev/null; then
    SYNC_OUT=""
    return 0
  fi
  if ! SYNC_OUT=$(git rebase --autostash "$upstream" 2>&1); then
    if rebase_in_progress; then
      CONFLICT_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')
      git rebase --abort >/dev/null 2>&1
      SYNC_OUT="conflict on ${CONFLICT_FILES% }"
      return 1
    fi
    SYNC_OUT=$(printf '%s' "$SYNC_OUT" | tail -1)
    return 2
  fi
  # autostash reapplied with a conflict → index entries unmerged (no rebase running)
  local left
  left=$(unmerged_files)
  if [ -n "${left% }" ]; then
    CONFLICT_FILES="$left"
    SYNC_OUT="conflict while restoring the stash on ${left% }"
    return 1
  fi
  SYNC_OUT=""
  return 0
}

# ---------------------------------------------------------------- hook stdin

STDIN_JSON=""
[ -t 0 ] || STDIN_JSON=$(timeout 1 cat 2>/dev/null)

# ==================================================================== whoami
case "$CMD" in
whoami)
  in_work_tree || exit 1
  whoami_member || exit 1
  exit 0
  ;;
esac

# ==================================================================== start
if [ "$CMD" = "start" ]; then
  event=$(stdin_json_field hook_event_name "UserPromptSubmit")
  case "$event" in SessionStart|UserPromptSubmit) ;; *) event="UserPromptSubmit" ;; esac
  problem=""
  if in_work_tree && [ "$HAVE_LOCK" = 1 ]; then
    sync_pull; src=$?
    case "$src" in
      1) problem=" Sync: conflict to resolve by hand ($SYNC_OUT)." ;;
      2) problem=" Sync failed: $SYNC_OUT." ;;
    esac
    # unresolved conflict present in the tree (unmerged or added markers)
    local_conflicts="$({ unmerged_files; git diff -U0 --no-color --no-ext-diff 2>/dev/null | marker_files; } | tr ' ' '\n' | sed '/^$/d' | sort -u | tr '\n' ' ')"
    if [ -n "${local_conflicts% }" ]; then
      problem="$problem Warning: unresolved conflict in ${local_conflicts% }— resolve it before anything else."
    fi
  fi
  if member=$(whoami_member); then
    ctx="Teammate: $member. Before ending this turn, update sessions/$member.md (done / in progress / next step) and goal.md (plan status, blockers) — see AGENTS.md.$problem"
    # unread team messages (messages.md) → summarised in plain language for the user
    inbox=$(python3 "$(git rev-parse --show-toplevel)/scripts/messages.py" deliver "$member" 2>/dev/null || true)
    if [ -n "$inbox" ]; then
      ctx="$ctx

NEW TEAM MESSAGES (messages.md) — at the top of your reply, before anything else, summarise each message for the user: \"From <first name> (time):\" then 1 to 3 sentences in plain English (what changes for them, what is expected of them). No raw quotes and no lists of paths, routes or identifiers; a technical term is fine if it is concise and part of a proper sentence. To reply: python3 scripts/messages.py send <recipient> \"text\", in concise, complete sentences, without a technical inventory.

$inbox"
    fi
  else
    ctx="Unknown teammate: ask the user for their name, then run \"git config finswag.member <yann|mika|celine|maria>\". Before ending this turn, update sessions/<member>.md and goal.md — see AGENTS.md.$problem"
  fi
  json_context "$event" "$ctx"
  exit 0
fi

# ==================================================================== stop
if [ "$CMD" = "stop" ]; then
  in_work_tree || exit 0
  stop_active=$(stdin_json_field stop_hook_active "false")

  member=""; member=$(whoami_member) || member=""

  # changed files: work tree + local commits not yet pushed
  changed=$({ git status --porcelain -uall 2>/dev/null | cut -c4- | sed 's/.* -> //'
              upstream_ref >/dev/null && git diff --name-only '@{u}'..HEAD 2>/dev/null
            } | sort -u)
  non_doc=$(printf '%s\n' "$changed" | grep -vE '^(sessions/|goal\.md$|messages\.md$)' | grep . || true)

  if [ -n "$non_doc" ] && [ "$stop_active" != "true" ]; then
    if [ -z "$member" ]; then
      json_block "Teammate not identified: ask the user for their name, then run \"git config finswag.member <yann|mika|celine|maria>\", update sessions/<member>.md and goal.md, then finish."
      exit 0
    fi
    if ! printf '%s\n' "$changed" | grep -qx "sessions/$member.md" || \
       ! printf '%s\n' "$changed" | grep -qx "goal.md"; then
      json_block "Before finishing: update sessions/$member.md (what you did, in progress, next step) and goal.md (plan status/blockers), then finish."
      exit 0
    fi
  fi

  # commit + push (under the lock; without it another turn takes care of it)
  if [ "$HAVE_LOCK" != 1 ]; then exit 0; fi
  if rebase_in_progress; then
    echo "team-sync: rebase already in progress — no commit, no sync." >&2
    exit 0
  fi

  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    unmerged=$(unmerged_files)          # BEFORE git add -A: the add would "resolve" it
    conflicts=""
    if [ -n "${unmerged% }" ]; then
      conflicts="${unmerged% }"         # no add: keep the merge state intact
    else
      git add -A >/dev/null 2>&1
      conflicts=$(conflict_files "")
      [ -n "$conflicts" ] && git reset -q >/dev/null 2>&1
    fi
    if [ -n "$conflicts" ]; then
      msg="Unresolved conflict in $conflicts (<<<<<<< / >>>>>>> markers or conflicted file): nothing committed or pushed. Resolve them (keep both contributions if it is goal.md or a doc), rerun uv run pytest -q, then finish."
      if [ "$stop_active" = "true" ]; then
        echo "team-sync: $msg" >&2
      else
        json_block "$msg"
      fi
      exit 0
    fi
    leaks=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      git reset -q >/dev/null 2>&1
      msg="team-sync: SECRET detected in ${leaks}— nothing committed or pushed. The key must live in an ignored file; if the line is intended, mark it \"auto-commit:allow\"."
      if [ "$stop_active" = "true" ]; then
        echo "$msg" >&2
      else
        json_block "$msg"
      fi
      exit 0
    fi
    git commit -m "${member:-unknown}: sync $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 || true
  fi

  # upstream sync + push (only on a branch with an upstream)
  if on_branch && upstream_ref >/dev/null; then
    upstream=$(upstream_ref)
    sync_pull; src=$?
    case "$src" in
      1)
        if [ "$stop_active" = "true" ]; then
          echo "team-sync: CONFLICT on ${CONFLICT_FILES% } — local commit kept, no push." >&2
        else
          json_block "Conflict with a teammate on ${CONFLICT_FILES% }: run git fetch && git rebase @{u}, resolve (keep both contributions for goal.md), then finish."
        fi
        exit 0 ;;
      2) echo "team-sync: sync failed ($SYNC_OUT) — local commit kept." >&2 ;;
    esac
    # never push a secret that came in through a manual commit
    leaks=$(git log -p -U0 --format= --no-color --no-ext-diff "$upstream"..HEAD 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      echo "team-sync: SECRET in a local commit not yet pushed (${leaks% }) — NO push." >&2
      exit 0
    fi
    # nor an unresolved conflict committed by hand
    markers=$(git log -p -U0 --format= --no-color --no-ext-diff "$upstream"..HEAD 2>/dev/null | marker_files)
    if [ -n "$markers" ]; then
      msg="Unresolved conflict committed in ${markers% } (<<<<<<< / >>>>>>> markers) — NO push. Resolve them, rerun uv run pytest -q, then finish."
      if [ "$stop_active" = "true" ]; then
        echo "team-sync: $msg" >&2
      else
        json_block "$msg"
      fi
      exit 0
    fi
    git push >/dev/null 2>&1 || \
      echo "team-sync: push failed (network/remote?) — local commit kept." >&2
  fi
  exit 0
fi

# ==================================================================== sync (manual)
if [ "$CMD" = "sync" ]; then
  in_work_tree || { echo "team-sync: not in a git repository."; exit 0; }
  member=""; member=$(whoami_member) || member="unknown"
  if rebase_in_progress; then
    echo "team-sync: rebase already in progress — finish or abort it by hand."
    exit 0
  fi
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    unmerged=$(unmerged_files)          # BEFORE git add -A: the add would "resolve" it
    conflicts=""
    if [ -n "${unmerged% }" ]; then
      conflicts="${unmerged% }"         # no add: keep the merge state intact
    else
      git add -A >/dev/null 2>&1
      conflicts=$(conflict_files "")
      [ -n "$conflicts" ] && git reset -q >/dev/null 2>&1
    fi
    if [ -n "$conflicts" ]; then
      echo "team-sync: Unresolved conflict in $conflicts (<<<<<<< / >>>>>>> markers or conflicted file): nothing committed or pushed. Resolve them (keep both contributions if it is goal.md or a doc), rerun uv run pytest -q, then finish."
      exit 0
    fi
    leaks=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      git reset -q >/dev/null 2>&1
      echo "team-sync: SECRET detected in ${leaks}— nothing committed. Use an ignored file, or mark the line \"auto-commit:allow\"."
      exit 0
    fi
    git commit -m "$member: sync $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 \
      && echo "team-sync: commit \"$member\" created."
  else
    echo "team-sync: clean tree, nothing to commit."
  fi
  if on_branch && upstream_ref >/dev/null; then
    sync_pull; src=$?
    case "$src" in
      0) ;;
      1) echo "team-sync: conflict with a teammate on ${CONFLICT_FILES% }— rebase aborted, local commit kept. Resolve: git fetch && git rebase @{u}."
         exit 0 ;;
      2) echo "team-sync: sync failed ($SYNC_OUT) — local commit kept."
         exit 0 ;;
    esac
    leaks=$(git log -p -U0 --format= --no-color --no-ext-diff "$(upstream_ref)"..HEAD 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      echo "team-sync: SECRET in a local commit not yet pushed (${leaks% }) — NO push."
      exit 0
    fi
    markers=$(git log -p -U0 --format= --no-color --no-ext-diff "$(upstream_ref)"..HEAD 2>/dev/null | marker_files)
    if [ -n "$markers" ]; then
      echo "team-sync: Unresolved conflict committed in ${markers% } (<<<<<<< / >>>>>>> markers) — NO push."
      exit 0
    fi
    if git push >/dev/null 2>&1; then
      echo "team-sync: pushed to $(upstream_ref)."
    else
      echo "team-sync: push failed (network/remote?) — local commit kept."
    fi
  else
    echo "team-sync: no branch/upstream — local commit only."
  fi
  exit 0
fi

echo "usage: team-sync.sh {whoami|start|stop|sync}" >&2
exit 0
