# FIREBREAK — Final interface brief

> For whoever builds the interface. The engine and the API are delivered (`docs/api.md`). This brief says **what we want to see, feel and handle**. It does not say which framework to use: pick whatever makes you fast. Due Sunday 12:00, freeze at 10:00.
>
> Read first: `docs/firebreak.md` (the idea), `docs/api.md` (the contract), `web/index.html` (the debug dashboard: not to be imitated, but it shows every call that works).

## 1. The intent in one sentence

An **incident control room** for a supply chain: beautiful like a 2026 product, readable like a cockpit, and so simple that a judge can grab the mouse and understand it alone. We pack real complexity (4 companies, 193 operations, a graph, signatures) into an interface that breathes.

Three adjectives to check on every screen: **tech, calm, provable.**

## 2. What the jury should feel, in order

1. **It's alive.** Activity flows between the companies. Nothing is static.
2. **It strikes.** One click, and the contamination spreads before your eyes. Precise red, not red everywhere.
3. **It holds.** Everything else keeps flowing. The big green numbers barely move.
4. **It proves.** A click on a blocked operation shows the exact path and the explanation.
5. **It heals.** One remediation, and the chain turns green again in a cascade, all the way to the partners.

If a screen does not serve one of these five emotions, cut it.

## 3. Art direction

### Mood

A monitoring center at night. Deep dark background, not pure black: a very desaturated midnight blue with, in the background, a **slow, fluid gradient** (blue, cyan, a hint of violet) that barely moves, like an aurora. It is the only "free" color in the interface: everything else is disciplined.

On top, **glass panels**: translucent background, strong backdrop blur, thin 1 px white border at 10 to 15% opacity, a very faint highlight at the top of the panel. The glass is not decoration: it sets the hierarchy. A glass panel = a surface you can interact with. The background = the living world.

Rule: **glass never carries long text**. Long text goes on a more opaque surface inside the panel, otherwise it is unreadable. Readability always beats the effect.

### Colors

| Role | Usage | Note |
|---|---|---|
| Background | desaturated midnight blue, animated gradient behind | never pure black |
| Glass | white at 6–10% + 20–40 px blur + 12% white border | one recipe, everywhere |
| Primary text | 92% off-white | |
| Secondary text | 55% white | |
| **Healthy / flowing** | mint green, bright but not neon | the reassuring color |
| **Tainted / blocked** | warm coral red | must be visible from afar, but never take more than 15% of the screen |
| **Recovering / released** | amber | transient |
| Accent | electric cyan | links, focus, verified signatures, primary buttons |

Four semantic colors, not one more. Never a color "to look nice": each color means something, and always the same thing. Text/background contrast ≥ 4.5:1 everywhere, including on glass: test with a contrast checker.

### Typography

