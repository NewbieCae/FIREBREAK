"""Benchmark: seeded generator, ground truth and 4 policies."""

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
    assert w.truth, "the compromise must contaminate something"
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
    """Averaged over 20 worlds, Firebreak blocks less healthy activity than
    partner blocking, without leaking more at p = 0."""
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
        raise AssertionError("network calls are forbidden in the benchmark")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for p in (0.0, 0.3):
        run_policies(generate(1, p_hidden=p))


def test_no_llm_module_loaded():
    """The benchmark imports neither the AI module nor boto3 (isolated
    process, since other tests load firebreak.ai)."""
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


# -- v2: draw, irreversible actions, policy D, report ---------------------


def test_every_company_can_be_compromised_including_the_last():
    drawn = Counter(generate(s).compromised for s in range(200))
    assert set(drawn) == {f"e{i}" for i in range(5)}
    assert drawn["e4"] > 0, "the final customer (who has no customers) must also be drawn"


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
    """What C sees, and nothing else: any read of the ground truth, the
    hidden dependencies or the true records fails the test."""

    def __init__(self, world):
        self._world = world
        self.compromised = world.compromised
        self.since = world.since
        self.partners = world.partners  # known contractual links (not read by D)

    def simulation(self):
        return self._world.simulation()

    def __getattr__(self, name):
        raise AssertionError(f"D read world.{name} (forbidden: ground truth)")


@pytest.mark.parametrize("p", [0.0, 0.3])
def test_cautious_never_reads_ground_truth(p):
    for seed in range(10):
        w = generate(seed, p_hidden=p)
        assert policy_cautious(_EngineViewOnly(w)) == policy_cautious(w)


def test_cautious_depends_only_on_recorded_view():
    """Two worlds with the same engine state but different truths: D gives
    the same result. The hidden world is "recorded" as true: hidden inputs
    removed, hidden sends turned into out-of-federation receptions."""
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
    """At p > 0, D catches leaks missed by C (averaged over 20 worlds)."""
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
    for needle in ("## Limitations", "origin rule", "Missing dependencies",
                   "missing provenance", "upper bound", "5th percentile",
                   "Breakdown by compromised company", "at least one leak"):
        assert needle in md, needle


# -- sensitivity: chain size and out-of-federation noise --------------------


def test_default_noise_keeps_main_worlds_unchanged():
    for seed in range(5):
        assert generate(seed) == generate(seed, p_external=0.1)


def test_external_noise_parameter():
    def n_ext(x):
        return sum(r.external for s in SEEDS for r in generate(s, p_external=x).records)

    assert n_ext(0.0) == 0
    assert n_ext(0.1) < n_ext(0.3)


def test_twelve_companies_all_drawn_and_full_recall_at_p0():
    drawn = Counter(generate(s, n_companies=12, n_ops=720).compromised for s in range(500))
    assert set(drawn) == {f"e{i}" for i in range(12)}
    for seed in range(5):
        w = generate(seed, n_companies=12, n_ops=720)
        assert evaluate(w, policy_firebreak(w))["recall"] == 1.0


def _bench(tmp_path, tag, *extra):
    csv_path, md_path = tmp_path / f"{tag}.csv", tmp_path / f"{tag}.md"
    subprocess.run(
        [sys.executable, "scripts/bench.py", "--seeds", "4", "--p", "0,0.3",
         "--sizes", "5,12", "--noise", "0,0.3", "--sens-p", "0,0.3",
         "--csv", str(csv_path), "--md", str(md_path),
         "--sens-csv", str(tmp_path / f"{tag}-sens.csv"), *extra],
        check=True, capture_output=True,
    )
    sens = tmp_path / f"{tag}-sens.csv"
    return csv_path.read_text(), md_path.read_text(), sens.read_text() if sens.exists() else None


def test_sensitivity_deterministic_separate_and_reported(tmp_path):
    a, b = _bench(tmp_path, "a"), _bench(tmp_path, "b")
    assert a == b
    main_csv, md, sens_csv = a
    assert "sweep" not in main_csv.splitlines()[0], "results.csv is still read by /api/compare"
    header = sens_csv.splitlines()[0].split(",")
    assert header[:5] == ["sweep", "n_companies", "n_ops", "p_external", "mean_clients"]
    sweeps = {(line.split(",")[0], line.split(",")[1], line.split(",")[2])
              for line in sens_csv.splitlines()[1:]}
    assert ("size", "12", "720") in sweeps and ("noise", "5", "300") in sweeps
    for needle in ("## Sensitivity", "### Chain size",
                   "### Out-of-federation reception noise",
                   "### Sensitivity: limitations and conclusions",
                   "get denser with size", "Cost of the",
                   "upper bound", "put to the test"):
        assert needle in md, needle


def test_sensitivity_does_not_change_main_results(tmp_path):
    with_sens = _bench(tmp_path, "w")
    without = _bench(tmp_path, "n", "--no-sensitivity")
    assert with_sens[0] == without[0]
    assert without[2] is None and "## Sensitivity" not in without[1]
