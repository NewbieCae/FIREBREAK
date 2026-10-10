"""Mondes synthétiques à graine pour le banc d'essai Firebreak.

`generate(seed, ...)` construit une supply chain aléatoire mais
reproductible : des entreprises reliées par des relations
fournisseur → client, ~300 opérations, et une VÉRITÉ TERRAIN, c'est-à-dire
toutes les vraies dépendances entre records.

Le moteur ne voit que les dépendances *enregistrées* : chaque vraie
dépendance (entrée d'un record, ou envoi d'une entreprise à une autre) est
cachée avec la probabilité `p_hidden`. Une dépendance d'envoi cachée donne
une copie reçue sans provenance : pas de jeton, origine = l'entreprise qui
la détient.

Vérité : les records émis par l'entreprise compromise à partir de `since`
et tous leurs descendants par les vraies dépendances, sauf les records
`verified` (jamais contaminés, ils arrêtent la propagation, comme dans le
moteur).

Quatre politiques sont évaluées sur le même monde :
- A « alerte seule » : on prévient, rien n'est bloqué ;
- B « blocage partenaires » : tout record daté de `since` ou après chez
  l'entreprise compromise et ses clients directs est bloqué ;
- C « Firebreak » : le moteur existant (Simulation.declare_compromise) ;
- D « Firebreak + prudence » (banc uniquement) : C, plus la quarantaine des
  réceptions sans provenance enregistrée chez les partenaires directs après
  `since`, et de ce qui en dépend. Signal lu dans l'état du moteur seulement.

Aucun appel réseau ni LLM : uniquement le moteur à règles.
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
ROLES = ["Fournisseur", "Sous-traitant", "Fabricant", "Assembleur",
         "Distributeur", "Grossiste", "Client"]
NATIVE_KINDS = ["purchase_order", "asn", "quality_cert", "invoice",
                "payment", "production", "shipment"]
GATE_KINDS = {"payment", "shipment", "production"}

P_RECEIVE = 0.3  # part des opérations qui sont une réception
P_EXTERNAL = 0.1  # part des réceptions venues d'hors fédération : légitimes, sans jeton
P_VERIFIED = 0.05  # part des opérations confirmées par une source de confiance
WINDOW = 25  # les entrées d'un record sont prises parmi les WINDOW précédents

POLICIES = {
    "A": "Alerte seule",
    "B": "Blocage fournisseur + partenaires",
    "C": "Firebreak",
    "D": "Firebreak + prudence",
}


@dataclass(frozen=True)
class SynthRecord:
    """Record avec ses vraies dépendances (vérité terrain)."""

    id: str
    company: str
    kind: str
    ts: datetime
    inputs: tuple[str, ...]  # vraies entrées, même registre
    gate: bool
    verified: bool
    sent_from: tuple[str, str] | None = None  # (expéditeur, record) si copie reçue
    external: bool = False  # réception légitime d'hors fédération (jamais de jeton)

    @property
    def origin(self) -> str:
        return self.sent_from[0] if self.sent_from else self.company


@dataclass(frozen=True)
class World:
    seed: int
    p_hidden: float
    companies: tuple[Company, ...]
    partners: dict[str, tuple[str, ...]]  # expéditeur -> clients directs
    records: tuple[SynthRecord, ...]  # ordre chronologique
    compromised: str
    since: datetime
    hidden: frozenset[tuple[str, str]]  # arêtes (parent, enfant) non enregistrées
    truth: frozenset[str]  # records réellement contaminés

    def true_edges(self) -> list[tuple[str, str]]:
        edges = []
        for r in self.records:
            edges.extend((p, r.id) for p in r.inputs)
            if r.sent_from:
                edges.append((r.sent_from[1], r.id))
        return edges

    def simulation(self) -> Simulation:
        """Registres + fédération construits avec les seules dépendances
        enregistrées. Objets neufs à chaque appel (le moteur les modifie)."""
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
    """Relations fournisseur → client, sans cycle (rang i vers rang j > i)."""
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
    """Monde déterministe pour (seed, n_companies, n_ops). Le monde réel ne
    dépend pas de p_hidden ; seules les dépendances cachées en dépendent, et
    elles sont emboîtées : ce qui est caché à p l'est aussi à p' > p.
    `p_external` : part des réceptions venues d'hors fédération (bruit pour
    le signal « provenance manquante » de la politique D)."""
    if n_companies < 2:
        raise ValueError("il faut au moins 2 entreprises")
    rng = random.Random(seed)
    partners = _company_graph(rng, n_companies)
    suppliers: dict[str, list[str]] = {cid: [] for cid in partners}
    for s, clients in partners.items():
        for c in clients:
            suppliers[c].append(s)
    companies = tuple(
        Company(cid, f"Entreprise {i + 1}", ROLES[min(i, len(ROLES) - 1)])
        for i, cid in enumerate(partners)
    )

    by_company: dict[str, list[str]] = {cid: [] for cid in partners}
    sent: set[tuple[str, str]] = set()  # (record expéditeur, destinataire)
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

    compromised = rng.choice(list(partners))  # toutes, y compris le client final
    since = records[int(n_ops * rng.uniform(0.3, 0.6))].ts

    # Tirages de masquage indépendants du monde, un par vraie arête.
    hide_rng = random.Random(f"hide-{seed}")
    rec_tuple = tuple(records)
    world = World(seed, p_hidden, companies, partners, rec_tuple, compromised,
                  since, frozenset(), _truth(rec_tuple, compromised, since))
    hidden = frozenset(e for e in world.true_edges() if hide_rng.random() < p_hidden)
    return World(seed, p_hidden, companies, partners, rec_tuple, compromised,
                 since, hidden, world.truth)


# -- politiques ------------------------------------------------------------


def policy_alert_only(world: World) -> set[str]:
    return set()


def policy_partner_block(world: World) -> set[str]:
    scope = {world.compromised, *world.partners[world.compromised]}
    return {r.id for r in world.records if r.company in scope and r.ts >= world.since}


def firebreak_run(world: World) -> Simulation:
    """Le moteur, sur ce qu'il voit : registres + liens enregistrés."""
    sim = world.simulation()
    sim.declare_compromise(world.compromised, world.since)
    return sim


