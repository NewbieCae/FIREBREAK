"""Chargement du contrat compilé (contracts/build/FirebreakRegistry.json)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .config import REPO_ROOT

ARTIFACT_PATH = REPO_ROOT / "contracts" / "build" / "FirebreakRegistry.json"
SOURCE_PATH = REPO_ROOT / "contracts" / "FirebreakRegistry.sol"


def source_sha256(path: Path = SOURCE_PATH) -> str:
    """Empreinte de la source Solidity, fins de ligne normalisées (Windows/Linux)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class ArtifactMissing(FileNotFoundError):
    pass


@lru_cache(maxsize=4)
def load_artifact(path: Path = ARTIFACT_PATH) -> dict:
    """Renvoie {contractName, abi, bytecode, solcVersion, evmVersion, sourceSha256, ...}."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArtifactMissing(
            f"{path} absent : lancer `uv run python scripts/chain_compile.py`"
        ) from exc
