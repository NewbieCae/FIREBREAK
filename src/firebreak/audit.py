"""Firebreak audit log: append-only, hash-chained.

Each company keeps its own log. Each entry carries the hash of the
previous one (`prev_hash`) and its own hash:
`hash = sha256(prev_hash + canonical_json(entry without "hash"))`.
Modifying, deleting or reordering an entry breaks the chain from that
entry on: `verify()` returns the index of the first broken entry.

Limitation: the chain proves the log was not modified by someone who
does not recompute all following hashes. To guard against that, the
last hash (`head`) must be anchored externally.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from typing import Literal

Actor = Literal["humain", "règle"]
GENESIS = "0" * 64


def _canonical(body: dict) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode()


def entry_hash(prev_hash: str, body: dict) -> str:
    return hashlib.sha256(prev_hash.encode() + _canonical(body)).hexdigest()


class AuditLog:
    def __init__(self, company_id: str) -> None:
        self.company_id = company_id
        self._entries: list[dict] = []

    @property
    def head(self) -> str:
        return self._entries[-1]["hash"] if self._entries else GENESIS

    def append(self, ts: datetime, event: str, actor: Actor, details: dict) -> dict:
        body = {
            "index": len(self._entries),
            "ts": ts.isoformat(),
            "company": self.company_id,
            "event": event,
            "actor": actor,
            "details": copy.deepcopy(details),
            "prev_hash": self.head,
        }
        entry = {**body, "hash": entry_hash(body["prev_hash"], body)}
        self._entries.append(entry)
        return copy.deepcopy(entry)

    def entries(self) -> list[dict]:
        return copy.deepcopy(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def verify(self) -> int | None:
        """Recomputes the chain. Returns None if intact, otherwise the index
        of the first broken entry."""
        prev = GENESIS
        for i, entry in enumerate(self._entries):
            body = {k: v for k, v in entry.items() if k != "hash"}
            if (
                entry.get("index") != i
                or entry.get("prev_hash") != prev
                or entry.get("hash") != entry_hash(prev, body)
            ):
                return i
            prev = entry["hash"]
        return None
