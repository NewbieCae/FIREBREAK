"""scripts/chain_deploy.py déroulé sur une EVM en mémoire (aucun réseau)."""

import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("eth_tester")

from web3 import EthereumTesterProvider, Web3  # noqa: E402

from firebreak.chain import ids  # noqa: E402
from firebreak.chain.accounts import TEST_MNEMONIC, derive_accounts  # noqa: E402
from firebreak.chain.config import COMPANIES  # noqa: E402
from firebreak.chain.deployer import allowlist_role, registry_contract, TX_ALLOWLIST  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location("chain_deploy", ROOT / "scripts" / "chain_deploy.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def funded_chain():
    w3 = Web3(EthereumTesterProvider())
    accounts = derive_accounts(TEST_MNEMONIC)
    tx = w3.eth.send_transaction({"from": w3.eth.accounts[0], "to": accounts["admin"].address,
                                  "value": w3.to_wei(100, "ether")})
    w3.eth.wait_for_transaction_receipt(tx)
    return w3, accounts


def test_deploy_writes_deployment_and_registers(funded_chain, tmp_path, monkeypatch):
    monkeypatch.setenv("FIREBREAK_KEY_SEED", "seed-de-test")
    script = _load_script()
    w3, accounts = funded_chain
    pubkeys = script.ed25519_public_keys()
    out = tmp_path / "l1.json"
    logs = []
    dep = script.deploy(w3, accounts, pubkeys, out, expected_chain_id=w3.eth.chain_id,
                        min_balance_wei=w3.to_wei(1, "ether"), log=logs.append)

    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved == dep
    assert saved["chainId"] == w3.eth.chain_id and saved["admin"] == accounts["admin"].address
    assert set(saved["members"]) == set(COMPANIES)
    assert "MNEMONIC" not in out.read_text(encoding="utf-8").upper()
    assert any("TxAllowList non activé" in line for line in logs)  # eth-tester n'a pas le precompile
    contract = registry_contract(w3, saved["address"])
    for cid in COMPANIES:
        assert w3.eth.get_balance(accounts[cid].address) >= w3.to_wei(1, "ether")
        company, pubkey, active = contract.functions.members(accounts[cid].address).call()
        assert company == ids.company_id(cid) and pubkey == pubkeys[cid] and active

    # --reuse : même adresse, aucun redéploiement.
    again = script.deploy(w3, accounts, pubkeys, out, reuse=True, log=logs.append)
    assert again["address"] == saved["address"]


def test_refuses_wrong_chain_id_and_unfunded_admin(funded_chain, tmp_path):
    script = _load_script()
    w3, accounts = funded_chain
    with pytest.raises(script.DeployError, match="chainId attendu"):
        script.deploy(w3, accounts, {}, tmp_path / "x.json", expected_chain_id=569712)
    poor = derive_accounts("abandon " * 11 + "about")
    with pytest.raises(script.DeployError, match="aucun jeton"):
        script.deploy(w3, poor, {}, tmp_path / "x.json")


def test_key_seed_required(monkeypatch):
    monkeypatch.delenv("FIREBREAK_KEY_SEED", raising=False)
    script = _load_script()
    with pytest.raises(script.DeployError, match="FIREBREAK_KEY_SEED"):
        script.ed25519_public_keys()


def test_allowlist_probe_on_chain_without_precompile(funded_chain):
    w3, accounts = funded_chain
    assert allowlist_role(w3, TX_ALLOWLIST, accounts["admin"].address) is None
