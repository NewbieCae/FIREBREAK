# Design System — FIREBREAK

> Design source of truth. Kept in sync with the final interface `web/app/` (served at `http://localhost:8000/app/`).
> The pitch slides reuse these values exactly. Three adjectives to check on every screen: **sober, high-contrast, provable**.
> Redesign of 11/10 (04:45): we leave the "neon / glowing glass" aesthetic for a startup-keynote register — deep black, a horizon of grainy light, no unnecessary boxes.

## Principles

- **Deep black, a single light**: background `#050506`, a horizon of grainy blue light rising from the bottom of the screen. It turns coral while an incident is in progress (1.6 s transition), then goes back to blue.
- **No boxes**: companies, figures and the feed float, separated by thin rules (1 px, white at 8 to 16%). A solid surface exists only for what you interact with: drawer, menus, action dock, toasts.
- **Healthy is neutral**: an operation that keeps running is a white dot. Only the abnormal carries a colour (coral = blocked, amber = recovering, blue = verified proof).
- **No glow**: no halo, no `text-shadow`, no neon. Contrast comes from black and white.
- **Frameless icons**: thin stroke, placed directly on the background.
- **No invented figures**: every number displayed comes from the API (`docs/api.md`); benchmark figures come from `docs/bench-results.md`.

## Colours

| Role | Value | Usage |
|---|---|---|
| Background | `#050506` | everywhere, never a background gradient apart from the horizon |
| Solid surface | `#0d0e11` + 8% white rule | drawer, menus, toasts, "with vs without" panels |
| Inner surface | 3.5% white + 8% white rule | facts, explanation, recovery plan |
| Horizon | blue `rgba(170,200,255,.62)` → `rgba(70,112,255,.48)` → `rgba(24,48,190,.24)`; coral incident variant `rgba(255,85,69,.34)` | blurred ellipse (30 px) below the bottom of the screen, 38 s drift |
| Grain | SVG fractal noise, 11%, `mix-blend-mode: overlay` | over the whole background |
| **Healthy / running** | `#f4f4f5` (dots at 56%) | dots, particles, "payments still flowing" |
| **Contaminated / blocked** | `#ff5545` (coral) | blocked dots, cut edges, "blocked" figures, "Compromised" label |
| **Recovering / released** | `#ffb02e` (amber) | remediation, cascading release (transient) |
| **Proof** | `#6e95ff` (blue) | verified signatures, Avalanche anchoring, focus, "verified" ring |
| Primary text | `#f4f4f5` | |
| Secondary text | `#f4f4f5` at 66% | 8.1:1 on the background |
| Tertiary text | `#f4f4f5` at 42% | decorative only (counters, roles) |

Computed contrasts (WCAG) on `#050506`: primary text 18.5:1 · secondary 8.1:1 · coral 6.4:1 · amber 11.2:1 · blue 7.2:1.

## Typography

Fonts self-hosted in `web/app/fonts/` (no external network during the demo): **Geist** and **Geist Mono**, as variable fonts.

| Role | Font | Weight | Size |
|---|---|---|---|
| Big figures | Geist | **300** | `clamp(44px, 4.1vw, 80px)`, letter-spacing −0.055 em |
| Titles | Geist | 500 | 15–22 px, letter-spacing −0.02 to −0.03 em |
| Body text | Geist | 400–450 | 14.5 px, line height 1.5 |
| Labels (KPIs, sections, feed meta) | Geist Mono | 450 | 10.5–11 px, UPPERCASE, letter-spacing 0.07 em |
| Identifiers, tokens, hashes, times | Geist Mono | 450 | 0.88 em; truncated token `7d4b…5efba` |

- Figures in `font-variant-numeric: tabular-nums`.
- The thin weight (300) is reserved for big figures and large values: never below 26 px.
- Brand: `firebreak` in lowercase, Geist 600, 18 px, letter-spacing −0.035 em. Subtitle: "Supply-chain firewall" in tertiary text.
- Everything is in English; technical identifiers stay as they are.

