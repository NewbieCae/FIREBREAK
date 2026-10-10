#!/usr/bin/env bash
# team-sync.sh — synchronisation d'équipe pour les agents de code (Claude Code, Devin CLI).
#
#   whoami   → id du membre (yann|mika|celine|maria) ou exit 1
#   start    → hooks SessionStart / UserPromptSubmit : synchro + rappel en contexte
#   stop     → hook Stop : rappel (block) si sessions/<m>.md / goal.md oubliés, sinon commit+push
#   sync     → version manuelle (Codex / humains) : commit+push avec statut lisible
#
# Ne fait jamais échouer le hook (exit 0), jamais d'action hors d'un arbre git,
# jamais de commit/push d'un secret. Synchronisation sérialisée par flock sur
# <git-common-dir>/auto-commit-sync.lock (même approche que hooks/auto-commit.sh).

set -u
MEMBERS="yann mika celine maria"
CMD="${1:-}"

# ---------------------------------------------------------------- utilitaires

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

json_context() { # $1 = hookEventName, $2 = texte
  python3 -c 'import json,sys
print(json.dumps({"hookSpecificOutput":{"hookEventName":sys.argv[1],"additionalContext":sys.argv[2]}},ensure_ascii=False))' "$1" "$2"
}

json_block() { # $1 = reason
  python3 -c 'import json,sys
print(json.dumps({"decision":"block","reason":sys.argv[1]},ensure_ascii=False))' "$1" "$1"
}

stdin_json_field() { # $1 = champ, $2 = défaut ; lit STDIN_JSON
  printf '%s' "$STDIN_JSON" | python3 -c 'import json,sys
try: v=json.load(sys.stdin).get(sys.argv[1],sys.argv[2])
except Exception: v=sys.argv[2]
print("true" if v is True else "false" if v is False else v)' "$1" "$2" 2>/dev/null
}

# ---------------------------------------------------------------- garde-fou secrets
# (repris de hooks/auto-commit.sh — ne jamais committer/pousser une clé)

SECRET_RE='(^|[^A-Za-z0-9])(AIza[0-9A-Za-z_-]{35}|sk-[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}([^A-Za-z0-9]|$)|xox[baprs]-[A-Za-z0-9-]{10,})|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
ENV_SECRET_RE=$'\t''[[:space:]]*(export[[:space:]]+)?[a-z0-9_]*(key|secret|token|password|passwd)[a-z0-9_]*[[:space:]]*=[[:space:]]*["'"'"']?[a-z0-9_./+=-]{16,}["'"'"']?[[:space:]]*$'

secret_files() { # stdin : diff git → fichiers dont une ligne AJOUTÉE porte un secret
  local added
  added=$(awk '/^\+\+\+ /{f=substr($0,7); next} /^\+/{print f "\t" substr($0,2)}')
  [ -n "$added" ] || return 0
  { printf '%s\n' "$added" | grep -E "$SECRET_RE"
    printf '%s\n' "$added" | grep -iE "$ENV_SECRET_RE" | grep -E '=.*[0-9]'
  } | grep -v 'auto-commit:allow' | cut -f1 | sort -u | tr '\n' ' '
}

# ----------------------------------------------------------- garde-fou conflits
# Ne jamais committer/pousser un conflit non résolu : les entrées « unmerged »
# de l'index et les marqueurs <<<<<<< / ||||||| / >>>>>>> ajoutés.
# Un « ======= » seul est volontairement ignoré (soulignement setext Markdown).
# Une ligne voulue se marque « team-sync:allow ».

MARKER_RE='^(<{7}|>{7}|\|{7})( |$)'

unmerged_files() { # fichiers en conflit réel dans l'index (avant tout git add)
  git diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' '
}

marker_files() { # stdin : diff git → fichiers dont une ligne AJOUTÉE porte un marqueur
  awk '/^\+\+\+ /{f=substr($0,7); next} /^\+/{print f "\t" substr($0,2)}' \
    | grep -v 'team-sync:allow' | grep -E "$MARKER_RE" \
    | cut -f1 | sort -u | tr '\n' ' '
}

conflict_files() { # $1 = entrées unmerged relevées AVANT git add -A (l'add les « résoudrait »)
  local after
  after=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | marker_files)
  printf '%s\n%s\n' ${1:-x} ${after:-x} | sed '/^x$/d' | sort -u | tr '\n' ' ' | sed 's/ *$//'
}

