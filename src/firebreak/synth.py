"""Seeded synthetic worlds for the Firebreak benchmark.

`generate(seed, ...)` builds a random but reproducible supply chain:
companies linked by supplier → customer relationships, ~300 operations,
and a GROUND TRUTH, i.e. every true dependency between records.

The engine only sees *recorded* dependencies: each true dependency (a
record's input, or a send from one company to another) is hidden with
probability `p_hidden`. A hidden send dependency yields a received copy
with no provenance: no token, origin = the company holding it.

Truth: records issued by the compromised company from `since` onwards and
all their descendants through the true dependencies, except `verified`
records (never contaminated, they stop propagation, as in the engine).

Four policies are evaluated on the same world:
- A "alert only": everyone is warned, nothing is blocked;
- B "partner block": every record dated `since` or later at the
  compromised company and its direct customers is blocked;
- C "Firebreak": the existing engine (Simulation.declare_compromise);
- D "Firebreak + caution" (benchmark only): C, plus quarantine of
  receptions with no recorded provenance at direct partners after
  `since`, and of whatever depends on them. Signal read from engine state only.

No network or LLM calls: rule engine only.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from .engine import Ledger
from .federation import Federation
from .model import Company, Record
from .simulation import Simulation

START = datetime(2026, 10, 10, 8, 0, 0)
ROLES = ["Supplier", "Subcontractor", "Manufacturer", "Assembler",
         "Distributor", "Wholesaler", "Customer"]
NATIVE_KINDS = ["purchase_order", "asn", "quality_cert", "invoice",
                "payment", "production", "shipment"]
GATE_KINDS = {"payment", "shipment", "production"}

P_RECEIVE = 0.3  # share of operations that are receptions
P_EXTERNAL = 0.1  # share of receptions from outside the federation: legitimate, no token
P_VERIFIED = 0.05  # share of operations confirmed by a trusted source
WINDOW = 25  # a record's inputs are drawn from the previous WINDOW records

POLICIES = {
    "A": "Alert only",
    "B": "Block supplier + partners",
    "C": "Firebreak",
    "D": "Firebreak + caution",
}


@dataclass(frozen=True)
class SynthRecord:
    """Record with its true dependencies (ground truth)."""

    id: str
    company: str
    kind: str
    ts: datetime
    inputs: tuple[str, ...]  # true inputs, same ledger
    gate: bool
    verified: bool
    sent_from: tuple[str, str] | None = None  # (sender, record) if received copy
    external: bool = False  # legitimate reception from outside the federation (never a token)

    @property
    def origin(self) -> str:
        return self.sent_from[0] if self.sent_from else self.company


@dataclass(frozen=True)
class World:
    seed: int
    p_hidden: float
    companies: tuple[Company, ...]
    partners: dict[str, tuple[str, ...]]  # sender -> direct customers
    records: tuple[SynthRecord, ...]  # chronological order
    compromised: str
    since: datetime
    hidden: frozenset[tuple[str, str]]  # unrecorded (parent, child) edges
    truth: frozenset[str]  # actually contaminated records

    def true_edges(self) -> list[tuple[str, str]]:
        edges = []
        for r in self.records:
            edges.extend((p, r.id) for p in r.inputs)
            if r.sent_from:
                edges.append((r.sent_from[1], r.id))
        return edges

    def simulation(self) -> Simulation:
        """Ledgers + federation built from recorded dependencies only.
        Fresh objects on every call (the engine mutates them)."""
        ids = [c.id for c in self.companies]
        ledgers = {cid: Ledger(cid) for cid in ids}
        fed = Federation(ids)
        for r in self.records:
            origin, token = r.company, None
            if r.sent_from and (r.sent_from[1], r.id) not in self.hidden:
                origin = r.sent_from[0]
                token = fed.register_send(r.sent_from[0], r.sent_from[1], r.company, r.id)
            ledgers[r.company].add(Record(
                id=r.id, company=r.company, origin=origin, kind=r.kind, ts=r.ts,
                label=f"{r.kind} {r.id}",
                inputs=[p for p in r.inputs if (p, r.id) not in self.hidden],
                gate=r.gate, verified=r.verified, token=token,
            ))
        return Simulation(list(self.companies), ledgers, fed)


def _company_graph(rng: random.Random, n: int) -> dict[str, tuple[str, ...]]:
    """Supplier → customer relationships, acyclic (rank i to rank j > i)."""
    ids = [f"e{i}" for i in range(n)]
    out: dict[str, set[str]] = {cid: set() for cid in ids}
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or rng.random() < 0.3:
                out[ids[i]].add(ids[j])
    return {cid: tuple(sorted(v)) for cid, v in out.items()}


def _truth(records: tuple[SynthRecord, ...], compromised: str,
           since: datetime) -> frozenset[str]:
    by_id = {r.id: r for r in records}
    children: dict[str, list[str]] = {r.id: [] for r in records}
    for r in records:
        for p in r.inputs:
            children[p].append(r.id)
        if r.sent_from:
            children[r.sent_from[1]].append(r.id)
    queue = deque(r.id for r in records
                  if r.company == compromised and r.kind != "received"
                  and r.ts >= since)
    tainted: set[str] = set()
    while queue:
        rid = queue.popleft()
        if rid in tainted or by_id[rid].verified:
            continue
        tainted.add(rid)
        queue.extend(children[rid])
    return frozenset(tainted)


def generate(seed: int, n_companies: int = 5, n_ops: int = 300,
             p_hidden: float = 0.0, p_external: float = P_EXTERNAL) -> World:
    """Deterministic world for (seed, n_companies, n_ops). The true world
    does not depend on p_hidden; only the hidden dependencies do, and they
    are nested: whatever is hidden at p is also hidden at p' > p.
    `p_external`: share of receptions from outside the federation (noise for
    policy D's "missing provenance" signal)."""
    if n_companies < 2:
        raise ValueError("at least 2 companies are required")
    rng = random.Random(seed)
    partners = _company_graph(rng, n_companies)
    suppliers: dict[str, list[str]] = {cid: [] for cid in partners}
    for s, clients in partners.items():
        for c in clients:
            suppliers[c].append(s)
    companies = tuple(
        Company(cid, f"Company {i + 1}", ROLES[min(i, len(ROLES) - 1)])
        for i, cid in enumerate(partners)
    )

    by_company: dict[str, list[str]] = {cid: [] for cid in partners}
    sent: set[tuple[str, str]] = set()  # (sender record, recipient)
    records: list[SynthRecord] = []
    ts = START
    for i in range(n_ops):
        ts += timedelta(minutes=rng.randint(1, 4))
        owner = rng.choice(list(partners))
        rid = f"{owner}-{i:04d}"
        sent_from = None
        receive = rng.random() < P_RECEIVE
        external = receive and rng.random() < p_external
        if receive and not external and suppliers[owner]:
            sender = rng.choice(suppliers[owner])
            candidates = [x for x in by_company[sender][-WINDOW:]
                          if (x, owner) not in sent]
            if candidates:
                src = rng.choice(candidates)
                sent.add((src, owner))
                sent_from = (sender, src)
        if external:
            rec = SynthRecord(rid, owner, "received", ts, (), False, False, external=True)
        elif sent_from:
            rec = SynthRecord(rid, owner, "received", ts, (), False, False, sent_from)
        else:
            kind = rng.choice(NATIVE_KINDS)
            pool = by_company[owner][-WINDOW:]
            k = min(len(pool), rng.choices([0, 1, 2, 3], [0.2, 0.4, 0.3, 0.1])[0])
            rec = SynthRecord(
                rid, owner, kind, ts, tuple(rng.sample(pool, k)),
                gate=kind in GATE_KINDS, verified=rng.random() < P_VERIFIED,
            )
        records.append(rec)
        by_company[owner].append(rid)

    compromised = rng.choice(list(partners))  # any company, including the final customer
    since = records[int(n_ops * rng.uniform(0.3, 0.6))].ts

    # Hiding draws independent of the world, one per true edge.
    hide_rng = random.Random(f"hide-{seed}")
    rec_tuple = tuple(records)
    world = World(seed, p_hidden, companies, partners, rec_tuple, compromised,
                  since, frozenset(), _truth(rec_tuple, compromised, since))
    hidden = frozenset(e for e in world.true_edges() if hide_rng.random() < p_hidden)
    return World(seed, p_hidden, companies, partners, rec_tuple, compromised,
                 since, hidden, world.truth)


# -- policies --------------------------------------------------------------


def policy_alert_only(world: World) -> set[str]:
    return set()


def policy_partner_block(world: World) -> set[str]:
    scope = {world.compromised, *world.partners[world.compromised]}
    return {r.id for r in world.records if r.company in scope and r.ts >= world.since}


def firebreak_run(world: World) -> Simulation:
    """The engine, on what it sees: ledgers + recorded links."""
    sim = world.simulation()
    sim.declare_compromise(world.compromised, world.since)
    return sim


def quarantined(sim: Simulation) -> set[str]:
    return {r.id for led in sim.ledgers.values() for r in led.records.values()
            if r.status == "quarantined"}


def policy_firebreak(world: World) -> set[str]:
    return quarantined(firebreak_run(world))


def missing_provenance(sim: Simulation, compromised: str, since: datetime) -> set[str]:
    """"Missing provenance" signal, read ONLY from engine state (ledgers +
    federation links): receptions from outside (`kind == "received"`) dated
    `since` or later, with no token or recorded link, at the known direct
    partners of the compromised company; then everything that depends on
    them in the recorded graph (internal dependencies + inter-company
    links), sparing `verified` and `released` records like the engine.

    Does not receive the world: has no access to the ground truth or to the
    "hidden dependency" flag."""
    linked = {link.recipient_record for link in sim.federation.links}
    partners = {link.recipient for link in sim.federation.links
                if link.sender == compromised} - {compromised}
    records = {rid: r for led in sim.ledgers.values() for rid, r in led.records.items()}
    succ: dict[str, list[str]] = {}
    for led in sim.ledgers.values():
        for a, b in led.graph.edges():
            succ.setdefault(a, []).append(b)
    for link in sim.federation.links:
        succ.setdefault(link.sender_record, []).append(link.recipient_record)

    queue = deque(
        r.id for cid in sorted(partners) for r in sim.ledgers[cid].records.values()
        if r.kind == "received" and r.token is None and r.id not in linked
        and r.ts >= since
    )
    out: set[str] = set()
    while queue:
        rid = queue.popleft()
        r = records[rid]
        if rid in out or r.verified or r.status == "released":
            continue
        out.add(rid)
        queue.extend(succ.get(rid, []))
    return out


def policy_cautious(world: World) -> set[str]:
    sim = firebreak_run(world)
    return quarantined(sim) | missing_provenance(sim, world.compromised, world.since)


POLICY_FUNCS = {
    "A": policy_alert_only,
    "B": policy_partner_block,
    "C": policy_firebreak,
    "D": policy_cautious,
}


# -- metrics --------------------------------------------------------------


def evaluate(world: World, blocked: set[str]) -> dict:
    """Leaks (including irreversible actions), collateral damage, healthy
    activity preserved, precision, recall. Undefined precision (nothing
    blocked) and recall (nothing contaminated): NaN."""
    total = len(world.records)
    truth = world.truth
    gates = {r.id for r in world.records if r.gate}
    healthy = total - len(truth)
    hit = len(blocked & truth)
    collateral = len(blocked - truth)
    nan = float("nan")
    return {
        "records": total,
        "contaminated": len(truth),
        "contaminated_gates": len(truth & gates),
        "blocked": len(blocked),
        "leaks": len(truth) - hit,
        "leaked_gates": len((truth - blocked) & gates),
        "collateral": collateral,
        "healthy_preserved": (healthy - collateral) / healthy if healthy else nan,
        "precision": hit / len(blocked) if blocked else nan,
        "recall": hit / len(truth) if truth else nan,
    }


def origin_rule_collateral(world: World, sim: Simulation) -> int:
    """Report diagnostic (reads the truth, decides nothing): healthy
    operations blocked by Firebreak because of the origin rule, i.e. data
    attributed to the compromised company after `since` but not contaminated
    (copy of earlier or verified data, reception from outside the federation
    at that company), and whatever follows from it in the recorded graph."""
    blocked_fp = quarantined(sim) - world.truth
    records = {rid: r for led in sim.ledgers.values() for rid, r in led.records.items()}
    succ: dict[str, list[str]] = {}
    for led in sim.ledgers.values():
        for a, b in led.graph.edges():
            succ.setdefault(a, []).append(b)
    for link in sim.federation.links:
        succ.setdefault(link.sender_record, []).append(link.recipient_record)
    queue = deque(rid for rid in blocked_fp if records[rid].origin == world.compromised)
    seen: set[str] = set()
    while queue:
        rid = queue.popleft()
        if rid in seen or rid not in blocked_fp:
            continue
        seen.add(rid)
        queue.extend(succ.get(rid, []))
    return len(seen)


def run_policies(world: World) -> dict[str, dict]:
    """Metrics for the 4 policies; the engine runs only once (C and D)."""
    sim = firebreak_run(world)
    blocked_c = quarantined(sim)
    blocked = {
        "A": policy_alert_only(world),
        "B": policy_partner_block(world),
        "C": blocked_c,
        "D": blocked_c | missing_provenance(sim, world.compromised, world.since),
    }
    out = {name: evaluate(world, b) for name, b in blocked.items()}
    out["C"]["fp_origin_rule"] = origin_rule_collateral(world, sim)
    return out
