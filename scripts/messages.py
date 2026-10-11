#!/usr/bin/env python3
"""messages.py — team messaging inside the repo (messages.md file).

    send <to> <text>       append a message (to = tous | all | yann | mika | celine | maria,
                           or several separated by commas), commit and push
    deliver [member]       unread messages for the member, marked as read
                           (used by the team-sync.sh start hook)
    pending [member]       same without marking them as read
    poll [member]          fetch without touching the work tree, notify (notify-send)
                           new messages for the member (used by the cron job)
    list                   all messages
    whoami                 current member

Message format in messages.md:

    ### yann → tous · 2026-10-11 01:05:00
    text on one or more lines

The "read" and "notified" cursors live in .git/ (per clone, hence per member),
never in the repo. No dependencies outside the stdlib.
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
        sys.exit("unknown member: pass it as an argument or run git config finswag.member <yann|mika|celine|maria>")
    return member


# ---------------------------------------------------------------- commands

def cmd_send(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("usage: messages.py send <to> <text>")
    to, text = argv[0].strip().lower(), " ".join(argv[1:]).strip()
    for t in to.split(","):
        if t.strip() not in MEMBERS + ("tous", "all"):
            sys.exit(f"unknown recipient: {t} (tous|{'|'.join(MEMBERS)})")
    sender = whoami()
    if not sender:
        sys.exit("unknown sender: git config finswag.member <yann|mika|celine|maria>")
    root = repo_root()
    p = root / "messages.md"
    at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n### {sender} → {to} · {at}\n{text}\n"
    with p.open("a", encoding="utf-8") as f:
        f.write(entry)
    # commit + rebase + push, without touching other modified files
    sh("git", "add", "messages.md")
    sh("git", "commit", "-q", "-m", f"{sender}: message → {to}")
    for _ in range(3):
        subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], capture_output=True)
        if subprocess.run(["git", "push", "-q"], capture_output=True).returncode == 0:
            print(f"sent to {to} ({at})")
            return
    sys.exit("local commit created but push failed — the hook will retry on the next turn")


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
        return  # no network: retry next minute
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
