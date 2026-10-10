#!/usr/bin/env python3
"""messages.py — messagerie d'équipe dans le dépôt (fichier messages.md).

    send <to> <texte>      ajoute un message (to = tous | yann | mika | celine | maria,
                           ou plusieurs séparés par des virgules), commit et push
    deliver [membre]       messages non lus pour le membre, marqués comme lus
                           (utilisé par le hook team-sync.sh start)
    pending [membre]       idem sans marquer comme lus
    poll [membre]          fetch sans toucher l'arbre, notifie (notify-send) les
                           nouveaux messages pour le membre (utilisé par le cron)
    list                   tous les messages
    whoami                 membre courant

Format d'un message dans messages.md :

    ### yann → tous · 2026-10-11 01:05:00
    texte sur une ou plusieurs lignes

Les curseurs « lu » et « notifié » vivent dans .git/ (par clone, donc par membre),
jamais dans le dépôt. Aucune dépendance hors stdlib.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MEMBERS = ("yann", "mika", "celine", "maria")
HEADER_RE = re.compile(
    r"^### (?P<from>\w+) → (?P<to>[^·]+?) · (?P<at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*$"
)


def sh(*args: str, check: bool = True, **kw) -> str:
    r = subprocess.run(args, capture_output=True, text=True, **kw)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(args)} → {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def repo_root() -> Path:
    return Path(sh("git", "rev-parse", "--show-toplevel").strip())


def git_dir() -> Path:
    return Path(sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir").strip())


def whoami() -> str | None:
    script = repo_root() / "scripts" / "team-sync.sh"
    r = subprocess.run(["bash", str(script), "whoami"], capture_output=True, text=True)
    m = r.stdout.strip()
    return m if r.returncode == 0 and m in MEMBERS else None


@dataclass
class Message:
    sender: str
    to: str
    at: str
    body: str

    @property
    def id(self) -> str:
        return f"{self.at} {self.sender}"

    def is_for(self, member: str) -> bool:
        if self.sender == member:
            return False
        targets = {t.strip().lower() for t in self.to.split(",")}
        return "tous" in targets or "all" in targets or member in targets

    def render(self) -> str:
        return f"📨 {self.sender} → {self.to} · {self.at[:16]}\n{self.body.strip()}"


def parse(text: str) -> list[Message]:
    msgs: list[Message] = []
    cur: Message | None = None
    body: list[str] = []
    for line in text.splitlines():
        m = HEADER_RE.match(line)
        if m:
            if cur:
                cur.body = "\n".join(body)
                msgs.append(cur)
            cur = Message(m["from"].lower(), m["to"].strip(), m["at"], "")
            body = []
        elif cur is not None:
            body.append(line)
    if cur:
        cur.body = "\n".join(body)
        msgs.append(cur)
    return msgs


def read_local() -> list[Message]:
    p = repo_root() / "messages.md"
    return parse(p.read_text(encoding="utf-8")) if p.exists() else []


def read_remote() -> list[Message]:
    sh("git", "fetch", "--quiet", "origin")
    r = subprocess.run(["git", "show", "origin/main:messages.md"], capture_output=True, text=True)
    return parse(r.stdout) if r.returncode == 0 else []


def cursor_path(kind: str, member: str) -> Path:
    return git_dir() / f"finswag-messages-{kind}-{member}"


def load_cursor(kind: str, member: str) -> set[str]:
    p = cursor_path(kind, member)
    return set(p.read_text().splitlines()) if p.exists() else set()


def save_cursor(kind: str, member: str, ids: set[str]) -> None:
    cursor_path(kind, member).write_text("\n".join(sorted(ids)) + "\n")


def unseen(msgs: list[Message], kind: str, member: str) -> list[Message]:
    seen = load_cursor(kind, member)
    return [m for m in msgs if m.is_for(member) and m.id not in seen]


def resolve_member(argv: list[str], idx: int) -> str:
    member = argv[idx].lower() if len(argv) > idx else whoami()
    if member not in MEMBERS:
        sys.exit("membre inconnu : passe-le en argument ou fais git config finswag.member <yann|mika|celine|maria>")
    return member


# ---------------------------------------------------------------- commandes

def cmd_send(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("usage: messages.py send <to> <texte>")
    to, text = argv[0].strip().lower(), " ".join(argv[1:]).strip()
    for t in to.split(","):
        if t.strip() not in MEMBERS + ("tous", "all"):
            sys.exit(f"destinataire inconnu : {t} (tous|{'|'.join(MEMBERS)})")
    sender = whoami()
    if not sender:
        sys.exit("expéditeur inconnu : git config finswag.member <yann|mika|celine|maria>")
    root = repo_root()
    p = root / "messages.md"
    at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n### {sender} → {to} · {at}\n{text}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(entry)
    # commit + rebase + push, sans toucher aux autres fichiers modifiés
    sh("git", "add", "messages.md")
    sh("git", "commit", "-q", "-m", f"{sender}: message → {to}")
    for _ in range(3):
        subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], capture_output=True)
        if subprocess.run(["git", "push", "-q"], capture_output=True).returncode == 0:
            print(f"envoyé à {to} ({at})")
            return
    sys.exit("commit local créé mais push échoué — le hook réessaiera au prochain tour")


def cmd_deliver(argv: list[str], mark: bool) -> None:
    member = resolve_member(argv, 0)
    new = unseen(read_local(), "seen", member)
    if not new:
        return
    print("\n\n".join(m.render() for m in new))
    if mark:
        save_cursor("seen", member, load_cursor("seen", member) | {m.id for m in new})


def notify(title: str, body: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "firebreak", "-i", "mail-unread", title, body])
    elif shutil.which("osascript"):
        subprocess.run(["osascript", "-e", f'display notification "{body}" with title "{title}"'])


def cmd_poll(argv: list[str]) -> None:
    member = resolve_member(argv, 0)
    try:
        msgs = read_remote()
    except RuntimeError:
        return  # pas de réseau : on réessaie à la prochaine minute
    new = unseen(msgs, "notified", member)
    for m in new:
        notify(f"📨 firebreak · {m.sender} → {m.to}", m.body.strip()[:400])
        print(m.render())
    if new:
        save_cursor("notified", member, load_cursor("notified", member) | {m.id for m in new})


def cmd_list() -> None:
    for m in read_local():
        print(m.render(), end="\n\n")


def main() -> None:
    cmd, argv = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    os.chdir(repo_root())
    if cmd == "send":
        cmd_send(argv)
    elif cmd == "deliver":
        cmd_deliver(argv, mark=True)
    elif cmd == "pending":
        cmd_deliver(argv, mark=False)
    elif cmd == "poll":
        cmd_poll(argv)
    elif cmd == "list":
        cmd_list()
    elif cmd == "whoami":
        print(whoami() or "", end="")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