- **Headings and numbers**: a crisp geometric grotesque (Space Grotesk, Geist, Inter Display or equivalent). Big numbers in **tabular-nums** so they don't jump when they increment.
- **Body text**: Inter or Geist, 15–16 px, line height 1.5.
- **Identifiers, tokens, hashes, timestamps**: a thin monospace (JetBrains Mono, Geist Mono). A truncated token `7d4b…5efba` in mono signals "crypto, verified".
- Few weights: regular, medium, semibold. No light on a dark background.
- Everything visible is **in English** (Mika's decision on 11/10, whole repo translated). Technical identifiers stay as they are.

Record the final choices in `design.md` (it is the design source of truth; it is empty today).

### Logo and name

- FIREBREAK, in the forestry sense: the strip you clear so the fire stops. The logo must tell that story: a clean stroke that **interrupts** a propagation. Ideas: a line of linked dots with one link cut by a vertical bar; or a stylized fire stopped by a line. Monochrome first (white), then cyan and red variants.
- The logo gets **one** animation: on load, the propagation animates, then the bar drops and stops it. Two seconds, once, never looping.
- Name in spaced capitals next to the logo in the header. Discreet subtitle: "Supply chain firewall".

### Icons

A **custom, consistent icon set**, 24 px, 1.5 px stroke, rounded caps, single stroke. No mixed packs. Icons needed:

| Icon | Meaning |
|---|---|
| order, shipping notice, certificate, invoice, payment, lot, shipment, receipt | the 8 `kind`s of a record |
| supplier, manufacturer, distributor, customer | the 4 companies (factory, warehouse, truck, shop) |
| gate | irreversible action: a padlock or a door |
| verified | a seal or a check mark in a shield |
| signed alert | an envelope with a seal; crossed-out variant for "signature rejected" |
| contamination | a drop or a wave |
| quarantine | a dotted circle |
| release / recovery | a return arrow |
| false alarm | a crossed-out bell |
| audit log | a chain (events are hash-chained) |
| with / without | two rectangles side by side |

Same stroke, same radius, same grid: any single icon should look like it came from the same hand as the others.

### Motion

Motion explains, it does not decorate. Three registers:

1. **Ambience**: the background gradient and the flow particles. Slow, continuous, never in the foreground.
2. **Causality**: propagation, alerts, release cascades. Paced by the SSE stream (`/api/events?speed=…`), 0.3 to 0.8 s per step. You must be able to **follow with your eyes** where the red comes from.
3. **Micro-interactions**: hover, focus, panels appearing. 150–250 ms, ease-out. Never bounce.

Default curve: `cubic-bezier(0.2, 0.8, 0.2, 1)`. Respect `prefers-reduced-motion`: particles stop, propagation becomes a fade.

**Loading and connections**: every network call has a visible state. Before the response: a glass **skeleton** with a soft light sweep, never a lone spinner. During a propagation: a thin cyan **progress line** under the header that follows the SSE steps. When a signed alert is verified: a brief cyan **pulse** on the envelope. On error: a glass toast, text in English, "Retry" button.

## 4. The screens

A single page, no navigation. The screens are **states** of the same scene. Nothing loads elsewhere.

### 4.1 Header

Logo, name, then on the right: the scenario selector (`GET /api/scenarios`, 4 choices: mixed, rib, cert, asn), the "Reset" button, and an AI indicator ("Bedrock" or "simulated", from `source` in `/explain`). The header is a thin, fixed glass panel.

### 4.2 The live dashboard (idle state)

- **Three numbers**, huge, top left on a glass panel: blocked operations, fraudulent payment blocked (€), payments still flowing (€). Source: `counters.global` from `/api/state` (`quarantined`, `amount_blocked`, `amount_flowing`). They **count up** with an animated counter during a propagation; tabular-nums prevent jumps.
- **The chain map**, in the center, 70% of the screen: four columns, supplier → manufacturer → distributor → customer. Each company is a glass panel with its icon and its counters (`counters.per_company`). Between them, **particles** flowing along the `cross: true` edges of `edges`. Inside each company, records are dots grouped by `kind`; we don't show 193 labels, we show 193 breathing dots.
- **The action button**, the only one, bottom center, glass with a coral red border: "Declare the supplier compromised since 14:00". The label comes from `scenarios[].compromise`. It is the only red button in the idle interface.

### 4.3 Propagation (incident state)

On click: `POST /api/compromise`, then open `GET /api/events?speed=0.6` and **play** the sequence:

| SSE step (`type`) | What you see |
|---|---|
| `declaration` | a red wave leaves the declared company; its panel gets a red border |
| `seed` | the record's dot turns red with a pulse; `rule` shown in a tooltip ("compromised source" or "verified alert") |
| `quarantine` | a red line runs from the `parent` to the record, then the record turns red |
| `gate_blocked` | same, plus the padlock icon closing; the "blocked" counter increments; the `text` appears in the event feed |
| `alert_sent` / `alert_received` | a sealed envelope travels along the cross-company edge (`alert.links`), cyan pulse on receipt if `verified`, red cross otherwise |
| `release`, `remediation`, `withdrawal` | same mechanics, in green or amber, in the other direction |

An **event feed** on the right, in glass, shows the `text` of each step in English, timestamped, with the type's icon. You can scroll back through the feed. A "Replay" button restarts the stream.

Healthy dots **keep flowing** throughout the incident. That is the message: we didn't shut down the factory.

### 4.4 With or without Firebreak (the demo's weapon)

"With vs without" button after a propagation. Two panels side by side, same scene, from `GET /api/compare`:

- Left, **without Firebreak**: "We cut off the supplier and its direct customers". Wide red: `blocked` (54) including `healthy_blocked` (42, collateral) hatched, and above all **`leaked`** (5): tainted dots that stayed green, marked with an alarm signal. Activity preserved: 76%.
- Right, **with Firebreak**: 17 blocked, 0 collateral, 0 leaks, 100% activity preserved.
- Below, a single comparison line: `precision` and `recall` as two gauges, and the euros.

The message fits in one image: **less breakage and less leakage**. Opening transition: the two panels slide in from the edges, 250 ms.

### 4.5 The proof (detail panel)

Click on a dot or a feed line: a glass side panel slides in from the right with `GET /api/records/{id}/explain`:

1. The label, the company, the timestamp, the `kind` with its icon, the status as a colored badge. The amount if `payload.amount`. The token in mono if `token`.
2. **The contamination path** (`path`): a small vertical timeline, one node per record, the seed at the top marked "origin", an arrow between each. This is the proof you show an auditor.
3. **The explanation** (`explanation`) on an opaque surface, in English, with a small "AI: Bedrock" or "AI: simulated" badge. A discreet subtitle reminds: "The decision comes from the graph. The AI explains."
4. **The recovery plan** (`remediation_plan`): three button-cards, label + `rationale` as secondary text. The click calls `POST /api/records/{id}/remediate` with the `action`, closes the panel and restarts the SSE stream to show the **release cascade** (green-amber climbing all the way to the customer, `release` alerts traveling).

The panel can be closed with Escape, a click outside, or a button. While loading: skeleton. The AI can take 2 to 4 s in Bedrock mode: show the path immediately (it comes from the already-known `record.taint_path`) and the explanation when it arrives.

### 4.6 False alarm

Small secondary "False alarm" button visible during an incident: `POST /api/compromise/withdraw`. Everything turns green again in a cascade. Show it to the jury if someone asks "what if you're wrong?".

### 4.7 Ingestion (bonus, if time allows)

Glass drop zone: drag in `assets/samples/facture-rib-modifie.pdf` or the `.eml`. `POST /api/ingest/document?company=…` returns a record proposal read by the AI; show it in a panel, "Confirm" button → `POST …/confirm`. The record appears on the map. Same for `epcis-sample.json` via `/api/ingest/epcis`. It shows "the lightweight component that records provenance" mentioned in the pitch.

### 4.8 Partner view (bonus)

A "View as: manufacturer / distributor / customer" switch. The map shows only that company's records; other companies' data is **blurred** (frosted glass, literally); you only see the alerts received, their verified signature, and the tokens. Visual proof that nothing leaks between companies.

## 5. Integration: what the API guarantees

- `GET /api/state` returns everything: `companies`, `records`, `edges`, `alerts`, `declarations`, `counters`. One call on load, then after each action (`compromise`, `remediate`, `withdraw`, `reset`, `confirm`) the response **is** the new complete state: no need to call `/state` again.
- The animated sequence comes from `/api/events` (SSE) or `/api/timeline` (same content, all at once). Replaying the steps in order reproduces the final state exactly: you can animate **then** show the state without inconsistency.
- "Operations still flowing" = `ok + released`. Euros only count payments (`kind == "payment"`), on purpose.
- `taint_path` is already in every record: the path displays without an extra call. `/explain` adds the explanation and the plan.
- Dates are in Paris time without a time zone. For `since`, `new Date().toISOString()` is accepted.
- CORS is open: the interface can run on a different port from the API.
- On 4xx/5xx: `{"detail": "…"}` in English, to show in the toast.

If something is missing from the API, **say so in `messages.md`** (`python3 scripts/messages.py send yann "…"`), and we'll add it. Don't work around the contract on the interface side.

## 6. 3-minute demo: the five moves

1. **Idle** (20 s): the chain is alive. "Four companies, 193 operations, everything running."
2. **Declare** (40 s): click, animated propagation, the three numbers go up. "17 blocked out of 193. Not 193."
3. **With vs without** (40 s): split screen. "Without us: 54 blocked, 42 for nothing, and 5 leaks. With us: 17, 0, 0."
4. **Prove** (40 s): click on the €5,210 payment. Path, explanation, modified bank details. "The graph decides, the AI explains."
5. **Heal** (30 s): remediate the lot receipt, green cascade all the way to the customer, signed release alerts. "And the partners are notified, without seeing our data."

Everything must work **without an external network** (simulated AI by default). Bedrock is a bonus if the connection holds.

## 7. Guardrails

- No data invented on the interface side: every number comes from the API.
- One glass recipe, one animation curve, four semantic colors. Consistency is what makes it polished.
- Tested at 1920×1080 (projector) and 1440×900 (laptop). No horizontal scroll. Big numbers stay readable at 5 m.
- Keyboard: Tab moves through panels, Escape closes, Enter triggers. Visible cyan focus.
- No heavy dependency just for an icon or an animation. If a graph library is used, it serves the graph; particles and panels are custom CSS/SVG/Canvas.
- Update `design.md` with the final values (colors, fonts, radii, glass recipe) so the pitch slides use the same language.