## Spacing and radii

- 4 px grid. Stage margins 32 px (26 px below 940 px of height), map / feed gutter 40 px.
- Radii: drawer and panels 20 px · controls as **pills** (999 px) · small surfaces 12–14 px.
- Between map columns: `clamp(36px, 3.4vw, 72px)` — this is where the particles flow.
- Operation dots: `clamp(9px, 2.4vh − 10px, 17px)`; a square dot = irreversible action (gate); hollow blue ring = verified.

## Motion

A single curve: `cubic-bezier(0.2, 0.8, 0.2, 1)`. Never a bounce. The causality animations are unchanged by the redesign.

| Register | Durations | Examples |
|---|---|---|
| Ambient | 3.2–54 s, continuous | horizon, dot breathing, particles (46 px/s) |
| Causality | 0.3–0.7 s per step (SSE stream at 0.6 s) | coral line parent → child, sealed envelope (also from one ledger to another for a quality report), declaration wave, padlock, amber flash |
| Micro-interactions | 160–240 ms | hover, focus, menus, drawer (300 ms), "with vs without" screen (260 ms) |

`prefers-reduced-motion`: horizon, breathing and particles stop; lines fade in.

## Logo

A **grid of dots** (the operations, the forest) **cut by a vertical bar** (the firewall): two columns of three dots on the left, the bar, a faded column on the right (`web/app/icons.js` → `logo()`, `web/app/favicon.svg`).

- Monochrome white. A single animation, on open, 2.2 s, never looping: the left dots turn coral one after another, the bar rises, then everything returns to white; the right column is never touched.

## Icons

Custom set (`web/app/icons.js`): 24 px grid, 1.4 px stroke, rounded caps and joins, `currentColor`, **never a frame or background**.

- Operation families: order, shipping notice, certificate, invoice, payment, lot, shipment, receipt, internal operations.
- Companies: factory (supplier), gear (manufacturer), truck (distributor), shop (customer).
- Semantics: padlock (gate), checked shield (verified), sealed envelope (signed alert or report) and its crossed-out variant, drop (contamination), dotted circle (quarantine), return arrow (release), crossed-out bell (false alarm), chain (audit log), two rectangles (with / without).

## Key components

| Component | Role |
|---|---|
| Header | no background: logo, "View as", scenario, AI indicator, Avalanche (if active), Import, Reset; 1 px white progress line below |
| Figures | three big thin numbers, frameless, separated from the map by a rule; labels in uppercase Geist Mono |
| Map | 4 floating columns, a rule at the top of each column (coral if the company is compromised, with the "Compromised" label) |
| Action dock | floating blurred pill at the bottom: a single **white** primary button with a pulsing coral dot ("Declare…"), then "With vs without" and "False alarm" |
| Quality incident | `lot` and `recall` scenarios: the dock guides the human actions ("Step 2/6 · Distributor"): report, confirm, escalate, analyse the origin, isolate the lot, report to the supplier, confirmation. The supplier is never blacklisted |
| Recall analysis | drawer: possible causes of a faulty product, impact of a recall, "probable cause" in coral, "Isolate" button |
| Event feed | right-hand column separated by a rule, frameless icons, one line per SSE step, clickable to the proof |
| Proof | solid drawer: facts, contamination path (round nodes), AI explanation, recovery plan |
| With / without | two solid panels sliding in from the edges, mini-maps, thin precision / recall gauges |
| Audit log | drawer: chain of entries `#i · prev → hash`, pill tabs, verification |
| Import | drawer: document drop, examples, AI proposal, human confirmation |
| Avalanche (optional) | badge in the header, drawer of anchorings (confirmed = blue, in progress = amber, failed = coral); nothing is shown if the chain is off |
| Toasts, skeletons | solid surface; skeleton with a discreet sweep, never a lone spinner |
| Lite mode | if images slow things down, the dock and the "with vs without" screen lose their blur |

## Tested screens

1920×1080 (projector) and 1440×900 (laptop), with no horizontal scrolling.
