"""Chain configuration, read from the environment and `.env.local`.

Never imports `web3`: this module is loaded even when the chain is
disabled. The mnemonic appears neither in `repr` nor in errors.
"""

from __future__ import annotations

import os
import warnings
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOTENV = REPO_ROOT / ".env.local"
DEFAULT_DEPLOYMENT = REPO_ROOT / "contracts" / "deployments" / "l1.json"

# Same identifiers and same order as scenario.py.
COMPANIES = ("fournisseur", "fabricant", "distributeur", "client")
MODES = ("off", "tester", "l1")


@dataclass(frozen=True)
class ChainConfig:
    mode: str = "off"
    rpc_url: str | None = None
    chain_id: int | None = None
    explorer_url: str | None = None
    mnemonic: str | None = field(default=None, repr=False)
    deployment_path: Path = DEFAULT_DEPLOYMENT

    def __repr__(self) -> str:
        masked = "***" if self.mnemonic else None
        return (
            f"ChainConfig(mode={self.mode!r}, rpc_url={self.rpc_url!r}, "
            f"chain_id={self.chain_id!r}, explorer_url={self.explorer_url!r}, "
            f"mnemonic={masked!r}, deployment_path={str(self.deployment_path)!r})"
        )

    @property
    def enabled(self) -> bool:
        return self.mode != "off"


def parse_dotenv(path: Path) -> dict[str, str]:
    """`KEY=value` per line; `#` at the start of a line = comment;
    single or double quotes around the value are stripped."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def apply_dotenv(env: MutableMapping[str, str], dotenv_path: Path) -> None:
    """Fills `env` from `.env.local` without overwriting an already defined variable."""
    for key, value in parse_dotenv(dotenv_path).items():
        env.setdefault(key, value)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_chain_config(
    env: Mapping[str, str] | None = None, dotenv_path: Path | None = None
) -> ChainConfig:
    """Without `env`, reads `os.environ` after loading `.env.local` into it (which
    also makes `FIREBREAK_KEY_SEED` visible to federation.py). With an explicit
    `env` (tests), `.env.local` is only read if `dotenv_path` is given."""
    if env is None:
        apply_dotenv(os.environ, dotenv_path or DEFAULT_DOTENV)
        source: Mapping[str, str] = os.environ
    else:
        merged = dict(env)
        if dotenv_path is not None:
            apply_dotenv(merged, dotenv_path)
        source = merged

    mode = (_blank_to_none(source.get("FIREBREAK_CHAIN")) or "off").lower()
    if mode not in MODES:
        warnings.warn(
            f"FIREBREAK_CHAIN={mode!r} unknown (expected: {', '.join(MODES)}): chain disabled.",
            stacklevel=2,
        )
        mode = "off"

    chain_id_raw = _blank_to_none(source.get("FIREBREAK_CHAIN_ID"))
    try:
        chain_id = int(chain_id_raw, 0) if chain_id_raw else None
    except ValueError:
        warnings.warn("FIREBREAK_CHAIN_ID is not an integer: ignored.", stacklevel=2)
        chain_id = None

    deployment_raw = _blank_to_none(source.get("FIREBREAK_CHAIN_DEPLOYMENT"))
    deployment = Path(deployment_raw) if deployment_raw else DEFAULT_DEPLOYMENT
    if not deployment.is_absolute():
        deployment = REPO_ROOT / deployment

    explorer = _blank_to_none(source.get("FIREBREAK_CHAIN_EXPLORER_URL"))
    return ChainConfig(
        mode=mode,
        rpc_url=_blank_to_none(source.get("FIREBREAK_CHAIN_RPC_URL")),
        chain_id=chain_id,
        explorer_url=explorer.rstrip("/") if explorer else None,
        mnemonic=_blank_to_none(source.get("FIREBREAK_CHAIN_MNEMONIC")),
        deployment_path=deployment,
    )


def explorer_tx_link(cfg: ChainConfig, tx_hash: str) -> str | None:
    if not cfg.explorer_url or not tx_hash:
        return None
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash
    return f"{cfg.explorer_url}/tx/{tx_hash}"


def explorer_address_link(cfg: ChainConfig, address: str) -> str | None:
    if not cfg.explorer_url or not address:
        return None
    return f"{cfg.explorer_url}/address/{address}"
