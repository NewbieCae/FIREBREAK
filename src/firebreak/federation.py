"""Fédération Firebreak : jetons opaques et alertes signées Ed25519.

- Quand A envoie une donnée à B, le record reçu côté B porte un
  `token = HMAC-SHA256(pair_secret, "{A}:{B}:{record_id_A}")`. B ne connaît
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
- Dans l'autre sens, B peut envoyer à A un **signalement qualité** signé
  (`QualityReport`) : « les données que tu m'as envoyées (ces jetons) sont
  mises en cause ». Il ne met rien en quarantaine chez A : A retrouve ses
  propres records à partir des jetons, et un humain décide (cas par cas).
  Seul l'émetteur d'un jeton peut le résoudre : B n'apprend rien de plus.
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

# Secrets de processus. Aucun secret n'est écrit dans le code : sans variable
# d'environnement, un secret aléatoire est tiré une fois par processus (stable
# pendant toute la durée du processus, différent à chaque lancement). Pour un
# comportement reproductible (démo, tests), définir FIREBREAK_PAIR_SECRET et
# FIREBREAK_KEY_SEED dans `.env.local` (ignoré par Git), jamais dans le dépôt.
_PROCESS_SECRETS: dict[str, bytes] = {}


def _secret(name: str) -> bytes:
    value = _PROCESS_SECRETS.get(name)
    if value is None:
        env = os.environ.get(name)
        value = env.encode() if env else secrets.token_bytes(32)
        _PROCESS_SECRETS[name] = value
    return value


AlertType = Literal["taint", "release"]
REASONS = {"taint": "source compromise", "release": "donnée de nouveau saine"}


def make_token(sender: str, recipient: str, record_id: str) -> str:
    """Jeton opaque : HMAC-SHA256 avec un secret que le code ne contient pas."""
    return hmac.new(
        _secret("FIREBREAK_PAIR_SECRET"),
        f"{sender}:{recipient}:{record_id}".encode(),
        hashlib.sha256,
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
            # Clé dérivée d'un secret de processus, jamais du seul nom de l'entreprise.
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

    # -- signalements qualité vers l'amont ----------------------------------

    def make_report(self, sender: str, recipient: str, tokens: list[str], reason: str,
                    issued_at: datetime) -> QualityReport:
        """Signalement signé par `sender` (le client) à l'émetteur des jetons."""
        self._report_counter += 1
        report = QualityReport(
            id=f"QR-{self._report_counter:03d}", sender=sender, recipient=recipient,
            tokens=sorted(tokens), reason=reason, issued_at=issued_at,
        )
        report.signature = self._priv[sender].sign(_canonical(report.payload())).hex()
        self.reports.append(report)
        return report

    def receive_report(self, report: QualityReport) -> list[str]:
        """Côté destinataire : vérifie la signature, puis résout les jetons en
        ses propres records (seul l'émetteur d'un jeton sait le faire).
        Renvoie les ids de records ; [] si la signature est invalide."""
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
    """Signalement qualité vers l'amont : jetons opaques + motif, signé."""

    id: str
    sender: str
    recipient: str
    tokens: list[str]
    reason: str
    issued_at: datetime
    signature: str = ""
    verified: bool | None = None
    records: list[str] = field(default_factory=list)  # résolus chez le destinataire
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
