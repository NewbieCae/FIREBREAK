"""Firebreak federation: opaque tokens and Ed25519-signed alerts.

- When A sends data to B, the record received on B's side carries a
  `token = HMAC-SHA256(pair_secret, "{A}:{B}:{record_id_A}")`. B never knows
  the id of A's record; A never sees B's derived records.
- When an outgoing record of A becomes tainted, A issues ONE alert per
  recipient, canonically signed. It contains only tokens: no business
  data (payload, price, label).
- B checks the signature with A's public key; a forged alert is
  rejected (`verified: false`) and seeds nothing.
- When an already-reported outgoing record is no longer tainted
  (remediation, withdrawn declaration), A issues a `type: "release"` alert,
  in the same format and signed the same way. B removes those tokens from
  its seeds, recomputes, and in turn releases downstream. A forged release
  is rejected: the tokens stay quarantined at B.
- In the other direction, B can send A a signed **quality report**
  (`QualityReport`): "the data you sent me (these tokens) is being
  questioned". It quarantines nothing at A: A finds its own records from
  the tokens, and a human decides (case by case).
  Only the issuer of a token can resolve it: B learns nothing more.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
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

# Process secrets. No secret is written in the code: without an environment
# variable, a random secret is drawn once per process (stable for the whole
# life of the process, different on each launch). For reproducible behavior
# (demo, tests), set FIREBREAK_PAIR_SECRET and FIREBREAK_KEY_SEED in
# `.env.local` (ignored by Git), never in the repo.
_PROCESS_SECRETS: dict[str, bytes] = {}


def _secret(name: str) -> bytes:
    value = _PROCESS_SECRETS.get(name)
    if value is None:
        env = os.environ.get(name)
        value = env.encode() if env else secrets.token_bytes(32)
        _PROCESS_SECRETS[name] = value
    return value


AlertType = Literal["taint", "release"]
REASONS = {"taint": "source compromise", "release": "data clean again"}


def make_token(sender: str, recipient: str, record_id: str) -> str:
    """Opaque token: HMAC-SHA256 with a secret the code does not contain."""
    return hmac.new(
        _secret("FIREBREAK_PAIR_SECRET"),
        f"{sender}:{recipient}:{record_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


@dataclass
class Link:
    """Send link A -> B: outgoing record on A's side, received copy on B's side."""

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
            # Key derived from a process secret, never from the company name alone.
            seed = hmac.new(
                _secret("FIREBREAK_KEY_SEED"), f"ed25519:{cid}".encode(), hashlib.sha256
            ).digest()
            priv = Ed25519PrivateKey.from_private_bytes(seed)
            self._priv[cid] = priv
            self.public_keys[cid] = priv.public_key().public_bytes(
                Encoding.Raw, PublicFormat.Raw
            )
        self.links: list[Link] = []
        self.alerts: list[Alert] = []
        self._alerted_links: set[tuple[str, str]] = set()
        self._issue_counter = 0
        self.reports: list[QualityReport] = []
        self._report_counter = 0

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
        """One alert per (sender, recipient, type):
        - "taint" for newly tainted outgoing records;
        - "release" for already-reported ones that no longer are.
        Leaks only tokens."""
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
        """Delivers the alert to the recipient. Returns True if accepted."""
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

    # -- upstream quality reports -------------------------------------------

    def make_report(self, sender: str, recipient: str, tokens: list[str], reason: str,
                    issued_at: datetime) -> QualityReport:
        """Report signed by `sender` (the customer) to the issuer of the tokens."""
        self._report_counter += 1
        report = QualityReport(
            id=f"QR-{self._report_counter:03d}", sender=sender, recipient=recipient,
            tokens=sorted(tokens), reason=reason, issued_at=issued_at,
        )
        report.signature = self._priv[sender].sign(_canonical(report.payload())).hex()
        self.reports.append(report)
        return report

    def receive_report(self, report: QualityReport) -> list[str]:
        """Recipient side: checks the signature, then resolves the tokens into
        its own records (only the issuer of a token can do that).
        Returns the record ids; [] if the signature is invalid."""
        report.verified = self.verify(report.sender, report.payload(), report.signature)
        if not report.verified:
            report.records = []
            return []
        wanted = set(report.tokens)
        report.records = sorted({
            link.sender_record for link in self.links
            if link.sender == report.recipient and link.recipient == report.sender
            and link.token in wanted
        })
        return report.records


@dataclass
class QualityReport:
    """Upstream quality report: opaque tokens + reason, signed."""

    id: str
    sender: str
    recipient: str
    tokens: list[str]
    reason: str
    issued_at: datetime
    signature: str = ""
    verified: bool | None = None
    records: list[str] = field(default_factory=list)  # resolved at the recipient
    status: str = "pending"  # pending | confirmed | rejected

    def payload(self) -> dict:
        return {
            "type": "report",
            "id": self.id,
            "from": self.sender,
            "to": self.recipient,
            "tokens": sorted(self.tokens),
            "reason": self.reason,
            "issued_at": self.issued_at.isoformat(),
        }
