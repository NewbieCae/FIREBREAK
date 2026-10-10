"""Les secrets de la fédération ne sont ni écrits dans le code ni devinables."""

import hashlib
import json
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from firebreak import federation
from firebreak.engine import Ledger
from firebreak.federation import Federation, make_token
from firebreak.model import Record

NOW = datetime(2026, 10, 10, 15, 0, 0)
SINCE = datetime(2026, 10, 10, 14, 0, 0)


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _legacy_public_key(cid: str) -> bytes:
    """Ancienne dérivation (clé = sha256 du nom) : ne doit plus fonctionner."""
    seed = hashlib.sha256(f"firebreak-key-{cid}".encode()).digest()
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )


def test_public_key_is_not_derivable_from_company_name():
    fed = Federation(["a", "b"])
    assert fed.public_keys["a"] != _legacy_public_key("a")
    assert fed.public_keys["b"] != _legacy_public_key("b")


def test_alert_forged_with_legacy_key_is_rejected():
    fed = Federation(["a", "b"])
    la, lb = Ledger("a"), Ledger("b")
    la.add(Record("a-out", "a", "a", "asn", NOW, "sortant"))
    token = fed.register_send("a", "a-out", "b", "b-recv")
    lb.add(Record("b-recv", "b", "a", "asn", NOW, "reçu", token=token))
    la.declare_compromised("a", SINCE)
    la.recompute()
    alert = fed.emit_alerts({"a": la, "b": lb}, NOW)[0]
    forger = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"firebreak-key-a").digest()
    )
    alert.signature = forger.sign(_canonical(alert.payload())).hex()
    assert fed.deliver(alert, {"a": la, "b": lb}) is False


def test_token_is_not_the_legacy_formula():
    legacy = hashlib.sha256(
        b"a:b:rec-1:firebreak-demo-pair-secret"
    ).hexdigest()
    assert make_token("a", "b", "rec-1") != legacy


def test_token_is_stable_inside_a_process_and_depends_on_inputs():
    assert make_token("a", "b", "rec-1") == make_token("a", "b", "rec-1")
    assert make_token("a", "b", "rec-1") != make_token("a", "b", "rec-2")
    assert make_token("a", "b", "rec-1") != make_token("b", "a", "rec-1")


def test_env_secrets_make_runs_reproducible(monkeypatch):
    monkeypatch.setattr(federation, "_PROCESS_SECRETS", {})
    monkeypatch.setenv("FIREBREAK_PAIR_SECRET", "secret-de-test")
    monkeypatch.setenv("FIREBREAK_KEY_SEED", "graine-de-test")
    t1 = make_token("a", "b", "r")
    k1 = Federation(["a"]).public_keys["a"]
    monkeypatch.setattr(federation, "_PROCESS_SECRETS", {})
    assert make_token("a", "b", "r") == t1
    assert Federation(["a"]).public_keys["a"] == k1


def test_no_hardcoded_secret_left_in_source():
    source = open(federation.__file__, encoding="utf-8").read()
    assert "firebreak-demo-pair-secret" not in source
    assert "firebreak-key-" not in source
