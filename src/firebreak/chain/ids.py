"""Identifiers and fingerprints anchored on-chain. Pure functions, no `web3`.

Nothing commercial leaves this module: only 32-byte sha256 digests.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..federation import Alert

ALERT_TYPE = {"taint": 0, "release": 1}


def company_id(cid: str) -> bytes:
    return hashlib.sha256(b"firebreak:company:" + cid.encode()).digest()


def new_run_id() -> bytes:
    return secrets.token_bytes(32)


def canonical_json(payload: dict) -> bytes:
    """Same canonicalization as federation._canonical (tested in test_chain_ids)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def alert_hash(alert: Alert) -> bytes:
    """Fingerprint of the alert as signed: canonical payload + signature."""
    return hashlib.sha256(
        canonical_json(alert.payload()) + b"|" + alert.signature.encode()
    ).digest()


def declaration_hash(company: str, since_iso: str, declarer: str) -> bytes:
    return hashlib.sha256(
        f"firebreak:declaration:{company}|{since_iso}|{declarer}".encode()
    ).digest()


def hex32(b: bytes) -> str:
    if len(b) != 32:
        raise ValueError(f"32 bytes expected, {len(b)} received")
    return "0x" + b.hex()


def from_hex32(value: str) -> bytes:
    raw = bytes.fromhex(value[2:] if value.startswith("0x") else value)
    if len(raw) != 32:
        raise ValueError(f"32 bytes expected, {len(raw)} received")
    return raw