def quarantined(sim: Simulation) -> set[str]:
    return {r.id for led in sim.ledgers.values() for r in led.records.values()
            if r.status == "quarantined"}


def policy_firebreak(world: World) -> set[str]:
    return quarantined(firebreak_run(world))


def missing_provenance(sim: Simulation, compromised: str, since: datetime) -> set[str]:
    """Signal « provenance manquante », lu UNIQUEMENT dans l'état du moteur
    (registres + liens de la fédération) : réceptions venues de l'extérieur
    (`kind == "received"`) datées de `since` ou après, sans jeton ni lien
    enregistré, chez les partenaires directs connus de l'entreprise
    compromise ; puis tout ce qui en dépend dans le graphe enregistré
    (dépendances internes + liens entre entreprises), en épargnant
    `verified` et `released` comme le moteur.

    Ne reçoit pas le monde : n'a accès ni à la vérité terrain ni au drapeau
    « dépendance cachée »."""
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


# -- métriques -------------------------------------------------------------


def evaluate(world: World, blocked: set[str]) -> dict:
    """Fuites (dont actions irréversibles), dégâts collatéraux, activité
    saine préservée, précision, rappel. Précision (rien de bloqué) et rappel
    (rien de contaminé) non définis : NaN."""
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
    """Diagnostic pour le rapport (lit la vérité, ne décide rien) : opérations
    saines bloquées par Firebreak à cause de la règle d'origine : données
    attribuées à l'entreprise compromise après `since` mais pas contaminées
    (copie d'une donnée antérieure ou vérifiée, réception d'hors fédération
    chez elle), et ce qui en découle dans le graphe enregistré."""
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
    """Métriques des 4 politiques ; le moteur ne tourne qu'une fois (C et D)."""
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