# Ré-exécution sous verrou (un seul fetch/rebase à la fois sur l'arbre partagé).
# Si le verrou n'est pas obtenu en 10 s, on ré-exécute avec TEAM_SYNC_LOCK=skip :
# un autre tour synchronise déjà le même arbre, on peut sortir sans rien perdre.
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
# TEAM_SYNC_LOCK=1 : verrou tenu. =skip : non obtenu. Non défini : pas de flock
# sur cette machine → on considère le verrou tenu (sinon rien ne tournerait).
HAVE_LOCK=0; [ "${TEAM_SYNC_LOCK:-1}" = "1" ] && HAVE_LOCK=1

# fetch + rebase --autostash sur l'amont. Retourne 0 ok / 1 conflit / 2 réseau / 3 ignoré.
SYNC_OUT=""; CONFLICT_FILES=""
sync_pull() {
  local upstream
  upstream=$(upstream_ref) || { SYNC_OUT="pas d'amont"; return 3; }
  [ -n "$upstream" ] || { SYNC_OUT="pas d'amont"; return 3; }
  if rebase_in_progress; then SYNC_OUT="rebase déjà en cours"; return 3; fi
  SYNC_OUT=$(git fetch --quiet 2>&1) || { SYNC_OUT="réseau/remote injoignable"; return 2; }
  if ! SYNC_OUT=$(git rebase --autostash "$upstream" 2>&1); then
    if rebase_in_progress; then
      CONFLICT_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')
      git rebase --abort >/dev/null 2>&1
      SYNC_OUT="conflit sur ${CONFLICT_FILES% }"
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
    SYNC_OUT="conflit au rétablissement du stash sur ${left% }"
    return 1
  fi
  SYNC_OUT=""
  return 0
}

# ---------------------------------------------------------------- stdin du hook

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
      1) problem=" Synchro : conflit à résoudre à la main ($SYNC_OUT)." ;;
      2) problem=" Synchro impossible : $SYNC_OUT." ;;
    esac
    # conflit non résolu présent dans l'arbre (unmerged ou marqueurs ajoutés)
    local_conflicts="$({ unmerged_files; git diff -U0 --no-color --no-ext-diff 2>/dev/null | marker_files; } | tr ' ' '\n' | sed '/^$/d' | sort -u | tr '\n' ' ')"
    if [ -n "${local_conflicts% }" ]; then
      problem="$problem Attention : conflit non résolu dans ${local_conflicts% }— résous-le avant tout."
    fi
  fi
  if member=$(whoami_member); then
    ctx="Coéquipier : $member. Avant de terminer ce tour, mets à jour sessions/$member.md (fait / en cours / prochaine étape) et goal.md (état du plan, blocages) — cf. AGENTS.md.$problem"
    # messages d'équipe non lus (messages.md) → livrés mot pour mot à l'utilisateur
    inbox=$(python3 "$(git rev-parse --show-toplevel)/scripts/messages.py" deliver "$member" 2>/dev/null || true)
    if [ -n "$inbox" ]; then
      ctx="$ctx

NOUVEAUX MESSAGES D'ÉQUIPE (messages.md) — affiche-les à l'utilisateur MOT POUR MOT, en tête de ta réponse, dans un bloc de citation, avant toute autre chose. Pour répondre : python3 scripts/messages.py send <destinataire> \"texte\".

$inbox"
    fi
  else
    ctx="Coéquipier inconnu : demande son nom à l'utilisateur puis exécute « git config finswag.member <yann|mika|celine|maria> ». Avant de terminer ce tour, mets à jour sessions/<membre>.md et goal.md — cf. AGENTS.md.$problem"
  fi
  json_context "$event" "$ctx"
  exit 0
fi

