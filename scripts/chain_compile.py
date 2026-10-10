"""Compile contracts/FirebreakRegistry.sol → contracts/build/FirebreakRegistry.json.

Le JSON produit est versionné : le serveur et les tests n'ont pas besoin de
solc. Idempotent : sans changement de source, le fichier n'est pas réécrit.

    uv run python scripts/chain_compile.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "FirebreakRegistry.sol"
OUTPUT = ROOT / "contracts" / "build" / "FirebreakRegistry.json"
CONTRACT = "FirebreakRegistry"
SOLC_VERSION = "0.8.24"
EVM_VERSION = "paris"  # pas de PUSH0 : compatible avec toute L1 Subnet-EVM
OPTIMIZER_RUNS = 200


sys.path.insert(0, str(ROOT / "src"))
from firebreak.chain.artifact import source_sha256  # noqa: E402


def compile_artifact() -> dict:
    import solcx

    if SOLC_VERSION not in {str(v) for v in solcx.get_installed_solc_versions()}:
        print(f"→ installation de solc {SOLC_VERSION}")
        solcx.install_solc(SOLC_VERSION)
    source = SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    out = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {SOURCE.name: {"content": source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": OPTIMIZER_RUNS},
                "evmVersion": EVM_VERSION,
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_version=SOLC_VERSION,
    )
    contract = out["contracts"][SOURCE.name][CONTRACT]
    return {
        "contractName": CONTRACT,
        "abi": contract["abi"],
        "bytecode": "0x" + contract["evm"]["bytecode"]["object"],
        "solcVersion": SOLC_VERSION,
        "evmVersion": EVM_VERSION,
        "optimizerRuns": OPTIMIZER_RUNS,
        "sourceSha256": source_sha256(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="échoue si le build ne correspond pas à la source, sans compiler")
    args = parser.parse_args(argv)

    current = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    up_to_date = current is not None and current.get("sourceSha256") == source_sha256()
    if args.check:
        print("build à jour" if up_to_date else "build absent ou périmé : relancer chain_compile.py")
        return 0 if up_to_date else 1
    if up_to_date:
        print(f"{OUTPUT.relative_to(ROOT)} déjà à jour")
        return 0

    artifact = compile_artifact()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    size = (len(artifact["bytecode"]) - 2) // 2
    print(f"→ {OUTPUT.relative_to(ROOT)} écrit (bytecode {size} octets, solc {SOLC_VERSION}, evm {EVM_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
