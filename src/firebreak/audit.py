"""Journal d'audit Firebreak : ajout seul, chaîné par hash.

Chaque entreprise tient son propre journal. Chaque entrée porte le hash
de la précédente (`prev_hash`) et son propre hash :
`hash = sha256(prev_hash + json_canonique(entrée sans "hash"))`.
Modifier, supprimer ou réordonner une entrée casse la chaîne à partir
de cette entrée : `verify()` renvoie l'index de la première entrée cassée.

Limite : la chaîne prouve que le journal n'a pas été modifié par
quelqu'un qui ne recalcule pas tous les hash suivants. Pour s'en
protéger, il faut ancrer le dernier hash (`head`) à l'extérieur.
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
        """Recalcule la chaîne. Renvoie None si intacte, sinon l'index de
        la première entrée cassée."""
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
