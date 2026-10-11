"""EVM accounts derived from the mnemonic: admin + one company per account.

Imports `eth_account`: only use it when the chain is enabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eth_account import Account

from .config import COMPANIES

if TYPE_CHECKING:
    from eth_account.signers.local import LocalAccount

# Public Hardhat / Foundry mnemonic: tests and "tester" mode only.
TEST_MNEMONIC = "test test test test test test test test test test test junk"
ROLES = ("admin", *COMPANIES)

Account.enable_unaudited_hdwallet_features()


def derive_accounts(mnemonic: str) -> dict[str, LocalAccount]:
    """Path m/44'/60'/0'/0/i: i = 0 admin, 1..4 in COMPANIES order."""
    if not mnemonic or not mnemonic.strip():
        raise ValueError("mnemonic missing (FIREBREAK_CHAIN_MNEMONIC)")
    return {
        role: Account.from_mnemonic(mnemonic.strip(), account_path=f"m/44'/60'/0'/0/{i}")
        for i, role in enumerate(ROLES)
    }


def public_addresses(accounts: dict[str, LocalAccount]) -> dict[str, str]:
    """Only public addresses leave this module (display, deployment)."""
    return {role: acct.address for role, acct in accounts.items()}
