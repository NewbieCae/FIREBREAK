"""Chiffres réels de la démo — les nombres cités dans docs/demo.md et le
pitch viennent d'ici, pas d'une copie à la main :

    uv run python -m firebreak.demo_figures
"""

from __future__ import annotations

from datetime import datetime

from .scenario import SCENARIOS, build_simulation


def main() -> None:
    sim = build_simulation("mixed")
    hint = sim.scenario["compromise"]
    since = datetime.fromisoformat(hint["since"])
    sim.declare_compromise(hint["company"], since)
    state = sim.state()
    g = state["counters"]["global"]
    blocked = [r for r in state["records"] if r["status"] == "quarantined"]
    gates = [r["id"] for r in blocked if r["gate"]]
    companies = sorted({r["company"] for r in blocked})
    hops = [(a["from"], a["to"]) for a in state["alerts"]]
    print("== Scénario mixed, fournisseur compromise depuis 14 h ==")
    print(f"records_total            = {g['total']}")
    print(f"operations_bloquees      = {g['quarantined']}")
    print(f"operations_qui_continuent = {g['ok'] + g['released']}")
    print(f"part_bloquee             = {g['quarantined'] / g['total']:.1%}")
    print(f"gates_bloques            = {g['gates_blocked']}  {gates}")
    print(f"paiements_bloques_eur    = {g['amount_blocked']:.0f}")
    print(f"paiements_qui_passent    = {g['amount_flowing']:.0f}")
    print(f"entreprises_touchees     = {len(companies)}  {companies}")
    print(f"alertes_signees          = {len(state['alerts'])}  {hops}")
    print(f"etapes_timeline          = {len(sim.timeline)}")
    v = sim.audit_verify()
    print(f"audit_integre            = {v['ok']}  "
          f"({sum(j['entries'] for j in v['journals'])} entrées)")
    pay = next(r for r in blocked if r["id"] == "m-pay-X")
    print(f"paiement_frauduleux      = {pay['payload']['amount']:.0f} € "
          f"(RIB {pay['payload']['rib']})")
    print()
    print("== Les 4 scénarios ==")
    for sid in SCENARIOS:
        s = build_simulation(sid)
        s.declare_compromise(hint["company"], since)
        c = s.state()["counters"]["global"]
        print(f"{sid:6s} bloqués {c['quarantined']:3d}/{c['total']:3d}  "
              f"gates {c['gates_blocked']}  "
              f"paiements bloqués {c['amount_blocked']:.0f} €")


if __name__ == "__main__":
    main()
