"""Client chaîne : file d'attente + thread d'envoi. Jamais bloquant.

`NullChain` (mode off) n'importe pas web3. `Web3Chain` (modes tester et l1)
signe chaque transaction avec le compte de l'entreprise émettrice.
"""

from __future__ import annotations

import itertools
import queue
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .config import ChainConfig, explorer_tx_link
from .ids import company_id

RECEIPT_TIMEOUT = 20
ATTEMPTS = 4
RETRY_BACKOFF = 1.0
READ_RETRIES = 3
READ_RETRY_DELAY = 1.0


@dataclass
class ChainOp:
    kind: str  # audit | alert | incident | ack
    company: str  # entreprise qui signe la transaction
    fn: str  # nom de la fonction du contrat
    args: tuple = ()
    hash: str = ""  # hex de ce qu'on ancre


@dataclass
class AnchorRecord:
    id: int
    kind: str
    company: str
    hash: str
    status: str = "pending"  # pending | sent | confirmed | failed | disabled
    tx_hash: str | None = None
    block: int | None = None
    error: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    explorer_link: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ChainClient(Protocol):
    def submit(self, op: ChainOp) -> AnchorRecord: ...
    def anchors(self) -> list[AnchorRecord]: ...
    def status(self) -> dict: ...
    def read_audit_anchor(self, run_id: bytes, company: str) -> dict | None: ...
    def flush(self, timeout: float = 5.0) -> None: ...


def _queue_counts(records: list[AnchorRecord]) -> dict:
    counts = {"pending": 0, "sent": 0, "confirmed": 0, "failed": 0}
    for r in records:
        if r.status in counts:
            counts[r.status] += 1
    return counts


class NullChain:
    """Mode off : aucune écriture, aucun import réseau."""

    def __init__(self, config: ChainConfig | None = None) -> None:
        self._ids = itertools.count(1)

    def submit(self, op: ChainOp) -> AnchorRecord:
        return AnchorRecord(next(self._ids), op.kind, op.company, op.hash,
                            status="disabled")

    def anchors(self) -> list[AnchorRecord]:
        return []

    def status(self) -> dict:
        return {"mode": "off", "connected": False, "chain_id": None,
                "contract": None, "explorer_url": None, "last_block": None,
                "queue": _queue_counts([])}

    def read_audit_anchor(self, run_id: bytes, company: str) -> dict | None:
        return None

    def flush(self, timeout: float = 5.0) -> None:
        return None


