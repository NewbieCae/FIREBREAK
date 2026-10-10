"""« Avec vs sans Firebreak » — comparaison de politiques sur la simulation
courante et ses déclarations actives.

Politique B (sans Firebreak) : pour chaque déclaration (source, since), on
coupe l'entreprise source et ses clients directs — tout record de leurs
registres avec `ts >= since` est bloqué. Même définition que
`policy_partner_block` dans synth.py.

Politique C (avec Firebreak) : les records actuellement `quarantined`.

Vérité terrain : BFS depuis les records ÉMIS par la source dans son propre
registre après `since`, le long des dépendances enregistrées (inputs +
envois inter-entreprises) ; `verified` arrête la propagation. Indépendante
des statuts — même définition que `_truth` dans synth.py.
"""

from __future__ import annotations

import csv
from collections import deque
from datetime import datetime
from pathlib import Path

from .model import Record, payment_amount
from .simulation import Simulation

BENCH_CSV = Path(__file__).resolve().parents[2] / "bench" / "results.csv"
BENCH_COMMAND = "uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3"

REAL_WORLD = [
    {
        "name": "Jaguar Land Rover",
        "date": "septembre 2025",
        "text": "Après une cyberattaque, JLR coupe ses systèmes : ses usines "
                "britanniques restent à l'arrêt environ six semaines. 196 M£ "
                "de coûts liés à l'attaque sur le trimestre, et des "
                "sous-traitants mettent leurs salariés au chômage.",
        "source": "https://www.reuters.com/business/retail-consumer/jaguar-land-rovers-uk-production-returns-normal-after-weeks-long-cyber-shutdown-2025-11-14/",
    },
    {
        "name": "CDK Global",
        "date": "juin 2024",
        "text": "Après deux cyberattaques, l'éditeur coupe ses systèmes : "
                "près de 15 000 concessions automobiles en Amérique du Nord "
                "reviennent au papier pendant près de deux semaines.",
        "source": "https://www.cnn.com/2024/07/02/business/cdk-global-dealers-online",
    },
]


def _declarations(sim: Simulation) -> dict[str, datetime]:
    """source -> since la plus ancienne, union de tous les registres."""
    decls: dict[str, datetime] = {}
    for ledger in sim.ledgers.values():
        for d in ledger.declarations:
            if d.source not in decls or d.since < decls[d.source]:
                decls[d.source] = d.since
    return decls


def _truth(sim: Simulation, source: str, since: datetime) -> set[str]:
    """Records réellement contaminés, indépendamment des statuts :
    semences = records émis par la source dans SON registre (origin ==
    company, pas une copie reçue) avec ts >= since ; propagation le long
    des inputs et des envois inter-entreprises ; `verified` arrête."""
    children: dict[str, list[str]] = {}
    for ledger in sim.ledgers.values():
        for rid, r in ledger.records.items():
            for p in r.inputs:
                children.setdefault(p, []).append(rid)
    for link in sim.federation.links:
        children.setdefault(link.sender_record, []).append(link.recipient_record)

    seeds = deque(
        r.id
        for ledger in sim.ledgers.values()
        for r in ledger.records.values()
        if r.company == source and r.origin == source and r.ts >= since
    )
    records = {
        rid: r for led in sim.ledgers.values() for rid, r in led.records.items()
    }
    tainted: set[str] = set()
    while seeds:
        rid = seeds.popleft()
        if rid in tainted or records[rid].verified:
            continue
        tainted.add(rid)
        seeds.extend(children.get(rid, ()))
    return tainted


def _direct_clients(sim: Simulation, source: str) -> set[str]:
    return {l.recipient for l in sim.federation.links if l.sender == source}


