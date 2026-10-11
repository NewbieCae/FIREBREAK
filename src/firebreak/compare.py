""""With vs without Firebreak": policy comparison on the current
simulation and its active declarations.

Policy B (without Firebreak): for each declaration (source, since), cut off
the source company and its direct customers: every record in their
ledgers with `ts >= since` is blocked. Same definition as
`policy_partner_block` in synth.py.

Policy C (with Firebreak): the records currently `quarantined`.

Ground truth: BFS from the records ISSUED by the source in its own ledger
after `since`, along recorded dependencies (inputs + cross-company sends);
`verified` stops propagation. Independent of statuses: same definition as
`_truth` in synth.py.
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
        "date": "September 2025",
        "text": "After a cyberattack, JLR shuts down its systems: its UK plants "
                "stay idle for about six weeks. £196M in attack-related "
                "costs for the quarter, and subcontractors lay off "
                "their workers.",
        "source": "https://www.reuters.com/business/retail-consumer/jaguar-land-rovers-uk-production-returns-normal-after-weeks-long-cyber-shutdown-2025-11-14/",
    },
    {
        "name": "CDK Global",
        "date": "June 2024",
        "text": "After two cyberattacks, the software vendor shuts down its "
                "systems: nearly 15,000 car dealerships in North America "
                "go back to paper for almost two weeks.",
        "source": "https://www.cnn.com/2024/07/02/business/cdk-global-dealers-online",
    },
]


def _declarations(sim: Simulation) -> dict[str, datetime]:
    """source -> earliest since, union of all ledgers."""
    decls: dict[str, datetime] = {}
    for ledger in sim.ledgers.values():
        for d in ledger.declarations:
            if d.source not in decls or d.since < decls[d.source]:
                decls[d.source] = d.since
    return decls


def _truth(sim: Simulation, source: str, since: datetime) -> set[str]:
    """Truly tainted records, regardless of statuses:
    seeds = records issued by the source in ITS ledger (origin ==
    company, not a received copy) with ts >= since; propagation along
    inputs and cross-company sends; `verified` stops it."""
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
    """Aggregate of Céline's bench (bench/results.csv), read on demand:
    per-seed mean for policies B and C, at p=0 and at the highest p present."""
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
        raise LookupError("no active declaration")

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
        "title": "Without Firebreak",
        "policy": "B",
        "subtitle": "Cut off the supplier and its direct customers since 2 pm",
        "scope": scopes,
        **_metrics(without_blocked, truth, records),
    }
    with_fb = {
        "title": "With Firebreak",
        "policy": "C",
        "subtitle": "Freeze only the tainted operations",
        **_metrics(with_blocked, truth, records),
    }
    return {
        "declarations": [
            {"company": s, "since": since.isoformat()}
            for s, since in sorted(decls.items())
        ],
        "truth": {
            "contaminated": len(truth),
            "ids": sorted(truth),
            "definition": "Truly tainted records: everything that depends, "
                          "even indirectly, on data issued by the compromised "
                          "source since the declared time (unless verified "
                          "evidence stops the propagation).",
        },
        "without": without,
        "with": with_fb,
        "healthy_blocked_ratio": (
            without["healthy_blocked"] / with_fb["healthy_blocked"]
            if with_fb["healthy_blocked"] else None),
        "bench": bench_block(),
        "real_world": REAL_WORLD,
    }