# ==================================================================== stop
if [ "$CMD" = "stop" ]; then
  in_work_tree || exit 0
  stop_active=$(stdin_json_field stop_hook_active "false")

  member=""; member=$(whoami_member) || member=""

  # fichiers modifiés : arbre de travail + commits locaux pas encore poussés
  changed=$({ git status --porcelain -uall 2>/dev/null | cut -c4- | sed 's/.* -> //'
              upstream_ref >/dev/null && git diff --name-only '@{u}'..HEAD 2>/dev/null
            } | sort -u)
  non_doc=$(printf '%s\n' "$changed" | grep -vE '^(sessions/|goal\.md$|messages\.md$)' | grep . || true)

  if [ -n "$non_doc" ] && [ "$stop_active" != "true" ]; then
    if [ -z "$member" ]; then
      json_block "Coéquipier non identifié : demande son nom à l'utilisateur puis exécute « git config finswag.member <yann|mika|celine|maria> », mets à jour sessions/<membre>.md et goal.md, puis termine."
      exit 0
    fi
    if ! printf '%s\n' "$changed" | grep -qx "sessions/$member.md" || \
       ! printf '%s\n' "$changed" | grep -qx "goal.md"; then
      json_block "Avant de finir : mets à jour sessions/$member.md (ce que tu as fait, en cours, prochaine étape) et goal.md (état du plan/blocages), puis termine."
      exit 0
    fi
  fi

  # commit + push (sous verrou ; sans verrou un autre tour s'en charge)
  if [ "$HAVE_LOCK" != 1 ]; then exit 0; fi
  if rebase_in_progress; then
    echo "team-sync: rebase déjà en cours — ni commit ni sync." >&2
    exit 0
  fi

  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A >/dev/null 2>&1
    leaks=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      git reset -q >/dev/null 2>&1
      msg="team-sync: SECRET détecté dans ${leaks}— rien commité ni poussé. La clé doit vivre dans un fichier ignoré ; si la ligne est voulue, la marquer « auto-commit:allow »."
      if [ "$stop_active" = "true" ]; then
        echo "$msg" >&2
      else
        json_block "$msg"
      fi
      exit 0
    fi
    git commit -m "${member:-inconnu}: sync $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 || true
  fi

  # sync amont + push (uniquement sur une branche avec upstream)
  if on_branch && upstream_ref >/dev/null; then
    upstream=$(upstream_ref)
    sync_pull; src=$?
    case "$src" in
      1)
        if [ "$stop_active" = "true" ]; then
          echo "team-sync: CONFLIT sur ${CONFLICT_FILES% } — commit local conservé, pas de push." >&2
        else
          json_block "Conflit avec un coéquipier sur ${CONFLICT_FILES% }: fais git fetch && git rebase @{u}, résous (garde les deux contributions pour goal.md), puis termine."
        fi
        exit 0 ;;
      2) echo "team-sync: synchro impossible ($SYNC_OUT) — commit local conservé." >&2 ;;
    esac
    # ne jamais pousser un secret arrivé par un commit manuel
    leaks=$(git log -p -U0 --format= --no-color --no-ext-diff "$upstream"..HEAD 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      echo "team-sync: SECRET dans un commit local pas encore poussé (${leaks% }) — PAS de push." >&2
      exit 0
    fi
    git push >/dev/null 2>&1 || \
      echo "team-sync: push échoué (réseau/remote ?) — commit local conservé." >&2
  fi
  exit 0
fi

# ==================================================================== sync (manuel)
if [ "$CMD" = "sync" ]; then
  in_work_tree || { echo "team-sync: pas dans un dépôt git."; exit 0; }
  member=""; member=$(whoami_member) || member="inconnu"
  if rebase_in_progress; then
    echo "team-sync: rebase déjà en cours — à finir ou abandonner à la main."
    exit 0
  fi
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A >/dev/null 2>&1
    leaks=$(git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      git reset -q >/dev/null 2>&1
      echo "team-sync: SECRET détecté dans ${leaks}— rien commité. Fichier ignoré requis, ou marquer la ligne « auto-commit:allow »."
      exit 0
    fi
    git commit -m "$member: sync $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 \
      && echo "team-sync: commit « $member » créé."
  else
    echo "team-sync: arbre propre, rien à committer."
  fi
  if on_branch && upstream_ref >/dev/null; then
    sync_pull; src=$?
    case "$src" in
      0) ;;
      1) echo "team-sync: conflit avec un coéquipier sur ${CONFLICT_FILES% }— rebase abandonné, commit local conservé. Résous : git fetch && git rebase @{u}."
         exit 0 ;;
      2) echo "team-sync: synchro impossible ($SYNC_OUT) — commit local conservé."
         exit 0 ;;
    esac
    leaks=$(git log -p -U0 --format= --no-color --no-ext-diff "$(upstream_ref)"..HEAD 2>/dev/null | secret_files)
    if [ -n "$leaks" ]; then
      echo "team-sync: SECRET dans un commit local pas encore poussé (${leaks% }) — PAS de push."
      exit 0
    fi
    if git push >/dev/null 2>&1; then
      echo "team-sync: poussé sur $(upstream_ref)."
    else
      echo "team-sync: push échoué (réseau/remote ?) — commit local conservé."
    fi
  else
    echo "team-sync: pas de branche/amont — commit local seulement."
  fi
  exit 0
fi

echo "usage: team-sync.sh {whoami|start|stop|sync}" >&2
exit 0
