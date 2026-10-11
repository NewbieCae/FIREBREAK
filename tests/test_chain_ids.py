"""Configuration, identifiers and accounts of the chain layer (no network)."""

import subprocess
import sys
from datetime import datetime

import pytest

from firebreak.chain import ids
from firebreak.chain.config import (
    COMPANIES,
    DEFAULT_DEPLOYMENT,
    REPO_ROOT,
    explorer_tx_link,
    load_chain_config,
    parse_dotenv,
)
from firebreak.federation import Alert, Federation, _canonical


def test_default_mode_is_off():
    cfg = load_chain_config(env={})
    assert cfg.mode == "off" and not cfg.enabled
    assert cfg.deployment_path == DEFAULT_DEPLOYMENT


def test_unknown_mode_falls_back_to_off():
    with pytest.warns(UserWarning):
        assert load_chain_config(env={"FIREBREAK_CHAIN": "mainnet"}).mode == "off"


def test_full_config_and_relative_deployment():
    cfg = load_chain_config(env={
        "FIREBREAK_CHAIN": "L1",
        "FIREBREAK_CHAIN_RPC_URL": "https://rpc.example/ext/bc/x/rpc",
        "FIREBREAK_CHAIN_ID": "569712",
        "FIREBREAK_CHAIN_EXPLORER_URL": "https://explorer.example/",
        "FIREBREAK_CHAIN_DEPLOYMENT": "contracts/deployments/other.json",
    })
    assert cfg.mode == "l1"
    assert cfg.chain_id == 569712
    assert cfg.deployment_path == REPO_ROOT / "contracts/deployments/other.json"
    assert explorer_tx_link(cfg, "abc") == "https://explorer.example/tx/0xabc"
    assert explorer_tx_link(load_chain_config(env={}), "0xabc") is None


def test_dotenv_does_not_override_environment(tmp_path):
    dotenv = tmp_path / ".env.local"
    dotenv.write_text(
        "# comment\nFIREBREAK_CHAIN=tester\nexport FIREBREAK_CHAIN_ID='43113'\n"
        "FIREBREAK_CHAIN_EXPLORER_URL=\"https://e.example\"\n",
        encoding="utf-8",
    )
    assert parse_dotenv(dotenv)["FIREBREAK_CHAIN_ID"] == "43113"
    cfg = load_chain_config(env={"FIREBREAK_CHAIN": "off"}, dotenv_path=dotenv)
    assert cfg.mode == "off"  # the environment wins
    assert cfg.chain_id == 43113 and cfg.explorer_url == "https://e.example"


def test_missing_dotenv_is_ignored(tmp_path):
    assert parse_dotenv(tmp_path / "absent") == {}


def test_repr_masks_mnemonic():
    secret = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima"
    cfg = load_chain_config(env={"FIREBREAK_CHAIN_MNEMONIC": secret})
    assert cfg.mnemonic == secret
    assert "alpha" not in repr(cfg) and "***" in repr(cfg)


def test_company_id_stable_and_distinct():
    a = ids.company_id("fournisseur")
    assert len(a) == 32 and a == ids.company_id("fournisseur")
    assert len({ids.company_id(c) for c in COMPANIES}) == len(COMPANIES)


def test_run_ids_are_random():
    assert ids.new_run_id() != ids.new_run_id()


def test_canonical_json_matches_federation():
    payload = {"type": "taint", "to": "b", "from": "a", "tokens": ["y", "x"], "é": 1}
    assert ids.canonical_json(payload) == _canonical(payload)


def _signed_alert() -> Alert:
    fed = Federation(list(COMPANIES))
    alert = Alert("fournisseur", "fabricant", ["t1", "t2"], "source compromise",
                  datetime(2026, 10, 11, 14, 5))
    alert.signature = fed._priv["fournisseur"].sign(_canonical(alert.payload())).hex()
    return alert


def test_alert_hash_depends_on_payload_and_signature():
    alert = _signed_alert()
    h = ids.alert_hash(alert)
    assert len(h) == 32 and h == ids.alert_hash(alert)
    alert.signature = "00" * 64
    assert ids.alert_hash(alert) != h


def test_declaration_hash_and_hex32_roundtrip():
    h = ids.declaration_hash("fournisseur", "2026-10-11T14:00:00", "fabricant")
    assert ids.from_hex32(ids.hex32(h)) == h
    assert ids.hex32(h).startswith("0x") and len(ids.hex32(h)) == 66
    with pytest.raises(ValueError):
        ids.hex32(b"\x00" * 31)


def test_config_and_ids_do_not_import_web3():
    code = (
        "import sys, firebreak.chain.config, firebreak.chain.ids;"
        "bad=[m for m in ('web3','eth_account') if m in sys.modules];"
        "sys.exit(1 if bad else 0)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_derive_accounts_from_test_mnemonic():
    from firebreak.chain.accounts import ROLES, TEST_MNEMONIC, derive_accounts, public_addresses

    accounts = derive_accounts(TEST_MNEMONIC)
    assert tuple(accounts) == ROLES == ("admin", *COMPANIES)
    # Well-known account 0 of the public Hardhat/Foundry mnemonic.
    assert accounts["admin"].address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    assert len(set(public_addresses(accounts).values())) == len(ROLES)
    with pytest.raises(ValueError):
        derive_accounts("  ")