class Web3Chain:
    """Modes tester (EVM en mémoire) et l1 (vraie L1)."""

    def __init__(self, config: ChainConfig, w3: Any = None, contract: Any = None,
                 accounts: dict | None = None, error: str | None = None) -> None:
        self.config = config
        self.w3 = w3
        self.contract = contract
        self.accounts = accounts or {}
        self.error = error
        self.connected = contract is not None and error is None
        self.chain_id = int(w3.eth.chain_id) if self.connected else None
        self._records: list[AnchorRecord] = []
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._queue: queue.Queue = queue.Queue()
        if self.connected:
            threading.Thread(target=self._worker, daemon=True,
                             name="chain-sender").start()

    def submit(self, op: ChainOp) -> AnchorRecord:
        rec = AnchorRecord(next(self._ids), op.kind, op.company, op.hash)
        with self._lock:
            self._records.append(rec)
        if not self.connected:
            self._fail(rec, self.error or "chaîne injoignable")
            return rec
        self._queue.put((op, rec))
        return rec

    def anchors(self) -> list[AnchorRecord]:
        with self._lock:
            return [AnchorRecord(**r.to_dict()) for r in self._records]

    def status(self) -> dict:
        with self._lock:
            counts = _queue_counts(self._records)
            last_block = max((r.block for r in self._records if r.block), default=None)
        return {
            "mode": self.config.mode,
            "connected": self.connected,
            "chain_id": self.chain_id,
            "contract": getattr(self.contract, "address", None),
            "explorer_url": self.config.explorer_url,
            "last_block": last_block,
            "queue": counts,
        }

    def read_audit_anchor(self, run_id: bytes, company: str) -> dict | None:
        if not self.connected:
            return None
        rec = None
        with self._lock:
            for r in reversed(self._records):
                if (r.kind == "audit" and r.company == company
                        and r.status == "confirmed"):
                    rec = r
                    break
        # Un nœud en retard peut renvoyer 0 entrée juste après la confirmation.
        attempts = 1 + (READ_RETRIES if rec else 0)
        head, entries = b"", 0
        for i in range(attempts):
            if i:
                time.sleep(READ_RETRY_DELAY)
            try:
                head, entries, _ = self.contract.functions.latestAudit(
                    run_id, company_id(company)).call()
            except Exception:
                entries = 0
                continue
            if entries:
                break
        if not entries:
            return {"unreadable": True} if rec else None
        return {
            "anchored_head": bytes(head).hex(),
            "anchored_entries": int(entries),
            "block": rec.block if rec else None,
            "tx_hash": rec.tx_hash if rec else None,
            "explorer_link": rec.explorer_link if rec else None,
        }

    def flush(self, timeout: float = 5.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return
            time.sleep(0.01)

    def _fail(self, rec: AnchorRecord, error: str) -> None:
        with self._lock:
            rec.status = "failed"
            rec.error = error[:200]

    def _worker(self) -> None:
        while True:
            op, rec = self._queue.get()
            try:
                self._send(op, rec)
            except Exception as exc:  # le worker ne doit jamais mourir
                self._fail(rec, f"{type(exc).__name__}: {exc}")
            finally:
                self._queue.task_done()

    def _send(self, op: ChainOp, rec: AnchorRecord) -> None:
        from .deployer import RECEIPT_POLL_SECONDS

        acct = self.accounts.get(op.company)
        if acct is None:
            raise ValueError(f"compte inconnu : {op.company}")
        last_error = "erreur inconnue"
        if op.fn == "acknowledgeAlert" and not self._alert_anchored(op.args[0]):
            self._fail(rec, "alerte non ancrée : accusé impossible")
            return
        tx_hash = None
        hex_hash = None
        for attempt in range(ATTEMPTS):
            if attempt:
                time.sleep(RETRY_BACKOFF * 2 ** (attempt - 1))
            try:
                if tx_hash is None:
                    tx = getattr(self.contract.functions, op.fn)(*op.args).build_transaction({
                        "from": acct.address,
                        "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
                        "chainId": self.chain_id,
                        "gasPrice": self.w3.eth.gas_price,
                    })
                    signed = acct.sign_transaction(tx)
                    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
                    tx_hash = self.w3.eth.send_raw_transaction(raw)
                    hex_hash = tx_hash.hex()
                    if not hex_hash.startswith("0x"):
                        hex_hash = "0x" + hex_hash
                    with self._lock:
                        rec.status = "sent"
                        rec.tx_hash = hex_hash
                # Une transaction déjà envoyée n'est jamais renvoyée : on réinterroge son reçu.
                receipt = self.w3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=RECEIPT_TIMEOUT,
                    poll_latency=RECEIPT_POLL_SECONDS)
                with self._lock:
                    if receipt["status"] == 1:
                        rec.status = "confirmed"
                        rec.block = int(receipt["blockNumber"])
                        rec.explorer_link = explorer_tx_link(self.config, hex_hash)
                        return
                last_error = "transaction rejetée par le contrat"
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        self._fail(rec, last_error)

    def _alert_anchored(self, alert_hash: bytes) -> bool:
        try:
            return int(self.contract.functions.alerts(alert_hash).call()[3]) != 0
        except Exception:
            return True  # lecture impossible : on laisse le contrat trancher


def get_chain_client(config: ChainConfig) -> ChainClient:
    if config.mode == "off":
        return NullChain(config)
    try:
        return _build_web3_chain(config)
    except Exception as exc:
        return Web3Chain(config, error=f"{type(exc).__name__}: {exc}")


def _build_web3_chain(config: ChainConfig) -> Web3Chain:
    from web3 import Web3

    from ..federation import Federation
    from .accounts import TEST_MNEMONIC, derive_accounts
    from .config import COMPANIES

    mnemonic = config.mnemonic or (TEST_MNEMONIC if config.mode == "tester" else "")
    accounts = derive_accounts(mnemonic)
    pubkeys = Federation(list(COMPANIES)).public_keys
    if config.mode == "tester":
        from web3 import EthereumTesterProvider

        from .deployer import ensure_tester_registry

        w3 = Web3(EthereumTesterProvider())
        contract = ensure_tester_registry(w3, accounts, pubkeys)
        return Web3Chain(config, w3, contract, accounts)

    import json
    from pathlib import Path

    from .deployer import connect, registry_contract

    w3 = connect(config.rpc_url, timeout=5)
    if not w3.is_connected():
        raise ConnectionError("RPC injoignable")
    if w3.eth.chain_id != config.chain_id:
        raise ConnectionError(
            f"chainId {w3.eth.chain_id} différent de {config.chain_id}")
    dep = json.loads(Path(config.deployment_path).read_text(encoding="utf-8"))
    contract = registry_contract(w3, dep["address"])
    return Web3Chain(config, w3, contract, accounts)
