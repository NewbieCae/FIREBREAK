"""Banc d'essai : générateur à graine, vérité terrain et 4 politiques."""

import dataclasses
import socket
import subprocess
import sys
from collections import Counter

import pytest

from firebreak.synth import (
    evaluate,
    generate,
    missing_provenance,
    policy_alert_only,
    policy_cautious,
    policy_firebreak,
    policy_partner_block,
    run_policies,
)

SEEDS = range(20)


def test_same_seed_same_world_and_results():
    a, b = generate(7, p_hidden=0.2), generate(7, p_hidden=0.2)
    assert a == b
    assert repr(run_policies(a)) == repr(run_policies(b))  # NaN != NaN
    assert generate(8, p_hidden=0.2).records != a.records


def test_world_shape():
    w = generate(3, n_companies=5, n_ops=300)
    assert len(w.records) == 300
    assert len(w.companies) == 5
    assert w.truth, "la compromission doit contaminer quelque chose"
    ts = [r.ts for r in w.records]
    assert ts == sorted(ts)


def test_true_world_independent_of_p_and_hiding_nested():
    w0, w1, w3 = (generate(5, p_hidden=p) for p in (0.0, 0.1, 0.3))
    assert w0.records == w1.records == w3.records
    assert w0.truth == w3.truth
    assert not w0.hidden
    assert w1.hidden <= w3.hidden
    assert generate(5, p_hidden=1.0).hidden == frozenset(w0.true_edges())


def test_truth_excludes_verified_records():
    for seed in SEEDS:
        w = generate(seed)
        verified = {r.id for r in w.records if r.verified}
        assert not (w.truth & verified)


@pytest.mark.parametrize("seed", SEEDS)
def test_firebreak_full_recall_without_hidden_dependencies(seed):
    w = generate(seed, p_hidden=0.0)
    m = evaluate(w, policy_firebreak(w))
    assert m["recall"] == 1.0
    assert m["leaks"] == 0


@pytest.mark.parametrize("p", [0.0, 0.3])
def test_alert_only_lets_all_contamination_through(p):
    for seed in SEEDS:
        w = generate(seed, p_hidden=p)
        assert policy_alert_only(w) == set()
        m = evaluate(w, set())
        assert m["leaks"] == len(w.truth)
        assert m["collateral"] == 0
        assert m["recall"] == 0.0
        assert m["healthy_preserved"] == 1.0


def test_partner_block_scope():
    w = generate(11)
    blocked = policy_partner_block(w)
    scope = {w.compromised, *w.partners[w.compromised]}
    by_id = {r.id: r for r in w.records}
    assert blocked
    assert all(by_id[r].company in scope and by_id[r].ts >= w.since for r in blocked)


def test_firebreak_beats_partner_block_on_collateral():
    """Sur la moyenne de 20 mondes, Firebreak bloque moins d'activité saine
    que le blocage des partenaires, sans fuir davantage à p = 0."""
    fb = [run_policies(generate(s)) for s in SEEDS]
    coll_b = sum(r["B"]["collateral"] for r in fb)
    coll_c = sum(r["C"]["collateral"] for r in fb)
    leaks_b = sum(r["B"]["leaks"] for r in fb)
    leaks_c = sum(r["C"]["leaks"] for r in fb)
    assert coll_c < coll_b
    assert leaks_c <= leaks_b


def test_simulation_is_fresh_each_time():
    w = generate(2)
    assert policy_firebreak(w) == policy_firebreak(w)


def test_no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("appel réseau interdit dans le banc d'essai")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for p in (0.0, 0.3):
        run_policies(generate(1, p_hidden=p))


