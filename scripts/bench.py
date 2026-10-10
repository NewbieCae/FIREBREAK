"""Banc d'essai Firebreak : 4 politiques × N graines × taux de dépendances cachées.

    uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3

Écrit bench/results.csv (une ligne par graine, p et politique) et
docs/bench-results.md (moyenne ± IC 95 %, pire cas, 5e centile, part des
mondes avec fuite, ventilation par entreprise compromise, limites).
Aucun appel réseau ni LLM.
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
    "leaks": "Fuites (contaminés non bloqués)",
    "leaked_gates": "Actions irréversibles fuitées (contaminées, gate, non bloquées)",
    "collateral": "Dégâts collatéraux (sains bloqués)",
    "healthy_preserved": "Activité saine préservée",
    "precision": "Précision",
    "recall": "Rappel",
}
PERCENT = {"healthy_preserved", "precision", "recall"}
NAN = float("nan")


# -- statistiques ------------------------------------------------------------


def clean(values: list[float]) -> list[float]:
    return [v for v in values if not math.isnan(v)]


def mean_ci(values: list[float]) -> tuple[float, float, int]:
    """Moyenne et demi-largeur de l'IC 95 % (approximation normale),
    en ignorant les NaN (métrique non définie)."""
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
    """Centile q ∈ [0, 1], interpolation linéaire, NaN ignorés."""
    xs = sorted(clean(values))
    if not xs:
        return NAN
    pos = q * (len(xs) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def share(values: list[float], pred) -> float:
    return sum(1 for v in values if pred(v)) / len(values) if values else NAN


# -- exécution ---------------------------------------------------------------


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


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if isinstance(v, float) and math.isnan(v) else
                            round(v, 6) if isinstance(v, float) else v)
                        for k, v in row.items()})


# -- rapport -----------------------------------------------------------------


def pct(x: float) -> str:
    return "n/d" if math.isnan(x) else f"{x:.1%}"


def num(x: float) -> str:
    return "n/d" if math.isnan(x) else f"{x:.1f}"


def fmt(metric: str, m: float, h: float) -> str:
    if math.isnan(m):
        return "n/d"
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
           n_ops: int, command: str) -> str:
    rep = Report(rows, ps)
    all_ids = [f"e{i}" for i in range(n_companies)]
    n_by_company = {c: len(rep.vals(ps[0], "A", "leaks", c)) for c in all_ids}
    excluded = [c for c, n in n_by_company.items() if n == 0]

    lines = [
        "# Banc d'essai Firebreak — résultats",
        "",
        f"> Généré par `{command}`. Ne pas éditer à la main.",
        "",
        f"{seeds} mondes synthétiques par valeur de p ({n_companies} entreprises, "
        f"{n_ops} opérations chacun, générateur `src/firebreak/synth.py`). "
        "Dans chaque monde, une entreprise tirée au hasard parmi **toutes** "
        "(du fournisseur amont `e0` au client final "
        f"`e{n_companies - 1}`) est compromise à partir d'une heure `since`. "
        "**Vérité terrain** : ses records émis après `since` et tous leurs "
        "descendants par les *vraies* dépendances, sauf les records `verified`. "
        "Le moteur ne voit que les dépendances *enregistrées* : chaque vraie "
        "dépendance (entrée d'un record ou envoi entre entreprises) est cachée "
        "avec la probabilité **p**. Un envoi caché laisse une réception sans "
        f"jeton ni lien. En plus, {P_EXTERNAL:.0%} des réceptions viennent d'hors "
        "fédération : légitimes, elles aussi sans jeton, donc indiscernables "
        "dans les registres.",
        "",
        "Entreprises compromises tirées (à p = "
        f"{ps[0]:g}) : " + ", ".join(f"`{c}` ({n})" for c, n in n_by_company.items())
        + ".",
        "",
    ]
    if excluded:
        lines += [f"⚠️ Jamais tirées comme compromises : {', '.join(excluded)} "
                  "(trop peu de graines ou exclusion de modélisation).", ""]
    else:
        lines += ["Aucune entreprise n'est exclue du tirage.", ""]
    lines += [
        "Politiques, appliquées au même monde :",
        "",
        "- **A — Alerte seule** : on prévient tout le monde, rien n'est bloqué.",
        "- **B — Blocage fournisseur + partenaires** : tout record daté de `since` "
        "ou après chez l'entreprise compromise et ses clients directs est bloqué "
        "(la réponse « on coupe le fournisseur »).",
        "- **C — Firebreak** : le moteur du dépôt (`Simulation.declare_compromise`), "
        "propagation sur le graphe enregistré + alertes signées.",
        "- **D — Firebreak + prudence** (banc uniquement) : C, plus la quarantaine "
        "des réceptions **sans provenance enregistrée** (sans jeton ni lien) datées "
        "de `since` ou après chez les partenaires directs connus de l'entreprise "
        "compromise, et de tout ce qui en dépend dans le graphe enregistré. "
        "D exploite le signal « provenance manquante », lu uniquement dans l'état "
        "du moteur : jamais la vérité terrain ni le drapeau « dépendance cachée ».",
        "",
        "Valeurs : moyenne ± demi-largeur de l'IC 95 % (approximation normale). "
        "« n/d » : non défini (A ne bloque rien, donc pas de précision).",
        "",
    ]

    for metric in METRICS:
        lines += rep.table(LABELS[metric], lambda p, k, m=metric: fmt(
            m, *mean_ci(rep.vals(p, k, m))[:2]))

    lines += rep.table(
        "Rappel : queue de distribution (moyenne / 5e centile / pire cas)",
        lambda p, k: " / ".join(pct(x) for x in (
            rep.avg(p, k, "recall"),
            percentile(rep.vals(p, k, "recall"), 0.05),
            min(clean(rep.vals(p, k, "recall")), default=NAN))))
    lines += rep.table(
        "Mondes avec au moins une fuite (toute opération / action irréversible)",
        lambda p, k: " / ".join(pct(share(rep.vals(p, k, m), lambda v: v > 0))
                                for m in ("leaks", "leaked_gates")))

    lines += ["## Ventilation par entreprise compromise", "",
              "Cellule : rappel moyen · sains bloqués · actions irréversibles fuitées "
              "(moyennes par monde). `e0` est le plus en amont.", ""]
    for p in ps:
        lines += [f"### p = {p:g}", "",
                  "| Compromise | Mondes | " + " | ".join(POLICIES) + " |",
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
    lines += ["## Lecture", "",
              f"- Un monde compte en moyenne {mt:.0f} records, dont {mc:.1f} ± {hc:.1f} "
              f"réellement contaminés, parmi lesquels {mg:.1f} actions irréversibles "
              "(paiement, expédition, lancement de production)."]
    for p in ps:
        cb, cc = rep.avg(p, "B", "collateral"), rep.avg(p, "C", "collateral")
        ratio = f"{cb / cc:.1f} fois moins" if cc else "aucune"
        lines.append(
            f"- p = {p:g} : Firebreak bloque {ratio} d'opérations saines que le "
            f"blocage des partenaires ({cc:.1f} contre {cb:.1f}), pour un rappel de "
            f"{pct(rep.avg(p, 'C', 'recall'))} contre {pct(rep.avg(p, 'B', 'recall'))} "
            f"et {rep.avg(p, 'C', 'leaked_gates'):.2f} action(s) irréversible(s) "
            f"fuitée(s) contre {rep.avg(p, 'B', 'leaked_gates'):.2f}.")
    lines += [
        f"- **A** laisse passer toute la contamination (rappel 0), dont "
        f"{rep.avg(ps[0], 'A', 'leaked_gates'):.1f} actions irréversibles par monde "
        "en moyenne : c'est le coût de « prévenir sans agir ».",
        "- **B** ne dépend pas de p (elle n'utilise aucune dépendance enregistrée). "
        "Elle arrête presque toute la contamination dans ces mondes, au prix d'une "
        "grosse part d'activité saine bloquée.",
        "",
    ]

    # -- limites, chiffrées par le script --
    p0, pmax = ps[0], ps[-1]
    fp_c = rep.avg(p0, "C", "collateral")
    fp_origin = rep.avg(p0, "C", "fp_origin_rule")
    lines += ["## Limites", ""]
    lines.append(
        f"- **Règle d'origine prudente.** À p = {p0:g}, Firebreak bloque {num(fp_c)} "
        f"opérations saines par monde, dont {num(fp_origin)} "
        f"({pct(fp_origin / fp_c if fp_c else NAN)}) à cause de la règle d'origine : "
        "toute donnée attribuée à l'entreprise compromise après `since` est mise "
        "en quarantaine, même si c'est la copie d'une donnée antérieure ou vérifiée, "
        "ainsi que ce qui en dépend. C'est un choix prudent du moteur, pas une erreur "
        "de propagation.")
    lines.append(
        f"- **Dépendances manquantes.** Firebreak ne voit que ce qui est tracé. Le "
        f"rappel de C passe de {pct(rep.avg(p0, 'C', 'recall'))} à p = {p0:g} à "
        f"{pct(rep.avg(pmax, 'C', 'recall'))} à p = {pmax:g} (5e centile "
        f"{pct(percentile(rep.vals(pmax, 'C', 'recall'), 0.05))}, pire cas "
        f"{pct(min(clean(rep.vals(pmax, 'C', 'recall')), default=NAN))}) ; à p = "
        f"{pmax:g}, {pct(share(rep.vals(pmax, 'C', 'leaked_gates'), lambda v: v > 0))} "
        "des mondes laissent passer au moins une action irréversible contaminée.")
    gain = rep.avg(pmax, "D", "recall") - rep.avg(pmax, "C", "recall")
    cost = rep.avg(pmax, "D", "collateral") - rep.avg(pmax, "C", "collateral")
    cost0 = rep.avg(p0, "D", "collateral") - rep.avg(p0, "C", "collateral")
    lines.append(
        "- **D exploite le signal « provenance manquante ».** À p = "
        f"{pmax:g}, D récupère {gain * 100:+.1f} points de rappel sur C pour "
        f"{cost:+.1f} opérations saines bloquées par monde ; à p = {p0:g}, "
        f"où rien n'est caché, D ne coûte que le bruit ({cost0:+.1f}) des "
        "réceptions légitimes d'hors fédération. Son gain repose sur une "
        "hypothèse du simulateur : une dépendance d'envoi manquante laisse "
        "toujours une trace visible (une réception non attribuée). Une "
        "dépendance interne manquante ne laisse aucune trace, et D ne la "
        "rattrape pas. Les chiffres de D sont donc une **borne haute** pour "
        "ce signal.")
    lines += [
        "- Tout est simulé : les chiffres décrivent notre modèle de supply chain, "
        "pas une entreprise réelle.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=500)
    ap.add_argument("--p", default="0,0.1,0.2,0.3",
                    help="taux de dépendances cachées, séparés par des virgules")
    ap.add_argument("--companies", type=int, default=5)
    ap.add_argument("--ops", type=int, default=300)
    ap.add_argument("--csv", type=Path, default=ROOT / "bench" / "results.csv")
    ap.add_argument("--md", type=Path, default=ROOT / "docs" / "bench-results.md")
    args = ap.parse_args()
    ps = [float(x) for x in args.p.split(",")]

    t0 = time.perf_counter()
    rows = run(args.seeds, ps, args.companies, args.ops)
    write_csv(rows, args.csv)
    command = (f"uv run python scripts/bench.py --seeds {args.seeds} --p {args.p}"
               + (f" --companies {args.companies}" if args.companies != 5 else "")
               + (f" --ops {args.ops}" if args.ops != 300 else ""))
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render(rows, args.seeds, ps, args.companies, args.ops, command))
    print(f"{len(rows)} lignes en {time.perf_counter() - t0:.1f} s → {args.csv}, {args.md}")


if __name__ == "__main__":
    main()
