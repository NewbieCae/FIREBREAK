"""Fédération Firebreak : jetons opaques et alertes signées Ed25519.

- Quand A envoie une donnée à B, le record reçu côté B porte un
  `token = sha256("{A}:{B}:{record_id_A}:{pair_secret}")`. B ne connaît
  jamais l'identifiant du record de A ; A ne voit jamais les records
  dérivés de B.
- Quand un record sortant de A devient contaminé, A émet UNE alerte par
  destinataire, signée canoniquement. Elle ne contient que des jetons :
  aucune donnée commerciale (payload, prix, libellé).
- B vérifie la signature avec la clé publique de A ; une alerte
  falsifiée est rejetée (`verified: false`) et ne seede rien.
- Quand un record sortant déjà signalé n'est plus contaminé (remédiation,
  retrait d'une déclaration), A émet une alerte `type: "release"`, au même
  format et signée de la même façon. B retire ces jetons de ses seeds,
  recalcule, et lève à son tour vers l'aval. Une release falsifiée est
  rejetée : les jetons restent en quarantaine chez B.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

if TYPE_CHECKING:
    from .engine import Ledger

PAIR_SECRET = "firebreak-demo-pair-secret"

AlertType = Literal["taint", "release"]
REASONS = {"taint": "source compromise", "release": "donnée de nouveau saine"}


def make_token(sender: str, recipient: str, record_id: str) -> str:
    return hashlib.sha256(
        f"{sender}:{recipient}:{record_id}:{PAIR_SECRET}".encode()
    ).hexdigest()


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class Link:
    """Lien d'envoi A -> B : record sortant côté A, copie reçue côté B."""

    sender: str
    sender_record: str
    recipient: str
    recipient_record: str
    token: str


@dataclass
class Alert:
    sender: str
    recipient: str
    tokens: list[str]
    reason: str
    issued_at: datetime
    type: AlertType = "taint"
    signature: str = ""
    verified: bool | None = None

    def payload(self) -> dict:
        return {
            "type": self.type,
            "from": self.sender,
            "to": self.recipient,
            "tokens": sorted(self.tokens),
            "reason": self.reason,
            "issued_at": self.issued_at.isoformat(),
        }


class Federation:
    def __init__(self, company_ids: list[str]) -> None:
        self._priv: dict[str, Ed25519PrivateKey] = {}
        self.public_keys: dict[str, bytes] = {}
        for cid in company_ids:
            seed = hashlib.sha256(f"firebreak-key-{cid}".encode()).digest()
            priv = Ed25519PrivateKey.from_private_bytes(seed)
            self._priv[cid] = priv
            self.public_keys[cid] = priv.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
        self.links: list[Link] = []
        self.alerts: list[Alert] = []
        self._alerted_links: set[tuple[str, str]] = set()
        self._issue_counter = 0

    def register_send(
        self, sender: str, sender_record: str, recipient: str, recipient_record: str
    ) -> str:
        token = make_token(sender, recipient, sender_record)
        self.links.append(Link(sender, sender_record, recipient, recipient_record, token))
        return token

    def verify(self, company: str, payload: dict, signature_hex: str) -> bool:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        key = self.public_keys.get(company)
        if key is None:
            return False
        pub = Ed25519PublicKey.from_public_bytes(key)
        try:
            pub.verify(bytes.fromhex(signature_hex), _canonical(payload))
            return True
        except (InvalidSignature, ValueError):
            return False

    def emit_alerts(self, ledgers: dict[str, Ledger], issued_at: datetime) -> list[Alert]:
        """Une alerte par (expéditeur, destinataire, type) :
        - « taint » pour les records sortants nouvellement contaminés ;
        - « release » pour ceux déjà signalés qui ne le sont plus.
        Ne fuite que des jetons."""
        new_alerts: list[Alert] = []
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for link in self.links:
            key = (link.sender_record, link.recipient_record)
            rec = ledgers[link.sender].records.get(link.sender_record)
            tainted = rec is not None and rec.status == "quarantined"
            alerted = key in self._alerted_links
            if tainted and not alerted:
                kind = "taint"
                self._alerted_links.add(key)
            elif alerted and not tainted:
                kind = "release"
                self._alerted_links.discard(key)
            else:
                continue
            grouped.setdefault((link.sender, link.recipient, kind), []).append(link.token)
        for (sender, recipient, kind), tokens in sorted(grouped.items()):
            self._issue_counter += 1
            alert = Alert(
                sender=sender,
                recipient=recipient,
                tokens=sorted(tokens),
                reason=REASONS[kind],
                issued_at=issued_at,
                type=kind,
            )
            alert.signature = (
                self._priv[sender].sign(_canonical(alert.payload())).hex()
            )
            self.alerts.append(alert)
            new_alerts.append(alert)
        return new_alerts

    def deliver(self, alert: Alert, ledgers: dict[str, Ledger]) -> bool:
        """Remet l'alerte au destinataire. Retourne True si acceptée."""
        ok = alert.recipient in ledgers and self.verify(
            alert.sender, alert.payload(), alert.signature
        )
        alert.verified = ok
        if not ok:
            return False
        if alert.type == "release":
            ledgers[alert.recipient].release_alert_tokens(list(alert.tokens))
        else:
            ledgers[alert.recipient].register_alert_tokens(list(alert.tokens))
        return True
