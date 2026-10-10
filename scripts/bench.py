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


def write_csv(rows: list[dict], path: Path, fields: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if isinstance(v, float) and math.isnan(v) else
                            round(v, 6) if isinstance(v, float) else v)
                        for k, v in row.items()})


# -- sensibilité ---------------------------------------------------------------

OPS_PER_COMPANY = 60  # balayage de taille : même densité par registre
SENS_FIELDS = ["sweep", "n_companies", "n_ops", "p_external", "mean_clients", *FIELDS]


def run_sensitivity(seeds: int, sizes: list[int], noises: list[float],
                    ps: list[float]) -> list[dict]:
    """Deux balayages, mêmes graines que le banc principal :
    - « taille » : n entreprises, OPS_PER_COMPANY × n opérations, bruit par défaut ;
    - « bruit » : 5 entreprises, 300 opérations, part p_external de réceptions
      hors fédération."""
    configs = [("taille", n, OPS_PER_COMPANY * n, P_EXTERNAL) for n in sizes]
    configs += [("bruit", 5, 300, x) for x in noises]
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
        field = "n_companies" if sweep == "taille" else "p_external"
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
    seeds = len(vals("taille", sizes[0], ps[0], "A", "leaks")) if sizes else 0
    lines = [
        "## Sensibilité",
        "",
        f"Mêmes graines que le banc principal ({seeds} par configuration), "
        "entreprise compromise tirée parmi toutes, p = "
        + " et ".join(f"{p:g}" for p in ps) + ". Données : `bench/sensitivity.csv`.",
        "",
    ]
    if sizes:
        lines += [
            "### Taille de la chaîne",
            "",
            f"{OPS_PER_COMPANY} opérations par entreprise : "
            + ", ".join(f"{n} entreprises → {OPS_PER_COMPANY * n} opérations"
                        for n in sizes)
            + f". Bruit hors fédération : {P_EXTERNAL:.0%}.",
            "",
        ]
        drawn = []
        for n in sizes:
            comp = [r["compromised"] for r in rows
                    if r["sweep"] == "taille" and r["n_companies"] == n
                    and r["p_hidden"] == ps[0] and r["policy"] == "A"]
            counts = {f"e{i}": comp.count(f"e{i}") for i in range(n)}
            missing = [c for c, k in counts.items() if k == 0]
            drawn.append(
                f"- {n} entreprises : chaque entreprise compromise de "
                f"{min(counts.values())} à {max(counts.values())} fois"
                + (f" ; ⚠️ jamais tirées : {', '.join(missing)}" if missing
                   else f", y compris la dernière (`e{n - 1}`)") + ".")
        lines += drawn + [""]
        tables = [
            ("Fuites (contaminés non bloqués)",
             lambda n, p, k: num(avg("taille", n, p, k, "leaks"))),
            ("Dégâts collatéraux (sains bloqués)",
             lambda n, p, k: num(avg("taille", n, p, k, "collateral"))),
            ("Rappel", lambda n, p, k: pct(avg("taille", n, p, k, "recall"))),
            ("Mondes avec au moins une fuite (toute opération / action irréversible)",
             lambda n, p, k: f"{pct(leak_share('taille', n, p, k))} / "
                             f"{pct(leak_share('taille', n, p, k, 'leaked_gates'))}"),
        ]
        for title, cell in tables:
            lines += [f"#### {title}", "", head, sep]
            for n in sizes:
                for p in ps:
                    lines.append(f"| {n} entr. · p = {p:g} | "
                                 + " | ".join(cell(n, p, k) for k in pols) + " |")
            lines.append("")

    if noises:
        lines += [
            "### Bruit des réceptions hors fédération (politique D)",
            "",
            "5 entreprises, 300 opérations. Part des réceptions venues d'hors "
            "fédération (légitimes, sans jeton) : "
            + ", ".join(f"{x:.0%}" for x in noises)
            + ". C sert de référence : le bruit ne la trompe que si la réception "
            "arrive chez l'entreprise compromise. Changer le bruit change aussi les "
            "tirages suivants du générateur : les mondes ne sont pas strictement "
            "identiques d'une ligne à l'autre, d'où les petites variations de C.",
            "",
            "| Bruit · p | Sains bloqués C / D | Précision C / D | Rappel C / D "
            "| Mondes avec fuite C / D |",
            "|---|---|---|---|---|",
        ]
        for x in noises:
            for p in ps:
                c = lambda m: avg("bruit", x, p, "C", m)  # noqa: E731
                d = lambda m: avg("bruit", x, p, "D", m)  # noqa: E731
                lines.append(
                    f"| {x:.0%} · p = {p:g} | {num(c('collateral'))} / "
                    f"{num(d('collateral'))} | {pct(c('precision'))} / "
                    f"{pct(d('precision'))} | {pct(c('recall'))} / {pct(d('recall'))} "
                    f"| {pct(leak_share('bruit', x, p, 'C'))} / "
                    f"{pct(leak_share('bruit', x, p, 'D'))} |")
        lines.append("")

    # -- limites et conclusions, chiffrées par le script --
    lines += ["### Limites et conclusions de la sensibilité", ""]
    p0, pmax = ps[0], ps[-1]
    checks: list[tuple[str, bool]] = []
    if sizes:
        lines.append(
            "- **Les relations entre entreprises se densifient avec la taille** "
            "(générateur inchangé) : "
            + ", ".join(f"{avg('taille', n, p0, 'A', 'mean_clients'):.2f} client(s) "
                        f"direct(s) par entreprise à {n}" for n in sizes)
            + ". Le blocage des partenaires (B) touche donc plus d'entreprises "
            "quand la chaîne grandit ; part des opérations réellement contaminées : "
            + ", ".join(
                f"{pct(avg('taille', n, p0, 'A', 'contaminated') / avg('taille', n, p0, 'A', 'records'))}"
                f" à {n}" for n in sizes) + ".")
        ratios = []
        for n in sizes:
            for p in ps:
                cb, cc = avg("taille", n, p, "B", "collateral"), avg("taille", n, p, "C", "collateral")
                ratios.append((n, p, cb, cc))
        lines.append(
            "- **Collatéraux B / C** : "
            + ", ".join(f"{cb / cc:.1f}× à {n} entr., p = {p:g}" if cc else
                        f"C = 0 à {n} entr., p = {p:g}" for n, p, cb, cc in ratios) + ".")
        checks.append(("Firebreak bloque moins d'opérations saines que le blocage "
                       "des partenaires, à toutes les tailles et tous les p",
                       all(cc < cb for _, _, cb, cc in ratios)))
        checks.append((f"le rappel de Firebreak vaut 100 % à p = {p0:g} à toutes les tailles",
                       all(abs(avg("taille", n, p0, "C", "recall") - 1) < 1e-9
                           for n in sizes)))
        if pmax != p0:
            lines.append(
                f"- **Dépendances manquantes selon la taille** (p = {pmax:g}) : rappel C "
                + ", ".join(f"{pct(avg('taille', n, pmax, 'C', 'recall'))} à {n}"
                            for n in sizes)
                + " ; rappel B "
                + ", ".join(f"{pct(avg('taille', n, pmax, 'B', 'recall'))} à {n}"
                            for n in sizes)
                + " ; mondes où C laisse passer une action irréversible "
                + ", ".join(f"{pct(leak_share('taille', n, pmax, 'C', 'leaked_gates'))}"
                            f" à {n}" for n in sizes) + ".")
            checks.append((f"à p = {pmax:g}, le rappel moyen de Firebreak reste sous "
                           "celui du blocage des partenaires (compromis assumé)",
                           all(avg("taille", n, pmax, "C", "recall")
                               < avg("taille", n, pmax, "B", "recall") for n in sizes)))
    if noises and pmax != p0:
        parts, gains = [], []
        for x in noises:
            dc = avg("bruit", x, pmax, "D", "collateral") - avg("bruit", x, pmax, "C", "collateral")
            dl = avg("bruit", x, pmax, "C", "leaks") - avg("bruit", x, pmax, "D", "leaks")
            gains.append(dl > 0)
            parts.append(f"à {x:.0%} de bruit, D rattrape {dl:.1f} fuite(s) pour "
                         f"{dc:+.1f} sain(s) bloqué(s)"
                         + (f", soit {dc / dl:.1f} sain(s) bloqué(s) par fuite rattrapée"
                            if dl > 0 else ""))
        lines.append(f"- **Prix du signal « provenance manquante »** (p = {pmax:g}) : "
                     + " ; ".join(parts) + ".")
        x0 = noises[0]
        lines.append(
            f"- À {x0:.0%} de bruit et p = {p0:g}, D bloque "
            f"{avg('bruit', x0, p0, 'D', 'collateral') - avg('bruit', x0, p0, 'C', 'collateral'):+.1f} "
            "sain(s) de plus que C : sans réception hors fédération, le signal "
            "n'a aucun faux positif, ce qui n'arrive pas dans une vraie supply chain. "
            "D reste une borne haute.")
        checks.append((f"D rattrape des fuites de C à p = {pmax:g} quel que soit le bruit",
                       all(gains)))
    lines += ["", "Conclusions de `docs/fiche-defense.md` mises à l'épreuve :", ""]
    lines += [f"- {'✅ inchangée' if ok else '⚠️ MODIFIÉE'} : {text}." for text, ok in checks]
    lines.append("")
    return lines


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
           n_ops: int, command: str, sensitivity: list[str] | None = None) -> str:
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
    return "\n".join(lines + (sensitivity or []))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=500)
    ap.add_argument("--p", default="0,0.1,0.2,0.3",
                    help="taux de dépendances cachées, séparés par des virgules")
    ap.add_argument("--companies", type=int, default=5)
    ap.add_argument("--ops", type=int, default=300)
    ap.add_argument("--csv", type=Path, default=ROOT / "bench" / "results.csv")
    ap.add_argument("--md", type=Path, default=ROOT / "docs" / "bench-results.md")
    ap.add_argument("--sizes", default="5,8,12",
                    help=f"sensibilité : nombres d'entreprises ({OPS_PER_COMPANY} op. chacune)")
    ap.add_argument("--noise", default="0,0.1,0.3",
                    help="sensibilité : parts de réceptions hors fédération")
    ap.add_argument("--sens-p", default="0,0.3", help="sensibilité : valeurs de p")
    ap.add_argument("--sens-csv", type=Path, default=None,
                    help="défaut : sensitivity.csv à côté de --csv")
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
        print(f"sensibilité : {len(sens_rows)} lignes → {sens_csv}")
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render(rows, args.seeds, ps, args.companies, args.ops, command,
                              sensitivity))
    print(f"{len(rows)} lignes en {time.perf_counter() - t0:.1f} s → {args.csv}, {args.md}")


if __name__ == "__main__":
    main()
