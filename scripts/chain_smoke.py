"""Vérification en lecture seule de la L1 configurée dans `.env.local`.

N'envoie aucune transaction. N'affiche ni le mnémonique ni aucune clé privée,
uniquement des adresses publiques.

    uv run python scripts/chain_smoke.py
Code de sortie 0 si tout va bien, 1 sinon.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from firebreak.chain.config import explorer_address_link, load_chain_config  # noqa: E402


def main() -> int:
    cfg = load_chain_config()
    problems: list[str] = []
    print(f"configuration : {cfg!r}")
    if not cfg.rpc_url:
        print("✗ FIREBREAK_CHAIN_RPC_URL manquant (voir docs/avalanche/tasks/00-setup.md)")
        return 1

    from firebreak.chain.deployer import (
        DEPLOYER_ALLOWLIST,
        TX_ALLOWLIST,
        allowlist_role,
        connect,
        registry_contract,
    )

    w3 = connect(cfg.rpc_url)
    try:
        chain_id = w3.eth.chain_id
        block = w3.eth.block_number
    except Exception as exc:  # noqa: BLE001
        print(f"✗ RPC injoignable : {type(exc).__name__}")
        return 1
    print(f"✓ RPC joignable — chainId {chain_id}, dernier bloc {block}")
    if cfg.chain_id is not None and cfg.chain_id != chain_id:
        problems.append(f"chainId attendu {cfg.chain_id}, reçu {chain_id}")

    addresses: dict[str, str] = {}
    if cfg.mnemonic:
        from firebreak.chain.accounts import derive_accounts, public_addresses

        addresses = public_addresses(derive_accounts(cfg.mnemonic))
        for role, addr in addresses.items():
            bal = w3.from_wei(w3.eth.get_balance(addr), "ether")
            print(f"  {role:<13} {addr}  solde {bal:.4f}")
        if w3.eth.get_balance(addresses["admin"]) == 0:
            problems.append("le compte admin (index 0) n'a aucun jeton")
    else:
        print("· FIREBREAK_CHAIN_MNEMONIC absent : comptes non vérifiés")

    probe = addresses.get("admin", "0x" + "00" * 20)
    for name, precompile in (("TxAllowList", TX_ALLOWLIST), ("ContractDeployerAllowList", DEPLOYER_ALLOWLIST)):
        role = allowlist_role(w3, precompile, probe)
        print(f"  {name:<26} {'non activé' if role is None else f'activé (rôle admin={role})'}")

    if cfg.deployment_path.exists():
        dep = json.loads(cfg.deployment_path.read_text(encoding="utf-8"))
        code = w3.eth.get_code(w3.to_checksum_address(dep["address"]))
        if dep.get("chainId") != chain_id:
            problems.append(f"déploiement pour chainId {dep.get('chainId')}, pas {chain_id}")
        elif not code:
            problems.append(f"aucun code à l'adresse du contrat {dep['address']}")
        else:
            contract = registry_contract(w3, dep["address"])
            print(f"✓ FirebreakRegistry {dep['address']} — admin {contract.functions.admin().call()}")
            link = explorer_address_link(cfg, dep["address"])
            if link:
                print(f"  {link}")
    else:
        print(f"· pas encore de déploiement ({cfg.deployment_path.relative_to(ROOT)})")

    for p in problems:
        print(f"✗ {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
