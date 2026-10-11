# FIREBREAK — quality incidents: defective lot and product recall

> Sheet for the pitch and the demo. Same rule as `docs/pitch-firebreak.md`: the only numbers are those on screen (`lot` and `recall` scenarios, deterministic) or measurements cited here with their source.

## The idea in one sentence

A quality problem isn't handled by cutting off a supplier: you isolate **the lot at fault**, case by case, on a human decision — and the alert can travel **in both directions** along the chain.

## Why it matters

- It's the same problem as cyber ("what depends on this data?"), but it happens **every day** in industry: material defect, fake certificate, late quality analysis.
- Real cases, to cite as public examples: **Kobe Steel (2017)**, falsified strength data on specific lots of aluminum and copper, ~688 customers affected according to the company's investigation; **AOG Technics (2023)**, CFM56 engine parts sold with fake certificates, traced engine by engine (68 to 126 engines depending on the source). In both cases, the question was: *which products contain those lots?*
- It widens the market: quality and product recalls, not just cybersecurity.

## The two directions

| Direction | Example | What Firebreak does |
|---|---|---|
| **Downstream** | The manufacturer's incoming inspection finds a defect on a coil from the supplier. | It declares **that lot** suspect: only that lot and what depends on it is isolated, at its site and then at its customers (signed alerts). The supplier, its other lots and its invoices keep going. |
| **Upstream** | The customer sees a failure on a construction site, on a product delivered long ago. | It sends a **signed quality report** to the previous link, which finds its own operations, decides (confirm or reject), and passes it upstream in turn. The manufacturer analyzes the genealogy and identifies the coil at fault: all products made with it, even those already shipped, are isolated. |

A report blocks nothing on its own: the recipient always decides. It contains only opaque tokens, never business data.

## Demo flow (`recall` scenario, ~60 s)

"Quality (debug)" panel of the dashboard, or the final interface (`/app/`, `recall` scenario: the action bar walks through the steps with the right arrow).

1. **Idle**: "A chain that's running, nobody is compromised."
2. **The customer reports** a failure on the delivery of lot LOT-503 → signed report to the distributor. "The customer doesn't know about the coil: it reports what it received."
3. **The distributor confirms** → the customer's delivery and payment for this lot are put on hold. It **passes the report upstream** to the manufacturer.
4. **The manufacturer analyzes**: the screen lists the possible causes (coil COIL-103, documents received from the supplier) with the scope of each. The analyst picks the coil. "It's the human who identifies the cause."
5. **Coil declared suspect** → the sibling lot LOT-A30, made with the same coil and already shipped, is isolated too. The other lots keep going.
6. **Report to the supplier**, which confirms. "At no point was the supplier blacklisted: its other deliveries and its invoices go through."
7. If the chain is active: "Every report, every decision and every acknowledgment is anchored on our Avalanche L1."

Numbers shown by the demo (`recall` scenario, to be read on screen): 20 operations isolated in total at the end of the flow.

## Pitch lines

- "A quality defect is no reason to cut off a supplier. Firebreak isolates the lot, not the company."
- "The alert also travels upstream: from the construction site to the coil, link by link, and each one decides for itself."
- "What we do for a cyberattack, we do for a product recall: same graph, same proof."

## Likely questions

- **"Who decides a lot is suspect?"** A human (quality control, analyst). Firebreak computes the scope and proposes causes; it declares nothing on its own.
- **"What if the report is abusive?"** The recipient rejects it: nothing is blocked on its side. Reports are signed and anchored: we know who reported what, and when.
- **"Does the supplier see my data?"** No: it receives tokens that only it can link to its own shipments.
- **"What about an incoming inspection that was already approved?"** An explicit declaration takes precedence: a defect discovered afterwards reopens the case.

## Measurements on the real L1 (`recall` scenario, 11/10 around 04:00)

Full flow (customer → distributor → manufacturer → supplier): 25 anchored proofs, 0 failures on the first run, local and Avalanche verification passing; the API responds in 0.1 s for each action, the anchoring queue drains in ~86 s after optimization (~130 s before), 25/25 confirmed (remaining limit: throughput of the hosted node). Details: `docs/avalanche/pitch.md`.

## Limits to state

- Everything is simulated; scenarios are deterministic.
- Genealogy is only reliable if transformations (consumed lots → produced lot) are recorded.
- No quantified "quality" measurement yet in Céline's test bench (it covers company compromises).

## Incoming stock control: prevent rather than contain

When a delivery is received, Firebreak gives the lot a **confidence score out of 100**, cross-checking the reference data (open order?, right part and bill of materials?, quantity, date, certificate present and consistent, certificate number in the usual sequence, new lot number, bank details (RIB) matching the record, ongoing alerts). Every point deducted has its reason, shown in plain language. **Below 80, the lot is put on hold**: nothing that depends on it can move forward until a human has accepted it (the lot becomes trusted) or rejected it (the lot stays isolated and a signed report goes to the supplier).

Results on the scenarios (deterministic): the 7 morning deliveries score 100/100; the trapped coil from the mixed attack scores **30/100** (unknown order BC-9999, out-of-sequence certificate, modified bank details); the phantom delivery **40/100**; the fake certificate **55/100** (grade S355 instead of S235). **In all three attacks, the trapped lot would have been stopped at receipt, before any production.**

Pitch line: "Before a trapped lot even enters stock, Firebreak scores it, explains why it has doubts, and puts it on hold. The human decides."

Answer to "Where's the AI?": the score comes from explainable rules (reproducible, defensible before an auditor); the AI writes the explanation and reads messy documents. It never decides.

Measurement on the real L1 (11/10, 05:30, mixed scenario): receipt screening in 32 ms, rejection of the trapped coil (report to the supplier) and acceptance of the legitimate delivery; 16 proofs anchored in ~25 s, 0 failures, local and Avalanche verification passing.
