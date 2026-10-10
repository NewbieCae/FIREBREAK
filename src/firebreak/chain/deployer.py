"""Déploiement de FirebreakRegistry et enregistrement des membres.

Partagé par scripts/chain_deploy.py, les tests et le mode « tester » du
client. Toutes les transactions sont signées localement (comptes dérivés du
mnémonique) : même code sur l'EVM en mémoire et sur la vraie L1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import ids
from .artifact import load_artifact
from .config import COMPANIES

if TYPE_CHECKING:
    from eth_account.signers.local import LocalAccount
    from web3 import Web3
    from web3.contract import Contract

RECEIPT_TIMEOUT = 60

# Precompiles Subnet-EVM (adresses fixes). readAllowList : 0 aucun, 1 enabled, 2 admin, 3 manager.
TX_ALLOWLIST = "0x0200000000000000000000000000000000000002"
DEPLOYER_ALLOWLIST = "0x0200000000000000000000000000000000000000"
ALLOWLIST_ABI = [
    {"type": "function", "name": "readAllowList", "stateMutability": "view",
     "inputs": [{"name": "addr", "type": "address"}], "outputs": [{"name": "role", "type": "uint256"}]},
    {"type": "function", "name": "setEnabled", "stateMutability": "nonpayable",
     "inputs": [{"name": "addr", "type": "address"}], "outputs": []},
]


class TransactionFailed(RuntimeError):
    pass


def connect(rpc_url: str, timeout: int = 15) -> Web3:
    """Client HTTP vers une L1 Subnet-EVM. Le middleware PoA tolère un champ
    `extraData` d'en-tête de bloc plus long que sur Ethereum."""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout}))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def allowlist_role(w3: Web3, precompile: str, address: str) -> int | None:
    """Rôle de `address` dans une allowlist Subnet-EVM ; None si le precompile
    n'est pas activé sur la chaîne (réponse vide)."""
    selector = w3.keccak(text="readAllowList(address)")[:4]
    data = selector + bytes(12) + bytes.fromhex(address[2:])
    raw = w3.eth.call({"to": w3.to_checksum_address(precompile), "data": data})
    if not raw:
        return None
    return int.from_bytes(raw[-32:], "big")


def _finalize(w3: Web3, account: LocalAccount, tx: dict[str, Any]) -> dict[str, Any]:
    tx = dict(tx)
    tx.setdefault("from", account.address)
    tx.setdefault("chainId", w3.eth.chain_id)
    tx.setdefault("nonce", w3.eth.get_transaction_count(account.address, "pending"))
    if "gasPrice" not in tx and "maxFeePerGas" not in tx:
        base = w3.eth.get_block("latest").get("baseFeePerGas")
        if base is None:
            tx["gasPrice"] = w3.eth.gas_price
        else:
            tip = w3.eth.max_priority_fee if hasattr(w3.eth, "max_priority_fee") else 0
            tx["maxPriorityFeePerGas"] = tip
            tx["maxFeePerGas"] = 2 * base + tip
    if "gas" not in tx:
        tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2) + 10_000
    return tx


def send_signed(w3: Web3, account: LocalAccount, tx: dict[str, Any], timeout: int = RECEIPT_TIMEOUT):
    """Signe localement, envoie, attend le reçu. Lève TransactionFailed si revert."""
    signed = account.sign_transaction(_finalize(w3, account, tx))
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
    if receipt["status"] != 1:
        raise TransactionFailed(f"transaction {tx_hash.hex()} revert")
    return receipt


def transact(w3: Web3, account: LocalAccount, call, timeout: int = RECEIPT_TIMEOUT):
    """Appel d'une fonction de contrat (`contract.functions.f(...)`) signé par `account`."""
    return send_signed(w3, account, call.build_transaction({"from": account.address}), timeout)


def send_value(w3: Web3, sender: LocalAccount, to: str, value_wei: int):
    return send_signed(w3, sender, {"to": to, "value": value_wei, "gas": 21_000})


def registry_contract(w3: Web3, address: str) -> Contract:
    return w3.eth.contract(address=w3.to_checksum_address(address), abi=load_artifact()["abi"])


def deploy_registry(w3: Web3, admin: LocalAccount) -> Contract:
    artifact = load_artifact()
    factory = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    receipt = send_signed(w3, admin, factory.constructor().build_transaction({"from": admin.address}))
    contract = registry_contract(w3, receipt["contractAddress"])
    contract.deploy_receipt = receipt  # type: ignore[attr-defined]
    return contract


def register_members(
    w3: Web3,
    contract: Contract,
    admin: LocalAccount,
    accounts: dict[str, LocalAccount],
    pubkeys: dict[str, bytes],
) -> list:
    """Enregistre chaque entreprise de COMPANIES (compte EVM + clé Ed25519).
    Idempotent : un membre déjà enregistré à l'identique n'est pas renvoyé."""
    receipts = []
    for cid in COMPANIES:
        acct = accounts[cid]
        company = ids.company_id(cid)
        pubkey = pubkeys[cid]
        if len(pubkey) != 32:
            raise ValueError(f"clé Ed25519 de {cid} : 32 octets attendus")
        current = contract.functions.members(acct.address).call()
        if current[0] == company and current[1] == pubkey and current[2]:
            continue
        receipts.append(transact(w3, admin, contract.functions.registerMember(acct.address, company, pubkey)))
    return receipts


def fund_accounts(
    w3: Web3, funder: LocalAccount, accounts: dict[str, LocalAccount], min_balance_wei: int
) -> list[str]:
    """Complète le solde des comptes d'entreprise sous `min_balance_wei`. Renvoie les rôles financés."""
    funded = []
    for cid in COMPANIES:
        addr = accounts[cid].address
        balance = w3.eth.get_balance(addr)
        if balance < min_balance_wei:
            send_value(w3, funder, addr, min_balance_wei - balance)
            funded.append(cid)
    return funded


def ensure_tester_registry(
    w3: Web3, accounts: dict[str, LocalAccount], pubkeys: dict[str, bytes]
) -> Contract:
    """EVM en mémoire (EthereumTesterProvider) : finance l'admin et les entreprises
    depuis le compte déverrouillé de eth-tester, déploie, enregistre les membres."""
    rich = w3.eth.accounts[0]
    amount = w3.to_wei(10, "ether")
    for role in ("admin", *COMPANIES):
        addr = accounts[role].address
        if w3.eth.get_balance(addr) < amount // 2:
            tx_hash = w3.eth.send_transaction({"from": rich, "to": addr, "value": amount})
            w3.eth.wait_for_transaction_receipt(tx_hash)
    contract = deploy_registry(w3, accounts["admin"])
    register_members(w3, contract, accounts["admin"], accounts, pubkeys)
    return contract
