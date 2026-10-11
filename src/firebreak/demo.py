"""FIREBREAK demo mode: FIREBREAK_DEMO=1.

Default scenario ("mixed"), AI guaranteed in mock mode (no network
dependency), SSE replay speed tuned for the stage, and the stepper driven
by POST /api/demo/step (click or right arrow in the dashboard).
"""

from __future__ import annotations

import os

DEMO_MODE = os.environ.get("FIREBREAK_DEMO", "").strip() == "1"
DEMO_SCENARIO = "mixed"
# Pause between two SSE events in demo mode: slow enough to narrate,
# fast enough to fit the demo in 3 min.
DEMO_REPLAY_SPEED = 0.35

DEMO_CAPTIONS = [
    "Reset: \"Mixed attack\" scenario, a normal morning: "
    "all operations are flowing.",
    "Aciers Durand is declared compromised since 2 pm: the taint spreads "
    "from company to company, and only the tainted operations go into "
    "quarantine.",
    "With vs without Firebreak: on the left, the partner and its customers "
    "are cut off entirely; on the right, targeted quarantine: the same "
    "leaks handled, far less collateral damage.",
    "Explanation: the payment to the modified RIB is blocked; the evidence "
    "is the exact path in the dependency graph.",
    "Remediation: human approval of the verified goods receipt; the records "
    "that no longer depended on it are released and signed release alerts "
    "go out to the partners.",
    "Audit: each company's logs are hash-chained and intact; every "
    "decision can be replayed.",
]
DEMO_END_CAPTION = (
    "Demo finished: \"Reset\" (or a first call) to start over."
)


def demo_caption(step: int) -> str:
    if 0 <= step < len(DEMO_CAPTIONS):
        return DEMO_CAPTIONS[step]
    return DEMO_END_CAPTION
