"""Banc d'essai Firebreak : 3 politiques × N graines × taux de dépendances cachées.

    uv run python scripts/bench.py --seeds 500 --p 0,0.1,0.2,0.3

Écrit bench/results.csv (une ligne par graine, p et politique) et
docs/bench-results.md (moyenne ± IC 95 % par politique et par p).
Aucun appel réseau ni LLM.
"""

from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

from firebreak.synth import POLICIES, generate, run_policies

ROOT = Path(__file__).resolve().parent.parent
METRICS = ["leaks", "collateral", "healthy_preserved", "precision", "recall"]
FIELDS = ["seed", "p_hidden", "policy", "compromised", "records", "contaminated",
          "blocked", *METRICS]
LABELS = {
    "leaks": "Fuites (contaminés non bloqués)",
    "collateral": "Dégâts collatéraux (sains bloqués)",
    "healthy_preserved": "Activité saine préservée",
    "precision": "Précision",
    "recall": "Rappel",
}
PERCENT = {"healthy_preserved", "precision", "recall"}


def mean_ci(values: list[float]) -> tuple[float, float, int]:
    """Moyenne et demi-largeur de l'IC 95 % (approximation normale),
    en ignorant les NaN (métrique non définie)."""
    xs = [v for v in values if not math.isnan(v)]
    n = len(xs)
    if n == 0:
        return math.nan, math.nan, 0
    m = sum(xs) / n
    if n == 1:
        return m, 0.0, 1
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, 1.96 * math.sqrt(var / n), n


def run(seeds: int, ps: list[float], n_companies: int, n_ops: int) -> list[dict]:
    rows = []
    for p in ps:
        for seed in range(seeds):
            world = generate(seed, n_companies=n_companies, n_ops=n_ops, p_hidden=p)
            for policy, metrics in run_policies(world).items():
                rows.append({"seed": seed, "p_hidden": p, "policy": policy,
                             "compromised": world.compromised, **metrics})
    return rows


def fmt(metric: str, m: float, h: float) -> str:
    if math.isnan(m):
        return "n/d"
    if metric in PERCENT:
        return f"{m:.1%} ± {h:.1%}"
    return f"{m:.1f} ± {h:.1f}"


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if isinstance(v, float) and math.isnan(v) else
                            round(v, 6) if isinstance(v, float) else v)
                        for k, v in row.items()})


def write_markdown(rows: list[dict], path: Path, seeds: int, ps: list[float],
                   n_companies: int, n_ops: int, command: str) -> None:
    lines = [
        "# Banc d'essai Firebreak — résultats",
        "",
        f"> Généré par `{command}`. Ne pas éditer à la main.",
        "",
        f"{seeds} mondes synthétiques par valeur de p ({n_companies} entreprises, "
        f"{n_ops} opérations chacun, générateur `src/firebreak/synth.py`). "
        "Dans chaque monde, une entreprise qui a des clients est compromise à partir "
        "d'une heure `since`. **Vérité terrain** : ses records émis après `since` et "
        "tous leurs descendants par les *vraies* dépendances, sauf les records "
        "`verified`. Le moteur ne voit que les dépendances *enregistrées* : chaque "
        "vraie dépendance (entrée d'un record ou envoi entre entreprises) est cachée "
        "avec la probabilité **p**.",
        "",
        "Politiques, appliquées au même monde :",
        "",
        "- **A — Alerte seule** : on prévient tout le monde, rien n'est bloqué.",
        "- **B — Blocage fournisseur + partenaires** : tout record daté de `since` "
        "ou après chez l'entreprise compromise et ses clients directs est bloqué "
        "(la réponse « on coupe le fournisseur »).",
        "- **C — Firebreak** : le moteur du dépôt (`Simulation.declare_compromise`), "
        "propagation sur le graphe enregistré + alertes signées.",
        "",
        "Valeurs : moyenne ± demi-largeur de l'IC 95 % (approximation normale). "
        "« n/d » : non défini (A ne bloque rien, donc pas de précision).",
        "",
    ]
    for metric in METRICS:
        lines += [f"## {LABELS[metric]}", "",
                  "| p | " + " | ".join(f"{k} — {v}" for k, v in POLICIES.items()) + " |",
                  "|---|" + "---|" * len(POLICIES)]
        for p in ps:
            cells = []
            for policy in POLICIES:
                vals = [r[metric] for r in rows
                        if r["p_hidden"] == p and r["policy"] == policy]
                m, h, _ = mean_ci(vals)
                cells.append(fmt(metric, m, h))
            lines.append(f"| {p:g} | " + " | ".join(cells) + " |")
        lines.append("")

    sizes = [r for r in rows if r["policy"] == "A" and r["p_hidden"] == ps[0]]
    mc, hc, _ = mean_ci([r["contaminated"] for r in sizes])
    mt, _, _ = mean_ci([r["records"] for r in sizes])
    lines += [
        "## Lecture",
        "",
        f"- Un monde compte en moyenne {mt:.0f} records, dont {mc:.1f} ± {hc:.1f} "
        "réellement contaminés.",
        "- **A** laisse passer toute la contamination (rappel 0) : c'est le coût de "
        "« prévenir sans agir ».",
        "- **B** arrête une grande partie de la contamination proche, mais bloque "
        "une grosse part d'activité saine chez les partenaires et laisse fuir ce "
        "qui a déjà dépassé le premier rang.",
        "- **C** suit la contamination sur tout le graphe : à p = 0, rappel de 100 %. "
        "Ses faux positifs viennent de la règle d'origine du moteur : toute donnée "
        "reçue de l'entreprise compromise après `since` est mise en quarantaine, "
        "même si c'est la copie d'un record antérieur ou vérifié (choix prudent). "
        "Quand p augmente, les dépendances non enregistrées font baisser le rappel : "
        "c'est la limite honnête de l'approche — Firebreak ne voit que ce qui est "
        "tracé.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


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
    write_markdown(rows, args.md, args.seeds, ps, args.companies, args.ops, command)
    print(f"{len(rows)} lignes en {time.perf_counter() - t0:.1f} s → {args.csv}, {args.md}")


if __name__ == "__main__":
    main()
