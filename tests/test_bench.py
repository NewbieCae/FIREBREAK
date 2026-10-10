"""Banc d'essai : générateur à graine, vérité terrain et 3 politiques."""

import socket
import subprocess
import sys

import pytest

from firebreak.synth import (
    evaluate,
    generate,
    policy_alert_only,
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
    assert w.partners[w.compromised], "l'entreprise compromise a des clients"
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
    assert len(lines) == 1 + 3 * 2 * 3
    md = md_path.read_text()
    assert "Firebreak" in md and "±" in md
