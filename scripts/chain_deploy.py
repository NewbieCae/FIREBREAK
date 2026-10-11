"""Déploie FirebreakRegistry sur la L1 et enregistre les 4 entreprises.

Lit `.env.local` (RPC, chainId, mnémonique, FIREBREAK_KEY_SEED). N'affiche ni
le mnémonique ni aucune clé privée. Écrit contracts/deployments/l1.json
(adresses publiques uniquement, fichier versionné).

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
    """Clés publiques de la fédération, pour le même FIREBREAK_KEY_SEED que le serveur."""
    if require_seed and not os.environ.get("FIREBREAK_KEY_SEED"):
        raise DeployError(
            "FIREBREAK_KEY_SEED n'est pas défini dans .env.local : sans lui, les clés Ed25519 "
            "changent à chaque lancement du serveur et ne correspondraient plus à celles "
            "enregistrées on-chain (voir docs/avalanche/tasks/00-setup.md)."
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
        raise DeployError("l'admin n'est pas autorisé à déployer (ContractDeployerAllowList)")
    role = allowlist_role(w3, TX_ALLOWLIST, admin.address)
    if role is None:
        log("· TxAllowList non activé sur cette L1 : étape sautée")
        return
    if role < 2:
        raise DeployError("TxAllowList activé mais l'admin n'en est pas admin/manager")
    allow = w3.eth.contract(address=w3.to_checksum_address(TX_ALLOWLIST), abi=ALLOWLIST_ABI)
    for cid in COMPANIES:
        addr = accounts[cid].address
        if allowlist_role(w3, TX_ALLOWLIST, addr) == 0:
            transact(w3, admin, allow.functions.setEnabled(addr))
            log(f"✓ TxAllowList : {cid} activé")


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
        raise DeployError(f"chainId attendu {expected_chain_id}, la L1 répond {chain_id}")
    if chain_id in MAINNET_CHAIN_IDS:
        raise DeployError(f"chainId {chain_id} = réseau principal : refusé")
    admin = accounts["admin"]
    if w3.eth.get_balance(admin.address) == 0:
        raise DeployError(f"le compte admin {admin.address} n'a aucun jeton")

    if not skip_allowlist:
        setup_allowlist(w3, admin, accounts, log)
    if min_balance_wei:
        for cid in fund_accounts(w3, admin, accounts, min_balance_wei):
            log(f"✓ {cid} financé")

    contract = None
    deploy_block = deploy_tx = None
    if reuse and out_path.exists():
        previous = json.loads(out_path.read_text(encoding="utf-8"))
        if previous.get("chainId") == chain_id and w3.eth.get_code(w3.to_checksum_address(previous["address"])):
            contract = registry_contract(w3, previous["address"])
            deploy_block, deploy_tx = previous.get("deployBlock"), previous.get("deployTx")
            log(f"· contrat existant réutilisé : {contract.address}")
    if contract is None:
        contract = deploy_registry(w3, admin)
        receipt = contract.deploy_receipt
        deploy_block = receipt["blockNumber"]
        deploy_tx = "0x" + bytes(receipt["transactionHash"]).hex().removeprefix("0x")
        log(f"✓ FirebreakRegistry déployé : {contract.address} (bloc {deploy_block})")

    register_members(w3, contract, admin, accounts, pubkeys)
    log("✓ membres enregistrés : " + ", ".join(COMPANIES))

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
    parser.add_argument("--reuse", action="store_true", help="réutiliser le contrat déjà déployé s'il est valide")
    parser.add_argument("--skip-allowlist", action="store_true")
    parser.add_argument("--min-balance", type=float, default=0.5,
                        help="solde minimal (jeton natif) des comptes d'entreprise, complété depuis l'admin")
    args = parser.parse_args(argv)

    cfg = load_chain_config()
    missing = [name for name, value in (
        ("FIREBREAK_CHAIN_RPC_URL", cfg.rpc_url),
        ("FIREBREAK_CHAIN_ID", cfg.chain_id),
        ("FIREBREAK_CHAIN_MNEMONIC", cfg.mnemonic),
    ) if not value]
    if missing:
        print("✗ variables manquantes dans .env.local : " + ", ".join(missing))
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

    print(f"→ {cfg.deployment_path.relative_to(ROOT)} écrit")
    for label, link in (("contrat", explorer_address_link(cfg, dep["address"])),
                        ("déploiement", explorer_tx_link(cfg, dep["deployTx"] or ""))):
        if link:
            print(f"  {label} : {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
