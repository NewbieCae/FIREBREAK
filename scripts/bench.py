"""Firebreak benchmark: 4 policies × N seeds × hidden-dependency rates.

    uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3

Writes bench/results.csv (one row per seed, p and policy) and
docs/bench-results.md (mean ± 95% CI, worst case, 5th percentile, share of
worlds with a leak, breakdown by compromised company, limitations).
No network or LLM calls.
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

from firebreak.synth import P_EXTERNAL, POLICIES, generate, run_policies

ROOT = Path(__file__).resolve().parent.parent
METRICS = ["leaks", "leaked_gates", "collateral", "healthy_preserved", "precision",
           "recall"]
FIELDS = ["seed", "p_hidden", "policy", "compromised", "records", "contaminated",
          "contaminated_gates", "blocked", *METRICS, "fp_origin_rule"]
LABELS = {
    "leaks": "Leaks (contaminated, not blocked)",
    "leaked_gates": "Leaked irreversible actions (contaminated, gate, not blocked)",
    "collateral": "Collateral damage (healthy blocked)",
    "healthy_preserved": "Healthy activity preserved",
    "precision": "Precision",
    "recall": "Recall",
}
PERCENT = {"healthy_preserved", "precision", "recall"}
NAN = float("nan")


# -- statistics --------------------------------------------------------------


def clean(values: list[float]) -> list[float]:
    return [v for v in values if not math.isnan(v)]


def mean_ci(values: list[float]) -> tuple[float, float, int]:
    """Mean and 95% CI half-width (normal approximation), ignoring NaN
    (undefined metric)."""
    xs = clean(values)
    n = len(xs)
    if n == 0:
        return NAN, NAN, 0
    m = sum(xs) / n
    if n == 1:
        return m, 0.0, 1
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, 1.96 * math.sqrt(var / n), n


def percentile(values: list[float], q: float) -> float:
    """Percentile q ∈ [0, 1], linear interpolation, NaN ignored."""
    xs = sorted(clean(values))
    if not xs:
        return NAN
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def share(values: list[float], pred) -> float:
    return sum(1 for v in values if pred(v)) / len(values) if values else NAN


# -- run ---------------------------------------------------------------------


def run(seeds: int, ps: list[float], n_companies: int, n_ops: int) -> list[dict]:
    rows = []
    for p in ps:
        for seed in range(seeds):
            world = generate(seed, n_companies=n_companies, n_ops=n_ops, p_hidden=p)
            for policy, metrics in run_policies(world).items():
                rows.append({"seed": seed, "p_hidden": p, "policy": policy,
                             "compromised": world.compromised,
                             "fp_origin_rule": NAN, **metrics})
    return rows


def write_csv(rows: list[dict], path: Path, fields: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if isinstance(v, float) and math.isnan(v) else
                            round(v, 6) if isinstance(v, float) else v)
                        for k, v in row.items()})


# -- sensitivity ---------------------------------------------------------------

OPS_PER_COMPANY = 60  # size sweep: same density per ledger
SENS_FIELDS = ["sweep", "n_companies", "n_ops", "p_external", "mean_clients", *FIELDS]


def run_sensitivity(seeds: int, sizes: list[int], noises: list[float],
                    ps: list[float]) -> list[dict]:
    """Two sweeps, same seeds as the main benchmark:
    - "size": n companies, OPS_PER_COMPANY × n operations, default noise;
    - "noise": 5 companies, 300 operations, a p_external share of receptions
      from outside the federation."""
    configs = [("size", n, OPS_PER_COMPANY * n, P_EXTERNAL) for n in sizes]
    configs += [("noise", 5, 300, x) for x in noises]
    rows = []
    for sweep, n, ops, ext in configs:
        for p in ps:
            for seed in range(seeds):
                world = generate(seed, n_companies=n, n_ops=ops, p_hidden=p,
                                 p_external=ext)
                clients = sum(len(v) for v in world.partners.values()) / n
                for policy, metrics in run_policies(world).items():
                    rows.append({"sweep": sweep, "n_companies": n, "n_ops": ops,
                                 "p_external": ext, "mean_clients": clients,
                                 "seed": seed, "p_hidden": p, "policy": policy,
                                 "compromised": world.compromised,
                                 "fp_origin_rule": NAN, **metrics})
    return rows


def render_sensitivity(rows: list[dict], sizes: list[int], noises: list[float],
                       ps: list[float]) -> list[str]:
    def vals(sweep, key, p, policy, metric):
        field = "n_companies" if sweep == "size" else "p_external"
        return [float(r[metric]) for r in rows
                if r["sweep"] == sweep and r[field] == key
                and r["p_hidden"] == p and r["policy"] == policy]

    def avg(*a):
        return mean_ci(vals(*a))[0]

    def leak_share(sweep, key, p, policy, metric="leaks"):
        return share(vals(sweep, key, p, policy, metric), lambda v: v > 0)

    pols = list(POLICIES)
    head = "| | " + " | ".join(f"{k} — {POLICIES[k]}" for k in pols) + " |"
    sep = "|---|" + "---|" * len(pols)
    seeds = len(vals("size", sizes[0], ps[0], "A", "leaks")) if sizes else 0
    lines = [
        "## Sensitivity",
        "",
        f"Same seeds as the main benchmark ({seeds} per configuration), "
        "compromised company drawn from all companies, p = "
        + " and ".join(f"{p:g}" for p in ps) + ". Data: `bench/sensitivity.csv`.",
        "",
    ]
    if sizes:
        lines += [
            "### Chain size",
            "",
            f"{OPS_PER_COMPANY} operations per company: "
            + ", ".join(f"{n} companies → {OPS_PER_COMPANY * n} operations"
                        for n in sizes)
            + f". Out-of-federation noise: {P_EXTERNAL:.0%}.",
            "",
        ]
        drawn = []
        for n in sizes:
            comp = [r["compromised"] for r in rows
                    if r["sweep"] == "size" and r["n_companies"] == n
                    and r["p_hidden"] == ps[0] and r["policy"] == "A"]
            counts = {f"e{i}": comp.count(f"e{i}") for i in range(n)}
            missing = [c for c, k in counts.items() if k == 0]
            drawn.append(
                f"- {n} companies: each company compromised "
                f"{min(counts.values())} to {max(counts.values())} times"
                + (f"; ⚠️ never drawn: {', '.join(missing)}" if missing
                   else f", including the last one (`e{n - 1}`)") + ".")
        lines += drawn + [""]
        tables = [
            ("Leaks (contaminated, not blocked)",
             lambda n, p, k: num(avg("size", n, p, k, "leaks"))),
            ("Collateral damage (healthy blocked)",
             lambda n, p, k: num(avg("size", n, p, k, "collateral"))),
            ("Recall", lambda n, p, k: pct(avg("size", n, p, k, "recall"))),
            ("Worlds with at least one leak (any operation / irreversible action)",
             lambda n, p, k: f"{pct(leak_share('size', n, p, k))} / "
                             f"{pct(leak_share('size', n, p, k, 'leaked_gates'))}"),
        ]
        for title, cell in tables:
            lines += [f"#### {title}", "", head, sep]
            for n in sizes:
                for p in ps:
                    lines.append(f"| {n} cos. · p = {p:g} | "
                                 + " | ".join(cell(n, p, k) for k in pols) + " |")
            lines.append("")

    if noises:
        lines += [
            "### Out-of-federation reception noise (policy D)",
            "",
            "5 companies, 300 operations. Share of receptions coming from outside "
            "the federation (legitimate, no token): "
            + ", ".join(f"{x:.0%}" for x in noises)
            + ". C is the baseline: noise only misleads it when the reception "
            "lands at the compromised company. Changing the noise also changes the "
            "generator's subsequent draws: worlds are not strictly identical from "
            "one row to the next, hence the small variations in C.",
            "",
            "| Noise · p | Healthy blocked C / D | Precision C / D | Recall C / D "
            "| Worlds with a leak C / D |",
            "|---|---|---|---|---|",
        ]
        for x in noises:
            for p in ps:
                c = lambda m: avg("noise", x, p, "C", m)  # noqa: E731
                d = lambda m: avg("noise", x, p, "D", m)  # noqa: E731
                lines.append(
                    f"| {x:.0%} · p = {p:g} | {num(c('collateral'))} / "
                    f"{num(d('collateral'))} | {pct(c('precision'))} / "
                    f"{pct(d('precision'))} | {pct(c('recall'))} / {pct(d('recall'))} "
                    f"| {pct(leak_share('noise', x, p, 'C'))} / "
                    f"{pct(leak_share('noise', x, p, 'D'))} |")
        lines.append("")

    # -- limitations and conclusions, computed by the script --
    lines += ["### Sensitivity: limitations and conclusions", ""]
    p0, pmax = ps[0], ps[-1]
    checks: list[tuple[str, bool]] = []
    if sizes:
        lines.append(
            "- **Inter-company relationships get denser with size** "
            "(unchanged generator): "
            + ", ".join(f"{avg('size', n, p0, 'A', 'mean_clients'):.2f} direct "
                        f"customer(s) per company at {n}" for n in sizes)
            + ". Partner blocking (B) therefore hits more companies "
            "as the chain grows; share of operations actually contaminated: "
            + ", ".join(
                f"{pct(avg('size', n, p0, 'A', 'contaminated') / avg('size', n, p0, 'A', 'records'))}"
                f" at {n}" for n in sizes) + ".")
        ratios = []
        for n in sizes:
            for p in ps:
                cb, cc = avg("size", n, p, "B", "collateral"), avg("size", n, p, "C", "collateral")
                ratios.append((n, p, cb, cc))
        lines.append(
            "- **Collateral B / C**: "
            + ", ".join(f"{cb / cc:.1f}× at {n} cos., p = {p:g}" if cc else
                        f"C = 0 at {n} cos., p = {p:g}" for n, p, cb, cc in ratios) + ".")
        checks.append(("Firebreak blocks fewer healthy operations than partner "
                       "blocking, at every size and every p",
                       all(cc < cb for _, _, cb, cc in ratios)))
        checks.append((f"Firebreak's recall is 100% at p = {p0:g} at every size",
                       all(abs(avg("size", n, p0, "C", "recall") - 1) < 1e-9
                           for n in sizes)))
        if pmax != p0:
            lines.append(
                f"- **Missing dependencies by size** (p = {pmax:g}): C recall "
                + ", ".join(f"{pct(avg('size', n, pmax, 'C', 'recall'))} at {n}"
                            for n in sizes)
                + "; B recall "
                + ", ".join(f"{pct(avg('size', n, pmax, 'B', 'recall'))} at {n}"
                            for n in sizes)
                + "; worlds where C lets an irreversible action through "
                + ", ".join(f"{pct(leak_share('size', n, pmax, 'C', 'leaked_gates'))}"
                            f" at {n}" for n in sizes) + ".")
            checks.append((f"at p = {pmax:g}, Firebreak's mean recall stays below "
                           "partner blocking's (accepted trade-off)",
                           all(avg("size", n, pmax, "C", "recall")
                               < avg("size", n, pmax, "B", "recall") for n in sizes)))
    if noises and pmax != p0:
        parts, gains = [], []
        for x in noises:
            dc = avg("noise", x, pmax, "D", "collateral") - avg("noise", x, pmax, "C", "collateral")
            dl = avg("noise", x, pmax, "C", "leaks") - avg("noise", x, pmax, "D", "leaks")
            gains.append(dl > 0)
            parts.append(f"at {x:.0%} noise, D catches {dl:.1f} leak(s) for "
                         f"{dc:+.1f} healthy blocked"
                         + (f", i.e. {dc / dl:.1f} healthy blocked per leak caught"
                            if dl > 0 else ""))
        lines.append(f"- **Cost of the \"missing provenance\" signal** (p = {pmax:g}): "
                     + "; ".join(parts) + ".")
        x0 = noises[0]
        lines.append(
            f"- At {x0:.0%} noise and p = {p0:g}, D blocks "
            f"{avg('noise', x0, p0, 'D', 'collateral') - avg('noise', x0, p0, 'C', 'collateral'):+.1f} "
            "more healthy operation(s) than C: with no out-of-federation reception, the "
            "signal has no false positives, which never happens in a real supply chain. "
            "D remains an upper bound.")
        checks.append((f"D catches leaks missed by C at p = {pmax:g} whatever the noise",
                       all(gains)))
    lines += ["", "Conclusions from `docs/fiche-defense.md` put to the test:", ""]
    lines += [f"- {'✅ unchanged' if ok else '⚠️ CHANGED'}: {text}." for text, ok in checks]
    lines.append("")
    return lines


# -- report ------------------------------------------------------------------


def pct(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{x:.1%}"


def num(x: float) -> str:
    return "n/a" if math.isnan(x) else f"{x:.1f}"


def fmt(metric: str, m: float, h: float) -> str:
    if math.isnan(m):
        return "n/a"
    if metric in PERCENT:
        return f"{m:.1%} ± {h:.1%}"
    if metric == "leaked_gates":
        return f"{m:.2f} ± {h:.2f}"
    return f"{m:.1f} ± {h:.1f}"


class Report:
    def __init__(self, rows: list[dict], ps: list[float]) -> None:
        self.rows, self.ps = rows, ps
        self.companies = sorted({r["compromised"] for r in rows},
                                key=lambda c: int(c.lstrip("e")))

    def vals(self, p: float, policy: str, metric: str,
             company: str | None = None) -> list[float]:
        return [float(r[metric]) for r in self.rows
                if r["p_hidden"] == p and r["policy"] == policy
                and (company is None or r["compromised"] == company)]

    def avg(self, p: float, policy: str, metric: str, company: str | None = None) -> float:
        return mean_ci(self.vals(p, policy, metric, company))[0]

    def table(self, header: str, cell) -> list[str]:
        out = ["| p | " + " | ".join(f"{k} — {v}" for k, v in POLICIES.items()) + " |",
               "|---|" + "---|" * len(POLICIES)]
        for p in self.ps:
            out.append(f"| {p:g} | " + " | ".join(cell(p, k) for k in POLICIES) + " |")
        return [f"## {header}", "", *out, ""]


def render(rows: list[dict], seeds: int, ps: list[float], n_companies: int,
           n_ops: int, command: str, sensitivity: list[str] | None = None) -> str:
    rep = Report(rows, ps)
    all_ids = [f"e{i}" for i in range(n_companies)]
    n_by_company = {c: len(rep.vals(ps[0], "A", "leaks", c)) for c in all_ids}
    excluded = [c for c, n in n_by_company.items() if n == 0]

    lines = [
        "# Firebreak benchmark — results",
        "",
        f"> Generated by `{command}`. Do not edit by hand.",
        "",
        f"{seeds} synthetic worlds per value of p ({n_companies} companies, "
        f"{n_ops} operations each, generator `src/firebreak/synth.py`). "
        "In each world, a company drawn at random from **all** of them "
        "(from the upstream supplier `e0` to the final customer "
        f"`e{n_companies - 1}`) is compromised from a time `since` onwards. "
        "**Ground truth**: its records issued after `since` and all their "
        "descendants through the *true* dependencies, except `verified` records. "
        "The engine only sees *recorded* dependencies: each true "
        "dependency (a record's input or a send between companies) is hidden "
        "with probability **p**. A hidden send leaves a reception with no "
        f"token or link. In addition, {P_EXTERNAL:.0%} of receptions come from outside "
        "the federation: they are legitimate, also have no token, and are therefore "
        "indistinguishable in the ledgers.",
        "",
        "Compromised companies drawn (at p = "
        f"{ps[0]:g}): " + ", ".join(f"`{c}` ({n})" for c, n in n_by_company.items())
        + ".",
        "",
    ]
    if excluded:
        lines += [f"⚠️ Never drawn as compromised: {', '.join(excluded)} "
                  "(too few seeds or modelling exclusion).", ""]
    else:
        lines += ["No company is excluded from the draw.", ""]
    lines += [
        "Policies, applied to the same world:",
        "",
        "- **A — Alert only**: everyone is warned, nothing is blocked.",
        "- **B — Block supplier + partners**: every record dated `since` "
        "or later at the compromised company and its direct customers is blocked "
        "(the \"cut off the supplier\" response).",
        "- **C — Firebreak**: the repository's engine (`Simulation.declare_compromise`), "
        "propagation over the recorded graph + signed alerts.",
        "- **D — Firebreak + caution** (benchmark only): C, plus quarantine "
        "of receptions **with no recorded provenance** (no token or link) dated "
        "`since` or later at the known direct partners of the compromised "
        "company, and of everything that depends on them in the recorded graph. "
        "D uses the \"missing provenance\" signal, read only from engine "
        "state: never the ground truth nor the \"hidden dependency\" flag.",
        "",
        "Values: mean ± 95% CI half-width (normal approximation). "
        "\"n/a\": undefined (A blocks nothing, so it has no precision).",
        "",
    ]

    for metric in METRICS:
        lines += rep.table(LABELS[metric], lambda p, k, m=metric: fmt(
            m, *mean_ci(rep.vals(p, k, m))[:2]))

    lines += rep.table(
        "Recall: distribution tail (mean / 5th percentile / worst case)",
        lambda p, k: " / ".join(pct(x) for x in (
            rep.avg(p, k, "recall"),
            percentile(rep.vals(p, k, "recall"), 0.05),
            min(clean(rep.vals(p, k, "recall")), default=NAN))))
    lines += rep.table(
        "Worlds with at least one leak (any operation / irreversible action)",
        lambda p, k: " / ".join(pct(share(rep.vals(p, k, m), lambda v: v > 0))
                                for m in ("leaks", "leaked_gates")))

    lines += ["## Breakdown by compromised company", "",
              "Cell: mean recall · healthy blocked · leaked irreversible actions "
              "(per-world means). `e0` is the furthest upstream.", ""]
    for p in ps:
        lines += [f"### p = {p:g}", "",
                  "| Compromised | Worlds | " + " | ".join(POLICIES) + " |",
                  "|---|---|" + "---|" * len(POLICIES)]
        for c in rep.companies:
            cells = [f"{pct(rep.avg(p, k, 'recall', c))} · "
                     f"{num(rep.avg(p, k, 'collateral', c))} · "
                     f"{rep.avg(p, k, 'leaked_gates', c):.2f}" for k in POLICIES]
            n = len(rep.vals(p, "A", "leaks", c))
            lines.append(f"| `{c}` | {n} | " + " | ".join(cells) + " |")
        lines.append("")

    sizes = rep.vals(ps[0], "A", "contaminated")
    gates = rep.vals(ps[0], "A", "contaminated_gates")
    mc, hc, _ = mean_ci(sizes)
    mg, _, _ = mean_ci(gates)
    mt, _, _ = mean_ci(rep.vals(ps[0], "A", "records"))
    lines += ["## Reading the results", "",
              f"- A world has {mt:.0f} records on average, of which {mc:.1f} ± {hc:.1f} "
              f"are actually contaminated, including {mg:.1f} irreversible actions "
              "(payment, shipment, production launch)."]
    for p in ps:
        cb, cc = rep.avg(p, "B", "collateral"), rep.avg(p, "C", "collateral")
        ratio = f"{cb / cc:.1f} times fewer" if cc else "no"
        lines.append(
            f"- p = {p:g}: Firebreak blocks {ratio} healthy operations than "
            f"partner blocking ({cc:.1f} vs {cb:.1f}), for a recall of "
            f"{pct(rep.avg(p, 'C', 'recall'))} vs {pct(rep.avg(p, 'B', 'recall'))} "
            f"and {rep.avg(p, 'C', 'leaked_gates'):.2f} leaked irreversible "
            f"action(s) vs {rep.avg(p, 'B', 'leaked_gates'):.2f}.")
    lines += [
        f"- **A** lets all contamination through (recall 0), including "
        f"{rep.avg(ps[0], 'A', 'leaked_gates'):.1f} irreversible actions per world "
        "on average: that is the cost of \"warning without acting\".",
        "- **B** does not depend on p (it uses no recorded dependency). "
        "It stops almost all contamination in these worlds, at the cost of "
        "blocking a large share of healthy activity.",
        "",
    ]

    # -- limitations, computed by the script --
    p0, pmax = ps[0], ps[-1]
    fp_c = rep.avg(p0, "C", "collateral")
    fp_origin = rep.avg(p0, "C", "fp_origin_rule")
    lines += ["## Limitations", ""]
    lines.append(
        f"- **Cautious origin rule.** At p = {p0:g}, Firebreak blocks {num(fp_c)} "
        f"healthy operations per world, {num(fp_origin)} of them "
        f"({pct(fp_origin / fp_c if fp_c else NAN)}) because of the origin rule: "
        "any data attributed to the compromised company after `since` is "
        "quarantined, even if it is a copy of earlier or verified data, "
        "along with whatever depends on it. This is a deliberately cautious engine "
        "choice, not a propagation error.")
    lines.append(
        f"- **Missing dependencies.** Firebreak only sees what is recorded. C's "
        f"recall drops from {pct(rep.avg(p0, 'C', 'recall'))} at p = {p0:g} to "
        f"{pct(rep.avg(pmax, 'C', 'recall'))} at p = {pmax:g} (5th percentile "
        f"{pct(percentile(rep.vals(pmax, 'C', 'recall'), 0.05))}, worst case "
        f"{pct(min(clean(rep.vals(pmax, 'C', 'recall')), default=NAN))}); at p = "
        f"{pmax:g}, {pct(share(rep.vals(pmax, 'C', 'leaked_gates'), lambda v: v > 0))} "
        "of worlds let at least one contaminated irreversible action through.")
    gain = rep.avg(pmax, "D", "recall") - rep.avg(pmax, "C", "recall")
    cost = rep.avg(pmax, "D", "collateral") - rep.avg(pmax, "C", "collateral")
    cost0 = rep.avg(p0, "D", "collateral") - rep.avg(p0, "C", "collateral")
    lines.append(
        "- **D uses the \"missing provenance\" signal.** At p = "
        f"{pmax:g}, D gains {gain * 100:+.1f} recall points over C for "
        f"{cost:+.1f} healthy operations blocked per world; at p = {p0:g}, "
        f"where nothing is hidden, D only costs the noise ({cost0:+.1f}) of "
        "legitimate out-of-federation receptions. Its gain rests on a "
        "simulator assumption: a missing send dependency always leaves a "
        "visible trace (an unattributed reception). A missing internal "
        "dependency leaves no trace, and D does not catch it. D's figures "
        "are therefore an **upper bound** for this signal.")
    lines += [
        "- Everything is simulated: the figures describe our supply chain model, "
        "not a real company.",
        "",
    ]
    return "\n".join(lines + (sensitivity or []))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=500)
    ap.add_argument("--p", default="0,0.1,0.2,0.3",
                    help="hidden-dependency rates, comma-separated")
    ap.add_argument("--companies", type=int, default=5)
    ap.add_argument("--ops", type=int, default=300)
    ap.add_argument("--csv", type=Path, default=ROOT / "bench" / "results.csv")
    ap.add_argument("--md", type=Path, default=ROOT / "docs" / "bench-results.md")
    ap.add_argument("--sizes", default="5,8,12",
                    help=f"sensitivity: numbers of companies ({OPS_PER_COMPANY} ops each)")
    ap.add_argument("--noise", default="0,0.1,0.3",
                    help="sensitivity: shares of out-of-federation receptions")
    ap.add_argument("--sens-p", default="0,0.3", help="sensitivity: values of p")
    ap.add_argument("--sens-csv", type=Path, default=None,
                    help="default: sensitivity.csv next to --csv")
    ap.add_argument("--no-sensitivity", action="store_true")
    args = ap.parse_args()
    ps = [float(x) for x in args.p.split(",")]
    floats = lambda txt: [float(x) for x in txt.split(",") if x]  # noqa: E731

    t0 = time.perf_counter()
    rows = run(args.seeds, ps, args.companies, args.ops)
    write_csv(rows, args.csv)
    command = (f"uv run python scripts/bench.py --seeds {args.seeds} --p {args.p}"
               + (f" --companies {args.companies}" if args.companies != 5 else "")
               + (f" --ops {args.ops}" if args.ops != 300 else ""))
    sensitivity = None
    if not args.no_sensitivity:
        sizes = [int(x) for x in args.sizes.split(",") if x]
        noises, sens_ps = floats(args.noise), floats(args.sens_p)
        sens_rows = run_sensitivity(args.seeds, sizes, noises, sens_ps)
        sens_csv = args.sens_csv or args.csv.with_name("sensitivity.csv")
        write_csv(sens_rows, sens_csv, SENS_FIELDS)
        sensitivity = render_sensitivity(sens_rows, sizes, noises, sens_ps)
        print(f"sensitivity: {len(sens_rows)} rows → {sens_csv}")
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render(rows, args.seeds, ps, args.companies, args.ops, command,
                              sensitivity))
    print(f"{len(rows)} rows in {time.perf_counter() - t0:.1f} s → {args.csv}, {args.md}")


if __name__ == "__main__":
    main()
