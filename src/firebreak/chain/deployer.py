"""Deploying FirebreakRegistry and registering the members.

Shared by scripts/chain_deploy.py, the tests and the client's "tester"
mode. Every transaction is signed locally (accounts derived from the
mnemonic): same code on the in-memory EVM and on the real L1.
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

# Subnet-EVM precompiles (fixed addresses). readAllowList: 0 none, 1 enabled, 2 admin, 3 manager.
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


RECEIPT_POLL_SECONDS = 1.0  # web3 polls every 0.1 s by default: too much for a managed node
_EXTRA_RETRY_METHODS = (
    "eth_blockNumber", "eth_getBlockByNumber", "eth_gasPrice", "eth_maxPriorityFeePerGas",
    "eth_getBalance", "eth_getCode",
)


def connect(rpc_url: str, timeout: int = 15) -> Web3:
    """HTTP client for a Subnet-EVM L1.

    - The PoA middleware tolerates a block header `extraData` field longer
      than on Ethereum.
    - Builder Hub managed nodes rate-limit (HTTP 429): automatic retry with
      exponential backoff (0.5 s → 16 s). Retrying `eth_sendRawTransaction`
      is safe: same signed transaction, same hash, the node only applies
      it once.
    """
    from requests.exceptions import ConnectionError as RequestsConnectionError
    from requests.exceptions import HTTPError, Timeout
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
    from web3.providers.rpc.utils import REQUEST_RETRY_ALLOWLIST, ExceptionRetryConfiguration

    retry = ExceptionRetryConfiguration(
        errors=(HTTPError, RequestsConnectionError, Timeout),
        retries=6,
        backoff_factor=0.5,
        method_allowlist=list(dict.fromkeys([*REQUEST_RETRY_ALLOWLIST, *_EXTRA_RETRY_METHODS])),
    )
    w3 = Web3(Web3.HTTPProvider(
        rpc_url, request_kwargs={"timeout": timeout}, exception_retry_configuration=retry
    ))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def _chain_id(w3: Web3) -> int:
    cached = getattr(w3, "_firebreak_chain_id", None)
    if cached is None:
        cached = w3.eth.chain_id
        w3._firebreak_chain_id = cached  # type: ignore[attr-defined]
    return cached


def allowlist_role(w3: Web3, precompile: str, address: str) -> int | None:
    """Role of `address` in a Subnet-EVM allowlist; None if the precompile
    is not enabled on the chain (empty reply)."""
    selector = w3.keccak(text="readAllowList(address)")[:4]
    data = selector + bytes(12) + bytes.fromhex(address[2:])
    raw = w3.eth.call({"to": w3.to_checksum_address(precompile), "data": data})
    if not raw:
        return None
    return int.from_bytes(raw[-32:], "big")


def _finalize(w3: Web3, account: LocalAccount, tx: dict[str, Any]) -> dict[str, Any]:
    tx = dict(tx)
    tx.setdefault("from", account.address)
    tx.setdefault("chainId", _chain_id(w3))
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
    """Signs locally, sends, waits for the receipt. Raises TransactionFailed on revert."""
    signed = account.sign_transaction(_finalize(w3, account, tx))
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=timeout, poll_latency=RECEIPT_POLL_SECONDS
    )
    if receipt["status"] != 1:
        raise TransactionFailed(f"transaction {tx_hash.hex()} revert")
    return receipt


def transact(w3: Web3, account: LocalAccount, call, timeout: int = RECEIPT_TIMEOUT):
    """Contract function call (`contract.functions.f(...)`) signed by `account`."""
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
    """Registers each company in COMPANIES (EVM account + Ed25519 key).
    Idempotent: a member already registered identically is not sent again."""
    receipts = []
    for cid in COMPANIES:
        acct = accounts[cid]
        company = ids.company_id(cid)
        pubkey = pubkeys[cid]
        if len(pubkey) != 32:
            raise ValueError(f"Ed25519 key of {cid}: 32 bytes expected")
        current = contract.functions.members(acct.address).call()
        if current[0] == company and current[1] == pubkey and current[2]:
            continue
        receipts.append(transact(w3, admin, contract.functions.registerMember(acct.address, company, pubkey)))
    return receipts


def fund_accounts(
    w3: Web3, funder: LocalAccount, accounts: dict[str, LocalAccount], min_balance_wei: int
) -> list[str]:
    """Tops up company accounts below `min_balance_wei`. Returns the funded roles."""
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
    """In-memory EVM (EthereumTesterProvider): funds the admin and the companies
    from eth-tester's unlocked account, deploys, registers the members."""
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