def _metrics(blocked: set[str], truth: set[str],
             records: dict[str, Record]) -> dict:
    hit = len(blocked & truth)
    collateral = len(blocked - truth)
    healthy = len(records) - len(truth)
    leaked = sorted(truth - blocked)
    blocked_pay = sum(payment_amount(r) for r in records.values()
                      if r.id in blocked)
    flowing_pay = sum(payment_amount(r) for r in records.values()
                      if r.id not in blocked)
    return {
        "blocked": len(blocked),
        "healthy_blocked": collateral,
        "leaked": len(leaked),
        "leaked_ids": [
            {"id": rid, "label": records[rid].label,
             "company": records[rid].company}
            for rid in leaked
        ],
        "gates_blocked": sum(
            1 for rid in blocked if records[rid].gate),
        "payments_blocked_eur": blocked_pay,
        "payments_flowing_eur": flowing_pay,
        "activity_preserved_pct": (
            (healthy - collateral) / healthy * 100 if healthy else None),
        "precision": hit / len(blocked) if blocked else None,
        "recall": hit / len(truth) if truth else None,
        "companies_hit": sorted({records[rid].company for rid in blocked}),
        "blocked_ids": sorted(blocked),
    }


def bench_block(path: Path | None = None) -> dict | None:
    """Agrégat du bench de Céline (bench/results.csv), lu à la demande :
    moyenne par graine pour politique B et C, à p=0 et au p max présent."""
    path = path or BENCH_CSV
    if not path.exists():
        return None
    groups: dict[tuple[str, str], list[dict]] = {}
    p_values: set[str] = set()
    with path.open() as fh:
        for row in csv.DictReader(fh):
            p_values.add(row["p_hidden"])
            groups.setdefault((row["p_hidden"], row["policy"]), []).append(row)
    if not groups:
        return None
    p_min = min(p_values, key=float)
    p_max = max(p_values, key=float)

    def mean(rows: list[dict], key: str) -> float:
        vals = [float(r[key]) for r in rows if r[key]]
        return sum(vals) / len(vals) if vals else float("nan")

    out = {}
    for p in (p_min, p_max):
        for policy in ("B", "C"):
            rows = groups.get((p, policy), [])
            if not rows:
                continue
            out[f"p{p}:{policy}"] = {
                "seeds": len(rows),
                "healthy_blocked_mean": mean(rows, "collateral"),
                "leaks_mean": mean(rows, "leaks"),
                "recall_mean": mean(rows, "recall"),
                "activity_preserved_mean": mean(rows, "healthy_preserved"),
            }
    return {
        "p_values": sorted(p_values, key=float),
        "seeds_per_group": len(groups.get((p_min, "C"), [])),
        "command": BENCH_COMMAND,
        "groups": out,
    }


def compare(sim: Simulation) -> dict:
    decls = _declarations(sim)
    if not decls:
        raise LookupError("aucune déclaration active")

    records = {
        rid: r for led in sim.ledgers.values() for rid, r in led.records.items()
    }

    truth: set[str] = set()
    without_blocked: set[str] = set()
    scopes: dict[str, list[str]] = {}
    for source, since in decls.items():
        truth |= _truth(sim, source, since)
        scope = {source, *_direct_clients(sim, source)}
        scopes[source] = sorted(scope)
        without_blocked |= {
            r.id for r in records.values()
            if r.company in scope and r.ts >= since
        }

    with_blocked = {
        r.id for r in records.values() if r.status == "quarantined"
    }

    without = {
        "title": "Sans Firebreak",
        "policy": "B",
        "subtitle": "On coupe le fournisseur et ses clients directs depuis 14 h",
        "scope": scopes,
        **_metrics(without_blocked, truth, records),
    }
    with_fb = {
        "title": "Avec Firebreak",
        "policy": "C",
        "subtitle": "On gèle seulement les opérations contaminées",
        **_metrics(with_blocked, truth, records),
    }
    return {
        "declarations": [
            {"company": s, "since": since.isoformat()}
            for s, since in sorted(decls.items())
        ],
        "truth": {
            "contaminated": len(truth),
            "definition": "Records réellement contaminés : tout ce qui dépend, "
                          "même indirectement, d'une donnée émise par la source "
                          "compromise depuis l'heure déclarée (sauf preuve "
                          "vérifiée qui arrête la propagation).",
        },
        "without": without,
        "with": with_fb,
        "healthy_blocked_ratio": (
            without["healthy_blocked"] / with_fb["healthy_blocked"]
            if with_fb["healthy_blocked"] else None),
        "bench": bench_block(),
        "real_world": REAL_WORLD,
    }