def test_no_llm_module_loaded():
    """Le banc n'importe ni le module IA ni boto3 (process isolé, car
    d'autres tests chargent firebreak.ai)."""
    code = (
        "import sys\n"
        "from firebreak.synth import generate, run_policies\n"
        "run_policies(generate(0, p_hidden=0.2))\n"
        "bad = [m for m in ('firebreak.ai', 'boto3', 'botocore') if m in sys.modules]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_bench_script_writes_outputs(tmp_path):
    csv_path, md_path = tmp_path / "results.csv", tmp_path / "bench.md"
    subprocess.run(
        [sys.executable, "scripts/bench.py", "--seeds", "3", "--p", "0,0.2",
         "--csv", str(csv_path), "--md", str(md_path)],
        check=True, capture_output=True,
    )
    lines = csv_path.read_text().splitlines()
    assert lines[0].startswith("seed,p_hidden,policy")
    assert len(lines) == 1 + 3 * 2 * 4
    md = md_path.read_text()
    assert "Firebreak" in md and "±" in md


# -- v2 : tirage, actions irréversibles, politique D, rapport ---------------


def test_every_company_can_be_compromised_including_the_last():
    drawn = Counter(generate(s).compromised for s in range(200))
    assert set(drawn) == {f"e{i}" for i in range(5)}
    assert drawn["e4"] > 0, "le client final (sans client) doit aussi être tiré"


def test_external_receptions_are_legit_and_untokened():
    for seed in SEEDS:
        w = generate(seed)
        ext = {r.id for r in w.records if r.external}
        assert not (ext & w.truth)
        sim = w.simulation()
        for rid in ext:
            rec = sim.find_record(rid)
            assert rec.kind == "received" and rec.token is None


@pytest.mark.parametrize("policy", ["C", "D"])
def test_no_irreversible_leak_at_p0_while_alert_only_leaks_them_all(policy):
    total_gates = 0
    for seed in SEEDS:
        r = run_policies(generate(seed, p_hidden=0.0))
        assert r[policy]["leaked_gates"] == 0
        assert r["A"]["leaked_gates"] == r["A"]["contaminated_gates"]
        total_gates += r["A"]["contaminated_gates"]
    assert total_gates > 0


@pytest.mark.parametrize("p", [0.0, 0.3])
def test_cautious_blocks_superset_of_firebreak(p):
    for seed in SEEDS:
        w = generate(seed, p_hidden=p)
        assert policy_firebreak(w) <= policy_cautious(w)


class _EngineViewOnly:
    """Ce que voit C, et rien d'autre : toute lecture de la vérité terrain,
    des dépendances cachées ou des vrais records fait échouer le test."""

    def __init__(self, world):
        self._world = world
        self.compromised = world.compromised
        self.since = world.since
        self.partners = world.partners  # liens contractuels connus (pas lus par D)

    def simulation(self):
        return self._world.simulation()

    def __getattr__(self, name):
        raise AssertionError(f"D a lu world.{name} (interdit : vérité terrain)")


@pytest.mark.parametrize("p", [0.0, 0.3])
def test_cautious_never_reads_ground_truth(p):
    for seed in range(10):
        w = generate(seed, p_hidden=p)
        assert policy_cautious(_EngineViewOnly(w)) == policy_cautious(w)


def test_cautious_depends_only_on_recorded_view():
    """Deux mondes au même état moteur mais aux vérités différentes : D donne
    le même résultat. On « enregistre » le monde caché comme vrai : entrées
    cachées supprimées, envois cachés devenus des réceptions d'hors fédération."""
    w = generate(4, p_hidden=0.3)
    assert w.hidden
    flat = []
    for r in w.records:
        if r.sent_from and (r.sent_from[1], r.id) in w.hidden:
            flat.append(dataclasses.replace(r, sent_from=None, external=True))
        else:
            flat.append(dataclasses.replace(
                r, inputs=tuple(x for x in r.inputs if (x, r.id) not in w.hidden)))
    twin = dataclasses.replace(w, records=tuple(flat), hidden=frozenset(),
                               truth=frozenset(rr.id for rr in flat))
    assert twin.truth != w.truth
    assert policy_cautious(twin) == policy_cautious(w)
    sim_w, sim_t = w.simulation(), twin.simulation()
    for sim in (sim_w, sim_t):
        sim.declare_compromise(w.compromised, w.since)
    assert missing_provenance(sim_w, w.compromised, w.since) == \
        missing_provenance(sim_t, w.compromised, w.since)


def test_cautious_recovers_hidden_sends():
    """À p > 0, D rattrape des fuites de C (en moyenne sur 20 mondes)."""
    leaks_c = leaks_d = 0
    for seed in SEEDS:
        r = run_policies(generate(seed, p_hidden=0.3))
        leaks_c += r["C"]["leaks"]
        leaks_d += r["D"]["leaks"]
    assert leaks_d < leaks_c


def test_origin_rule_diagnostic_bounded():
    for seed in SEEDS:
        c = run_policies(generate(seed))["C"]
        assert 0 <= c["fp_origin_rule"] <= c["collateral"]


def test_bench_deterministic_and_reports_limits(tmp_path):
    outs = []
    for k in range(2):
        csv_path, md_path = tmp_path / f"r{k}.csv", tmp_path / f"b{k}.md"
        subprocess.run(
            [sys.executable, "scripts/bench.py", "--seeds", "6", "--p", "0,0.3",
             "--csv", str(csv_path), "--md", str(md_path)],
            check=True, capture_output=True,
        )
        outs.append((csv_path.read_text(), md_path.read_text()))
    assert outs[0] == outs[1]
    csv_text, md = outs[0]
    header = csv_text.splitlines()[0].split(",")
    assert {"leaks", "leaked_gates", "contaminated_gates", "fp_origin_rule"} <= set(header)
    assert {line.split(",")[2] for line in csv_text.splitlines()[1:]} == {"A", "B", "C", "D"}
    for needle in ("## Limites", "Règle d'origine", "Dépendances manquantes",
                   "provenance manquante", "borne haute", "5e centile",
                   "Ventilation par entreprise compromise", "au moins une fuite"):
        assert needle in md, needle
