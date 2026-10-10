"""Comptes EVM dérivés du mnémonique : admin + une entreprise par compte.

Importe `eth_account` : à n'utiliser que si la chaîne est active.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eth_account import Account

from .config import COMPANIES

if TYPE_CHECKING:
    from eth_account.signers.local import LocalAccount

# Mnémonique public de Hardhat / Foundry : tests et mode « tester » uniquement.
TEST_MNEMONIC = "test test test test test test test test test test test junk"
ROLES = ("admin", *COMPANIES)

Account.enable_unaudited_hdwallet_features()


def derive_accounts(mnemonic: str) -> dict[str, LocalAccount]:
    """Chemin m/44'/60'/0'/0/i : i = 0 admin, 1..4 dans l'ordre de COMPANIES."""
    if not mnemonic or not mnemonic.strip():
        raise ValueError("mnémonique absent (FIREBREAK_CHAIN_MNEMONIC)")
    return {
        role: Account.from_mnemonic(mnemonic.strip(), account_path=f"m/44'/60'/0'/0/{i}")
        for i, role in enumerate(ROLES)
    }


def public_addresses(accounts: dict[str, LocalAccount]) -> dict[str, str]:
    """Seules les adresses publiques sortent d'ici (affichage, déploiement)."""
    return {role: acct.address for role, acct in accounts.items()}
