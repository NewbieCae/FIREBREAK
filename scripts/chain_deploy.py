"""Deploy FirebreakRegistry on the L1 and register the 4 companies.

Reads `.env.local` (RPC, chainId, mnemonic, FIREBREAK_KEY_SEED). Never prints
the mnemonic or any private key. Writes contracts/deployments/l1.json
(public addresses only, committed file).

    uv run python scripts/chain_deploy.py [--reuse] [--skip-allowlist] [--min-balance 0.5]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from firebreak.chain.config import (  # noqa: E402
    COMPANIES,
    explorer_address_link,
    explorer_tx_link,
    load_chain_config,
)

MAINNET_CHAIN_IDS = {1, 43114}


class DeployError(RuntimeError):
    pass


def ed25519_public_keys(require_seed: bool = True) -> dict[str, bytes]:
    """Federation public keys, for the same FIREBREAK_KEY_SEED as the server."""
    if require_seed and not os.environ.get("FIREBREAK_KEY_SEED"):
        raise DeployError(
            "FIREBREAK_KEY_SEED is not set in .env.local: without it, the Ed25519 keys "
            "change on every server start and would no longer match the ones "
            "registered on-chain (see docs/avalanche/tasks/00-setup.md)."
        )
    from firebreak.federation import Federation

    return Federation(list(COMPANIES)).public_keys


def setup_allowlist(w3, admin, accounts, log) -> None:
    from firebreak.chain.deployer import (
        ALLOWLIST_ABI,
        DEPLOYER_ALLOWLIST,
        TX_ALLOWLIST,
        allowlist_role,
        transact,
    )

    deployer_role = allowlist_role(w3, DEPLOYER_ALLOWLIST, admin.address)
    if deployer_role == 0:
        raise DeployError("the admin is not allowed to deploy (ContractDeployerAllowList)")
    role = allowlist_role(w3, TX_ALLOWLIST, admin.address)
    if role is None:
        log("· TxAllowList not enabled on this L1: step skipped")
        return
    if role < 2:
        raise DeployError("TxAllowList enabled but the admin is not its admin/manager")
    allow = w3.eth.contract(address=w3.to_checksum_address(TX_ALLOWLIST), abi=ALLOWLIST_ABI)
    for cid in COMPANIES:
        addr = accounts[cid].address
        if allowlist_role(w3, TX_ALLOWLIST, addr) == 0:
            transact(w3, admin, allow.functions.setEnabled(addr))
            log(f"✓ TxAllowList: {cid} enabled")


def deploy(
    w3,
    accounts: dict,
    pubkeys: dict[str, bytes],
    out_path: Path,
    *,
    expected_chain_id: int | None = None,
    reuse: bool = False,
    skip_allowlist: bool = False,
    min_balance_wei: int = 0,
    log=print,
) -> dict:
    from firebreak.chain.artifact import load_artifact
    from firebreak.chain.deployer import (
        deploy_registry,
        fund_accounts,
        register_members,
        registry_contract,
    )

    chain_id = w3.eth.chain_id
    if expected_chain_id is not None and chain_id != expected_chain_id:
        raise DeployError(f"expected chainId {expected_chain_id}, the L1 answers {chain_id}")
    if chain_id in MAINNET_CHAIN_IDS:
        raise DeployError(f"chainId {chain_id} = mainnet: refused")
    admin = accounts["admin"]
    if w3.eth.get_balance(admin.address) == 0:
        raise DeployError(f"the admin account {admin.address} has no tokens")

    if not skip_allowlist:
        setup_allowlist(w3, admin, accounts, log)
    if min_balance_wei:
        for cid in fund_accounts(w3, admin, accounts, min_balance_wei):
            log(f"✓ {cid} funded")

    contract = None
    deploy_block = deploy_tx = None
    if reuse and out_path.exists():
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        if previous.get("chainId") == chain_id and w3.eth.get_code(w3.to_checksum_address(previous["address"])):
            contract = registry_contract(w3, previous["address"])
            deploy_block, deploy_tx = previous.get("deployBlock"), previous.get("deployTx")
            log(f"· reusing existing contract: {contract.address}")
    if contract is None:
        contract = deploy_registry(w3, admin)
        receipt = contract.deploy_receipt
        deploy_block = receipt["blockNumber"]
        deploy_tx = "0x" + bytes(receipt["transactionHash"]).hex().removeprefix("0x")
        log(f"✓ FirebreakRegistry deployed: {contract.address} (block {deploy_block})")

    register_members(w3, contract, admin, accounts, pubkeys)
    log("✓ members registered: " + ", ".join(COMPANIES))

    artifact = load_artifact()
    deployment = {
        "network": "avalanche-l1",
        "chainId": chain_id,
        "address": contract.address,
        "deployBlock": deploy_block,
        "deployTx": deploy_tx,
        "admin": admin.address,
        "members": {cid: accounts[cid].address for cid in COMPANIES},
        "ed25519PubKeys": {cid: "0x" + pubkeys[cid].hex() for cid in COMPANIES},
        "abiSha256": hashlib.sha256(json.dumps(artifact["abi"], sort_keys=True).encode()).hexdigest(),
        "sourceSha256": artifact["sourceSha256"],
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deployment, indent=2) + "\n", encoding="utf-8")
    return deployment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reuse", action="store_true", help="reuse the already deployed contract if it is valid")
    parser.add_argument("--skip-allowlist", action="store_true")
    parser.add_argument("--min-balance", type=float, default=0.5,
                        help="minimum balance (native token) of the company accounts, topped up from the admin")
    args = parser.parse_args(argv)

    cfg = load_chain_config()
    missing = [name for name, value in (
        ("FIREBREAK_CHAIN_RPC_URL", cfg.rpc_url),
        ("FIREBREAK_CHAIN_ID", cfg.chain_id),
        ("FIREBREAK_CHAIN_MNEMONIC", cfg.mnemonic),
    ) if not value]
    if missing:
        print("✗ missing variables in .env.local: " + ", ".join(missing))
        return 1

    from firebreak.chain.accounts import derive_accounts
    from firebreak.chain.deployer import connect

    try:
        pubkeys = ed25519_public_keys()
        w3 = connect(cfg.rpc_url)
        dep = deploy(
            w3,
            derive_accounts(cfg.mnemonic),
            pubkeys,
            cfg.deployment_path,
            expected_chain_id=cfg.chain_id,
            reuse=args.reuse,
            skip_allowlist=args.skip_allowlist,
            min_balance_wei=w3.to_wei(args.min_balance, "ether"),
        )
    except DeployError as exc:
        print(f"✗ {exc}")
        return 1

    print(f"→ {cfg.deployment_path.relative_to(ROOT)} written")
    for label, link in (("contract", explorer_address_link(cfg, dep["address"])),
                        ("deployment", explorer_tx_link(cfg, dep["deployTx"] or ""))):
        if link:
            print(f"  {label}: {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
