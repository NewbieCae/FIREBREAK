"""Real demo figures: the numbers quoted in docs/demo.md and the pitch
come from here, not from a manual copy:

    uv run python -m firebreak.demo_figures
"""

from __future__ import annotations

from datetime import datetime

from .compare import compare
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
    print("== Mixed scenario, supplier compromised since 2 pm ==")
    print(f"records_total            = {g['total']}")
    print(f"blocked_operations       = {g['quarantined']}")
    print(f"flowing_operations       = {g['ok'] + g['released']}")
    print(f"blocked_share            = {g['quarantined'] / g['total']:.1%}")
    print(f"gates_blocked            = {g['gates_blocked']}  {gates}")
    print(f"blocked_payments_eur     = {g['amount_blocked']:.0f}")
    print(f"flowing_payments_eur     = {g['amount_flowing']:.0f}")
    print(f"companies_hit            = {len(companies)}  {companies}")
    print(f"signed_alerts            = {len(state['alerts'])}  {hops}")
    print(f"timeline_steps           = {len(sim.timeline)}")
    v = sim.audit_verify()
    print(f"audit_intact             = {v['ok']}  "
          f"({sum(j['entries'] for j in v['journals'])} entries)")
    pay = next(r for r in blocked if r["id"] == "m-pay-X")
    print(f"fraudulent_payment       = {pay['payload']['amount']:.0f} € "
          f"(RIB {pay['payload']['rib']})")
    print()
    print("== With vs without Firebreak (policy C vs B) ==")
    cmp = compare(sim)
    for side in ("without", "with"):
        m = cmp[side]
        print(f"{m['policy']:4s} {m['title']:17s} blocked {m['blocked']:3d}  "
              f"healthy blocked {m['healthy_blocked']:3d}  leaks {m['leaked']}  "
              f"gates {m['gates_blocked']}  "
              f"activity preserved {m['activity_preserved_pct']:.1f} %")
    ratio = cmp["healthy_blocked_ratio"]
    print(f"ratio                    = "
          f"{f'{ratio:.1f}x' if ratio is not None else 'infinite (0 healthy blocked with Firebreak)'}")
    print()
    print("== The 6 scenarios ==")
    for sid in SCENARIOS:
        s = build_simulation(sid)
        s.declare_compromise(hint["company"], since)
        c = s.state()["counters"]["global"]
        print(f"{sid:6s} blocked {c['quarantined']:3d}/{c['total']:3d}  "
              f"gates {c['gates_blocked']}  "
              f"payments blocked {c['amount_blocked']:.0f} €")


if __name__ == "__main__":
    main()
