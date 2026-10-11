// The scene: chain map, particle flows, causality effects,
// numbers, event feed and SSE stream playback.
import { S, $, $$, api, el, emit, showTip, hideTip, companyName, REDUCED, EASE, wait, API } from './core.js';
import { icon, COMPANY_ICON } from './icons.js';
import * as F from './format.js';

// Healthy is neutral (white): only the abnormal gets a colour (design.md).
const OK = '244, 244, 245';
const Q = '255, 85, 69';
const R = '255, 176, 46';
const A = '110, 149, 255';
const SPEED = 0.6; // s between two SSE steps (brief: 0.3 to 0.8 s)

const dots = new Map();      // id → .dot button
const pos = new Map();       // id → {x, y} in map coordinates
const panels = new Map();    // company → article
let flows = [];              // animated cross edges
// Diagnostic access from the console (read-only).
window.__firebreak = { S, pos, dots, flows: () => flows };
const flashing = new Map();  // id → amber flash deadline (particles)

// =====================================================================
// State → display
// =====================================================================

export function applyState(st, { render = false } = {}) {
  S.state = st;
  S.recs = new Map(st.records.map((r) => [r.id, r]));
  S.status = new Map(st.records.map((r) => [r.id, r.status]));
  S.compromised = new Set((st.declarations || []).map((d) => d.source));
  S.companyName = Object.fromEntries(st.companies.map((c) => [c.id, c.name]));
  if (render || dots.size !== st.records.length || st.records.some((r) => !dots.has(r.id))) renderMap();
  else syncDots();
  for (const c of st.companies) setCompromised(c.id, S.compromised.has(c.id));
  refreshCounts();
  filterFeed();
  setKpis(currentCounters(), { animate: !render });
}

// API counters (global, or per company in partner view).
function currentCounters() {
  const c = S.state.counters;
  return S.view === 'all' ? c.global : c.per_company[S.view];
}

// Same definitions as the API (docs/api.md → Counters), computed on the
// displayed statuses: only used during an animation in partner view.
function localCounters(company) {
  const out = { total: 0, quarantined: 0, released: 0, gates_blocked: 0, amount_blocked: 0, amount_flowing: 0 };
  for (const r of S.state.records) {
    if (company && r.company !== company) continue;
    out.total++;
    const s = S.status.get(r.id);
    const amt = r.kind === 'payment' ? Number(r.payload?.amount) || 0 : 0;
    if (s === 'quarantined') {
      out.quarantined++;
      if (r.gate) out.gates_blocked++;
      out.amount_blocked += amt;
    } else {
      if (s === 'released') out.released++;
      out.amount_flowing += amt;
    }
  }
  out.ok = out.total - out.quarantined - out.released;
  return out;
}

// =====================================================================
// Map
// =====================================================================

function renderMap() {
  const wrap = $('#companies');
  wrap.innerHTML = '';
  dots.clear();
  panels.clear();
  const st = S.state;
  st.companies.forEach((c, ci) => {
    const recs = st.records.filter((r) => r.company === c.id).sort((a, b) => a.ts.localeCompare(b.ts));
    const p = el('article', 'company glass');
    p.dataset.company = c.id;
    p.tabIndex = 0;
    p.setAttribute('aria-label', `${c.name}, ${c.role}`);
    p.innerHTML = `
      <span class="c-tag">Compromised</span>
      <div class="c-head">
        <div class="c-ico">${icon(COMPANY_ICON[c.id] || 'maker')}</div>
        <div style="min-width:0">
          <div class="c-name">${F.esc(c.name)}</div>
          <div class="c-role">${F.esc(c.role)}</div>
        </div>
      </div>
      <div class="c-counts">
        <span class="ok"><i></i><b data-ok>0</b> flowing</span>
        <span class="q"><i></i><b data-q>0</b> <span data-ql>blocked</span></span>
        <span class="r"><i></i><b data-r>0</b> <span data-rl>released</span></span>
      </div>
      <div class="fams"></div>
      <div class="c-foot"><button data-audit="${F.esc(c.id)}" title="Audit log · ${F.esc(c.name)}">${icon('audit', 's16')}<span>Log</span><span class="mono" data-head>—</span><span></span></button></div>
      <div class="privacy"></div>`;
    const fams = p.querySelector('.fams');
    for (const f of F.FAMILIES) {
      const list = recs.filter((r) => F.familyOf(r.kind) === f.id);
      if (!list.length) continue;
      const fam = el('div', 'fam');
      fam.innerHTML = `<div class="fam-h">${icon(f.icon, 's16')}<span>${f.label}</span><span class="n">${list.length}</span></div><div class="dots"></div>`;
      const box = fam.querySelector('.dots');
      for (const r of list) {
        const d = el('button', 'dot');
        d.dataset.id = r.id;
        if (r.gate) d.classList.add('gate');
        if (r.verified) d.classList.add('verified');
        d.style.setProperty('--delay', `${(-Math.random() * 6).toFixed(2)}s`);
        d.style.setProperty('--breath', `${(3.8 + Math.random() * 2.6).toFixed(2)}s`);
        box.append(d);
        dots.set(r.id, d);
        paintDot(r.id, S.status.get(r.id));
      }
      fams.append(fam);
    }
    panels.set(c.id, p);
    wrap.append(p);
    p.style.animation = `rise 420ms ${EASE} ${ci * 70}ms both`;
  });
  applyView();
  // Measure now, then after the panels' entry animation (≈ 650 ms).
  measure();
  setTimeout(measure, 120);
  setTimeout(measure, 900);
}

function paintDot(id, s) {
  const d = dots.get(id);
  if (!d) return;
  const r = S.recs.get(id);
  d.dataset.s = s;
  d.tabIndex = s === 'quarantined' ? 0 : -1;
  d.setAttribute('aria-label', `${r.label} — ${F.STATUS[s]?.label || s}`);
}

function syncDots() {
  for (const [id, s] of S.status) paintDot(id, s);
}

export function refreshCounts() {
  for (const [cid, p] of panels) {
    const c = localCounters(cid);
    const flow = c.total - c.quarantined;
    p.querySelector('[data-ok]').textContent = F.n(flow);
    p.querySelector('[data-q]').textContent = F.n(c.quarantined);
    p.querySelector('[data-r]').textContent = F.n(c.released);
    p.querySelector('[data-rl]').textContent = 'released';
    p.querySelector('[data-ql]').textContent = 'blocked';
    p.querySelector('.c-counts .q').classList.toggle('zero', c.quarantined === 0);
    p.querySelector('.c-counts .r').classList.toggle('zero', c.released === 0);
  }
}

// In partner view, a ledger only knows a source is compromised if it
// recorded the declaration itself (otherwise it only receives tokens).
function knowsCompromise(cid) {
  if (S.view === 'all' || cid === S.view) return true;
  return (S.state.declarations || []).some((d) => d.ledger === S.view && d.source === cid);
}

function setCompromised(cid, on) {
  panels.get(cid)?.classList.toggle('compromised', on && knowsCompromise(cid));
}

// In partner view, the feed only shows events from the selected ledger.
function filterFeed() {
  for (const row of $$('#feed .ev')) row.hidden = S.view !== 'all' && row.dataset.co !== S.view;
}

// Dot positions in map coordinates (canvas and SVG layer).
export function measure() {
  const map = $('#map');
  const mr = map.getBoundingClientRect();
  pos.clear();
  for (const [id, d] of dots) {
    const r = d.getBoundingClientRect();
    if (!r.width) continue;
    pos.set(id, { x: r.left - mr.left + r.width / 2, y: r.top - mr.top + r.height / 2 });
  }
  const fx = $('#fx');
  fx.setAttribute('viewBox', `0 0 ${mr.width} ${mr.height}`);
  sizeCanvas(mr.width, mr.height);
  buildFlows();
}

// =====================================================================
// Flows: particles along inter-company edges (canvas, under the glass)
// =====================================================================

const canvas = () => $('#flows');
let ctx = null, cw = 0, ch = 0, last = 0, running = false;

function sizeCanvas(w, h) {
  const c = canvas();
  const dpr = Math.min(2, devicePixelRatio || 1);
  c.width = Math.round(w * dpr);
  c.height = Math.round(h * dpr);
  ctx = c.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  cw = w; ch = h;
}

function bezierPts(a, b, n = 40) {
  const dx = Math.max(40, Math.abs(b.x - a.x) * 0.5);
  const c1 = { x: a.x + dx, y: a.y }, c2 = { x: b.x - dx, y: b.y };
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, u = 1 - t;
    pts.push({
      x: u * u * u * a.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * b.x,
      y: u * u * u * a.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * b.y,
    });
  }
  return pts;
}

function pathLen(pts) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
  return L;
}

function at(pts, t) {
  const f = t * (pts.length - 1), i = Math.min(pts.length - 2, Math.floor(f)), k = f - i;
  return { x: pts[i].x + (pts[i + 1].x - pts[i].x) * k, y: pts[i].y + (pts[i + 1].y - pts[i].y) * k };
}

function buildFlows() {
  flows = (S.state.edges || [])
    .filter((e) => e.cross && pos.has(e.source) && pos.has(e.target))
    .map((e) => {
      const pts = bezierPts(pos.get(e.source), pos.get(e.target));
      return { s: e.source, t: e.target, pts, len: pathLen(pts), ph: [Math.random(), Math.random()] };
    });
  if (!running) { running = true; requestAnimationFrame(frame); }
}

function flowFor(a, b) {
  return flows.find((f) => f.s === a && f.t === b);
}

// Smoothness safeguard: if frames slow down noticeably (modest projection
// machine), the map panels switch to opaque glass, without blur.
let slowFrames = 0, sampled = 0;
function watchFps(raw) {
  if (document.body.classList.contains('lite') || document.hidden) return;
  if (raw > 0 && raw < 250) { sampled++; if (raw > 28) slowFrames++; }
  if (sampled >= 180) {
    if (slowFrames / sampled > 0.5) {
      document.body.classList.add('lite');
      console.info('[firebreak] slow frames: map glass without blur');
    }
    sampled = 0; slowFrames = 0;
  }
}

function frame(t) {
  const raw = t - (last || t);
  const dt = Math.min(0.05, raw / 1000);
  last = t;
  watchFps(raw);
  if (ctx) {
    ctx.clearRect(0, 0, cw, ch);
    const now = performance.now();
    for (const f of flows) {
      const src = S.recs.get(f.s), dst = S.recs.get(f.t);
      const ss = S.status.get(f.s);
      const cut = ss === 'quarantined';
      const mine = S.view === 'all' || src?.company === S.view || dst?.company === S.view;
      ctx.beginPath();
      ctx.moveTo(f.pts[0].x, f.pts[0].y);
      for (let i = 1; i < f.pts.length; i++) ctx.lineTo(f.pts[i].x, f.pts[i].y);
      ctx.lineWidth = cut ? 1.4 : 1;
      ctx.strokeStyle = cut ? `rgba(${Q}, ${mine ? 0.6 : 0.12})` : `rgba(255, 255, 255, ${mine ? 0.08 : 0.025})`;
      ctx.stroke();
      if (cut || REDUCED || !mine) continue;
      const amber = ss === 'released' || (flashing.get(f.s) || 0) > now || (flashing.get(f.t) || 0) > now;
      const col = amber ? R : OK;
      ctx.globalCompositeOperation = 'lighter';
      for (let k = 0; k < f.ph.length; k++) {
        f.ph[k] = (f.ph[k] + (dt * 46) / f.len) % 1;
        const p = at(f.pts, f.ph[k]);
        ctx.fillStyle = `rgba(${col}, 0.07)`;
        ctx.beginPath(); ctx.arc(p.x, p.y, 4.5, 0, 6.283); ctx.fill();
        ctx.fillStyle = `rgba(${col}, 0.9)`;
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.4, 0, 6.283); ctx.fill();
      }
      ctx.globalCompositeOperation = 'source-over';
    }
  }
  requestAnimationFrame(frame);
}

// =====================================================================
// Causality effects (SVG layer above the panels)
// =====================================================================

const NS = 'http://www.w3.org/2000/svg';
function svg(tag, attrs = {}, parent = $('#fx')) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent.append(e);
  return e;
}
function fadeOut(node, delay = 0, dur = 900) {
  setTimeout(() => {
    const a = node.animate([{ opacity: 1 }, { opacity: 0 }], { duration: REDUCED ? 1 : dur, fill: 'forwards' });
    a.onfinish = () => node.remove();
  }, delay);
}

export function clearFx() { $('#fx').innerHTML = ''; }

function pulse(id, cls = 'pulse') {
  const d = dots.get(id);
  if (!d) return;
  d.classList.remove('pulse', 'pulse-a');
  void d.offsetWidth;
  d.classList.add(cls);
}

function trace(a, b, rgb, dur = 320) {
  const p0 = pos.get(a), p1 = pos.get(b);
  if (!p0 || !p1) return wait(0);
  const mx = (p0.x + p1.x) / 2, my = (p0.y + p1.y) / 2;
  const dx = p1.x - p0.x, dy = p1.y - p0.y;
  const bend = Math.min(0.35, 40 / (Math.hypot(dx, dy) + 1));
  const d = `M${p0.x} ${p0.y} Q${mx - dy * bend} ${my + dx * bend} ${p1.x} ${p1.y}`;
  const path = svg('path', { d, class: 'trace', stroke: `rgb(${rgb})`, color: `rgb(${rgb})` });
  const L = path.getTotalLength();
  path.style.strokeDasharray = `${L}`;
  if (REDUCED) {
    path.style.strokeDashoffset = '0';
    path.animate([{ opacity: 0 }, { opacity: 1 }], { duration: dur, fill: 'forwards' });
  } else {
    path.animate([{ strokeDashoffset: L }, { strokeDashoffset: 0 }], { duration: dur, easing: EASE, fill: 'forwards' });
  }
  fadeOut(path, dur + 1100, 1200);
  return wait(dur);
}

function ripple(x, y, rgb, { r = 60, dur = 1100, width = 1.5, delay = 0 } = {}) {
  if (REDUCED) return;
  const c = svg('circle', { cx: x, cy: y, r, class: 'ripple', stroke: `rgb(${rgb})`, 'stroke-width': width });
  c.style.transformBox = 'fill-box';
  c.style.transformOrigin = 'center';
  c.animate(
    [{ transform: 'scale(0.08)', opacity: 0.9 }, { transform: 'scale(1)', opacity: 0 }],
    { duration: dur, delay, easing: EASE, fill: 'both' },
  ).onfinish = () => c.remove();
}

function panelCenter(cid) {
  const p = panels.get(cid);
  if (!p) return null;
  const mr = $('#map').getBoundingClientRect(), r = p.getBoundingClientRect();
  return { x: r.left - mr.left + r.width / 2, y: r.top - mr.top + r.height / 2, w: r.width, h: r.height };
}

function companyWave(cid, rgb) {
  const c = panelCenter(cid);
  if (!c) return;
  const R0 = Math.max(c.w, c.h) * 0.75;
  for (let i = 0; i < 3; i++) ripple(c.x, c.y, rgb, { r: R0, dur: 1600, delay: i * 220, width: 2 });
}

function floatTag(id, text, rgb = Q) {
  const p = pos.get(id);
  if (!p || !text) return;
  const g = svg('g', { class: 'tag' });
  const t = svg('text', { x: p.x, y: p.y - 15, 'text-anchor': 'middle' }, g);
  t.textContent = text;
  const w = t.getComputedTextLength() + 16;
  const rect = svg('rect', { x: p.x - w / 2, y: p.y - 29, width: w, height: 20, rx: 10 }, g);
  rect.style.stroke = `rgba(${rgb}, 0.6)`;
  g.insertBefore(rect, t);
  g.animate([{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 220, easing: EASE, fill: 'both' });
  fadeOut(g, 1500, 500);
}

function lockPop(id) {
  const p = pos.get(id);
  if (!p) return;
  const g = svg('g', { transform: `translate(${p.x - 9} ${p.y - 30}) scale(0.75)` });
  g.innerHTML = `<rect x="-2" y="-2" width="28" height="28" rx="9" fill="rgba(9,14,27,.92)" stroke="rgba(${Q},.6)" stroke-width="1.3"/>
    <g fill="none" stroke="rgb(${Q})" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="5" y="10.5" width="14" height="10" rx="2"/>
      <path class="shackle" d="M8 10.5V7.5a4 4 0 0 1 7.75-1.4"/>
      <path d="M12 14.5V17"/>
    </g>`;
  $('#fx').append(g);
  g.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, fill: 'both' });
  setTimeout(() => g.querySelector('.shackle')?.setAttribute('d', 'M8 10.5V7.5a4 4 0 0 1 8 0v3'), 260);
  fadeOut(g, 1900, 500);
}

function crossMark(id) {
  const p = pos.get(id);
  if (!p) return;
  const g = svg('g', { stroke: `rgb(${Q})`, 'stroke-width': 2, 'stroke-linecap': 'round' });
  svg('path', { d: `M${p.x - 7} ${p.y - 7}L${p.x + 7} ${p.y + 7}M${p.x + 7} ${p.y - 7}L${p.x - 7} ${p.y + 7}` }, g);
  fadeOut(g, 1600, 500);
}

// Sealed envelope travelling along an inter-company edge.
function envelope(a, b, rgb, dur = 520) {
  const f = flowFor(a, b) || (pos.get(a) && pos.get(b) ? { pts: bezierPts(pos.get(a), pos.get(b)) } : null);
  if (!f) return wait(0);
  return envelopeAlong(f.pts, rgb, dur);
}

function envelopeAlong(pts, rgb, dur) {
  const f = { pts };
  const g = svg('g', { class: 'env' });
  g.innerHTML = `<g transform="translate(-9 -7)" stroke="rgb(${rgb})">
      <rect x="0" y="0" width="18" height="13" rx="2.5"/>
      <path d="M1 1.5 9 7.5l8-6" fill="none"/>
    </g>
    <circle cx="8" cy="6" r="3.4" stroke="rgb(${A})"/>`;
  if (REDUCED) {
    const p = f.pts[f.pts.length - 1];
    g.setAttribute('transform', `translate(${p.x} ${p.y})`);
    fadeOut(g, dur, 300);
    return wait(dur);
  }
  return new Promise((resolve) => {
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      const p = at(f.pts, e);
      g.setAttribute('transform', `translate(${p.x} ${p.y})`);
      if (k < 1) requestAnimationFrame(step);
      else { fadeOut(g, 120, 260); resolve(); }
    };
    requestAnimationFrame(step);
  });
}

// Quality report: envelope from one ledger to another (upstream).
function panelEnvelope(from, to, rgb = A, dur = 700) {
  const a = panels.get(from), b = panels.get(to);
  if (!a || !b) return wait(0);
  const mr = $('#map').getBoundingClientRect();
  const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
  const y = (r) => r.top - mr.top + 34;
  const left = ra.left > rb.left;
  const p0 = { x: (left ? ra.left : ra.right) - mr.left, y: y(ra) };
  const p1 = { x: (left ? rb.right : rb.left) - mr.left, y: y(rb) };
  const pts = bezierPts(p0, p1).map((p, i, all) => ({ x: p.x, y: p.y - Math.sin((i / (all.length - 1)) * Math.PI) * 26 }));
  return envelopeAlong(pts, rgb, dur);
}

// =====================================================================
// Animated statuses
// =====================================================================

function setStatus(id, s, { flash = false } = {}) {
  if (!S.recs.has(id)) return;
  S.status.set(id, s);
  const d = dots.get(id);
  if (flash && d) {
    d.classList.add('flash-r');
    flashing.set(id, performance.now() + 1600);
    setTimeout(() => d.classList.remove('flash-r'), 1100);
  }
  paintDot(id, s);
  refreshCounts();
}

// =====================================================================
// Numbers
// =====================================================================

const tweens = new WeakMap();
function tween(node, to, fmt, animate = true) {
  if (!node) return;
  const from = Number(node.dataset.cur || 0);
  node.dataset.cur = String(to);
  cancelAnimationFrame(tweens.get(node));
  if (!animate || REDUCED || from === to) { node.textContent = fmt(to); return; }
  const t0 = performance.now(), dur = 520;
  const step = (t) => {
    const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    node.textContent = fmt(from + (to - from) * e);
    if (k < 1) tweens.set(node, requestAnimationFrame(step));
  };
  tweens.set(node, requestAnimationFrame(step));
}

export function setKpis(c, { animate = true, total } = {}) {
  if (!c) return;
  const tot = total ?? c.total ?? S.state.records.length;
  tween($('#kpiBlocked [data-v]'), c.quarantined, F.n, animate);
  tween($('#kpiBlocked [data-total]'), tot, F.n, animate);
  tween($('#kpiBlocked [data-flow]'), tot - c.quarantined, F.n, animate);
  tween($('#kpiFraud [data-v]'), c.amount_blocked || 0, F.n, animate);
  tween($('#kpiFraud [data-gates]'), c.gates_blocked || 0, F.n, animate);
  const quality = !!S.state.scenario?.incident;
  $('#kpiFraud .k-label span').textContent = quality ? 'Payments withheld' : 'Fraudulent payment blocked';
  $('#kpiFraud [data-gates-l]').textContent = (c.gates_blocked || 0) > 1 ? 'irreversible actions blocked' : 'irreversible action blocked';
  tween($('#kpiFlowing [data-v]'), c.amount_flowing || 0, F.n, animate);
  $('#kpiBlocked').classList.toggle('hot', c.quarantined > 0);
  $('#kpiFraud').classList.toggle('hot', (c.amount_blocked || 0) > 0);
  $('#kpiFlowing [data-scope]').textContent = S.view === 'all'
    ? 'across the whole chain'
    : `at ${F.ROLE_LABEL[S.view] || companyName(S.view)}`;
}

// =====================================================================
// Partner view: the other ledgers are frosted glass
// =====================================================================

export function applyView() {
  filterFeed();
  for (const cid of panels.keys()) setCompromised(cid, S.compromised.has(cid));
  for (const [cid, p] of panels) {
    const masked = S.view !== 'all' && cid !== S.view;
    p.classList.toggle('masked', masked);
    for (const part of p.querySelectorAll('.fams, .c-counts, .c-foot')) part.inert = masked;
    const priv = p.querySelector('.privacy');
    if (!masked) { priv.innerHTML = ''; continue; }
    const alerts = (S.state.alerts || []).filter((a) =>
      (a.from === cid && a.to === S.view) || (a.from === S.view && a.to === cid));
    const rows = alerts.slice(-4).map((a) => {
      const inbound = a.to === S.view;
      const kind = a.type === 'release' ? 'release' : 'contamination';
      const bad = a.verified === false;
      return `<div class="p-alert surface ${bad ? 'bad' : ''}">${icon(bad ? 'alertBad' : 'alert', 's16')}
        <span>${inbound ? 'Received' : 'Sent'} · ${kind}</span>
        <span class="mono">${F.n(a.tokens_count)} token${a.tokens_count > 1 ? 's' : ''}</span></div>`;
    }).join('');
    priv.innerHTML = `${icon('lockKey')}
      <div class="p-title">Private ledger · ${F.esc(companyName(cid))}</div>
      <div class="p-sub">${alerts.length
        ? 'Only signed alerts get through: opaque tokens, no label or amount.'
        : 'Nothing leaves this ledger. No alerts exchanged with you.'}</div>
      ${rows ? `<div class="p-alerts">${rows}</div>` : ''}`;
  }
  setKpis(currentCounters(), { animate: true });
}

// =====================================================================
// Event feed
// =====================================================================

const feed = () => $('#feed');
let feedSteps = 0;

export function feedReset() {
  feed().innerHTML = '';
  feedSteps = 0;
  updateFeedCount();
  feedEmpty();
}

function feedEmpty() {
  if (feed().children.length) return;
  const st = S.state;
  const box = el('div', 'feed-empty surface');
  box.innerHTML = st
    ? `<b>No incident.</b>${F.n(st.records.length)} operations flow between ${st.companies.length} companies. ${st.scenario?.incident
      ? 'A quality defect is about to be reported: Firebreak isolates the faulty lot and what derives from it, without cutting off the supplier.'
      : 'Declare a compromise: Firebreak isolates only what is contaminated.'}`
    : '<span class="sk line"></span><span class="sk line"></span>';
  feed().append(box);
}

function updateFeedCount() {
  $('#feedCount').textContent = feedSteps ? String(feedSteps) : '';
  $('#feedCount').title = `${feedSteps} step${feedSteps > 1 ? 's' : ''}`;
}

function feedGroup(title) {
  feed().querySelector('.feed-empty')?.remove();
  const g = el('div', 'ev-group');
  g.innerHTML = `<div class="sec-title" style="margin:10px 8px 6px">${F.esc(title)}</div>`;
  feed().append(g);
  feed().scrollTop = feed().scrollHeight;
  return g;
}

function stepText(step) {
  if (step.type === 'document_confirmed') return `Document confirmed by a human and recorded in the ${F.esc(companyName(step.company))} ledger: “${F.esc(S.recs.get(step.record)?.label || step.record)}”.`;
  if (step.type === 'epcis_import') return `EPCIS import into the ${F.esc(companyName(step.company))} ledger.`;
  return step.text || '';
}

function feedAdd(group, step, animate) {
  const meta = F.STEP_META[step.type] || { icon: 'dot', tone: 'a', label: step.type };
  const bad = (step.type === 'alert_received' || step.type === 'alert_sent') && step.alert?.verified === false;
  const isRelease = step.alert?.type === 'release';
  const tone = bad ? 'q' : (step.type.startsWith('alert') ? 'a' : meta.tone);
  const row = el(step.record ? 'button' : 'div', `ev t-${tone}`);
  if (!animate) row.style.animation = 'none';
  if (step.record) row.dataset.record = step.record;
  row.dataset.co = step.company || '';
  if (S.view !== 'all' && step.company !== S.view) row.hidden = true;
  const label = step.type.startsWith('alert') ? `${meta.label}${isRelease ? ' · release' : ''}` : meta.label;
  row.innerHTML = `<span class="ev-ico">${icon(bad ? 'alertBad' : meta.icon, 's16')}</span>
    <span><span class="ev-meta"><span class="mono">${F.hm(step.ts)}</span><span>${label}</span><span>· ${F.esc(F.ROLE_SHORT[step.company] || step.company || '')}</span></span>
    <span class="ev-text">${F.richText(stepText(step))}</span></span>`;
  group.append(row);
  feedSteps++;
  updateFeedCount();
  const list = feed();
  const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 140;
  if (nearBottom || !animate) list.scrollTop = list.scrollHeight;
}

export function feedLoad(steps, title) {
  const g = feedGroup(title);
  for (const s of steps) feedAdd(g, s, false);
}

// =====================================================================
// SSE stream playback
// =====================================================================

// Statuses before the last action, rebuilt by walking the timeline backwards.
export function snapshotBefore(steps) {
  const status = new Map(S.status);
  const compromised = new Set(S.compromised);
  for (const s of [...steps].reverse()) {
    if (s.type === 'declaration') compromised.delete(s.company);
    if (s.type === 'withdrawal') compromised.add(s.company);
    if (!s.record) continue;
    if (s.type === 'seed' || s.type === 'quarantine' || s.type === 'gate_blocked') status.set(s.record, 'ok');
    else if (s.type === 'release' || s.type === 'remediation') status.set(s.record, 'quarantined');
  }
  return { status, compromised };
}

export function takeSnapshot() {
  return { status: new Map(S.status), compromised: new Set(S.compromised) };
}

function restore(snap) {
  for (const id of S.recs.keys()) {
    const s = snap.status.get(id) ?? 'ok';
    S.status.set(id, s);
    paintDot(id, s);
  }
  for (const cid of panels.keys()) setCompromised(cid, snap.compromised.has(cid));
  refreshCounts();
  const c = localCounters(S.view === 'all' ? null : S.view);
  setKpis(c, { animate: false });
}

async function* sse(signal) {
  const res = await fetch(`${API}/api/events?speed=${SPEED}`, { signal, headers: { Accept: 'text/event-stream' } });
  if (!res.ok || !res.body) throw new Error('Live stream unavailable.');
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const data = chunk.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trim()).join('\n');
      if (data) yield JSON.parse(data);
    }
  }
}

// Fallback if the SSE stream fails: the same sequence in one go, paced here.
async function* paced(steps, signal) {
  for (const s of steps) {
    if (signal.aborted) return;
    yield s;
    await wait(SPEED * 1000);
  }
}

function setProgress(k) {
  const bar = $('#progress');
  bar.classList.toggle('on', k != null);
  bar.querySelector('span').style.width = `${Math.round((k ?? 0) * 100)}%`;
}

// Plays the last action step by step, then applies the final API state.
// `final`: full response of the action (null = the current state).
export async function play({ final = null, title, snapshot = null, source = null } = {}) {
  S.abort?.abort();
  const ctrl = new AbortController();
  S.abort = ctrl;
  S.playing = true;
  emit('playing', true);
  const target = final || S.state;
  try {
    const { steps } = await api('GET', '/api/timeline', undefined, { signal: ctrl.signal });
    if (!steps.length) { applyState(target); return; }
    // Healing sequence (remediation, withdrawal): no new contamination.
    S.healing = steps.some((s) => s.type === 'release' || s.type === 'remediation' || s.type === 'withdrawal' || s.type === 'lot_suspect_withdrawn')
      && !steps.some((s) => s.type === 'seed' || s.type === 'quarantine' || s.type === 'gate_blocked');
    emit('playing', true);
    // New records (ingestion): lay out the new map, then the previous state.
    let born = [];
    if (final && final.records.length !== S.state.records.length) {
      const old = new Set(S.recs.keys());
      applyState(final, { render: true });
      born = [...S.recs.keys()].filter((id) => !old.has(id));
      await wait(60);
      if (ctrl.signal.aborted) return;
    }
    const snap = snapshot || S.snapshot;
    S.snapshot = snap;
    if (snap) restore(snap);
    for (const id of born) {
      const d = dots.get(id);
      d?.classList.add('new');
      d?.addEventListener('animationend', () => d.classList.remove('new'), { once: true });
    }
    const group = feedGroup(title || 'Replay');
    const total = steps.length;
    const src = source ?? [...S.compromised][0];
    let stream;
    try { stream = sse(ctrl.signal); } catch { stream = paced(steps, ctrl.signal); }
    let n = 0;
    try {
      for await (const step of stream) {
        if (ctrl.signal.aborted) return;
        n++;
        setProgress(n / total);
        await onStep(group, step, src, ctrl.signal);
      }
    } catch (e) {
      if (e.name === 'AbortError' || ctrl.signal.aborted) return;
      // Stream cut: finish with the timeline (same content).
      for await (const step of paced(steps.slice(n), ctrl.signal)) { n++; setProgress(n / total); await onStep(group, step, src, ctrl.signal); }
    }
    await wait(450);
    if (ctrl.signal.aborted) return;
    applyState(target);
  } finally {
    if (S.abort === ctrl) {
      S.playing = false;
      S.abort = null;
      setProgress(null);
      emit('playing', false);
      emit('settled');
    }
  }
}

async function onStep(group, step, source, signal) {
  if (signal?.aborted) return;
  feedAdd(group, step, true);
  if (S.view === 'all' && step.counters) setKpis(step.counters, { total: S.state.records.length });
  const id = step.record;
  switch (step.type) {
    case 'declaration':
      companyWave(step.company, Q);
      if (step.company === source) setCompromised(step.company, true);
      break;
    case 'withdrawal':
      companyWave(step.company, OK);
      if (step.company === source) setCompromised(step.company, false);
      break;
    case 'seed':
      setStatus(id, 'quarantined');
      pulse(id);
      floatTag(id, F.RULE_LABEL[step.rule] || String(step.rule || ''));
      break;
    case 'quarantine':
    case 'gate_blocked':
      if (step.parent) await trace(step.parent, id, Q);
      if (signal?.aborted) return;
      setStatus(id, 'quarantined');
      pulse(id);
      if (step.type === 'gate_blocked') lockPop(id);
      break;
    case 'alert_sent': {
      const rgb = step.alert?.type === 'release' ? OK : Q;
      (step.alert?.links || []).forEach(([a, b], i) => setTimeout(() => envelope(a, b, rgb), i * 70));
      break;
    }
    case 'alert_received':
      for (const [, b] of step.alert?.links || []) {
        if (step.alert.verified === false) crossMark(b);
        else { pulse(b, 'pulse-a'); const p = pos.get(b); if (p) ripple(p.x, p.y, A, { r: 18, dur: 800 }); }
      }
      break;
    case 'release':
      setStatus(id, 'ok', { flash: true });
      pulse(id);
      break;
    case 'remediation': {
      setStatus(id, 'released');
      pulse(id);
      const p = pos.get(id);
      if (p) ripple(p.x, p.y, R, { r: 46, dur: 1200 });
      break;
    }
    case 'lot_suspect':
      companyWave(step.company, Q);
      break;
    case 'lot_suspect_withdrawn':
      companyWave(step.company, OK);
      break;
    case 'report_sent': {
      const rep = [...(S.reports || [])].reverse().find((r) => r.from === step.company);
      if (rep) await panelEnvelope(rep.from, rep.to);
      break;
    }
    case 'report_received':
    case 'report_decided': {
      const c = panelCenter(step.company);
      if (c) ripple(c.x, c.y, A, { r: Math.max(c.w, c.h) * 0.55, dur: 1300 });
      break;
    }
    case 'document_confirmed':
    case 'epcis_import': {
      const c = panelCenter(step.company);
      if (c) ripple(c.x, c.y, A, { r: Math.max(c.w, c.h) * 0.6, dur: 1400 });
      if (id) pulse(id, 'pulse-a');
      break;
    }
    default:
      break;
  }
  if (S.view !== 'all') setKpis(localCounters(S.view), {});
}

// =====================================================================
// Map interactions: tooltip, lineage, click → proof
// =====================================================================

function lineage(id) {
  const out = [];
  const r = S.recs.get(id);
  if (!r) return out;
  for (const i of r.inputs || []) out.push([i, id]);
  for (const e of S.state.edges) {
    if (e.target === id && e.cross) out.push([e.source, id]);
    if (e.source === id) out.push([id, e.target]);
  }
  return out;
}

let hoverG = null;
function showLineage(id) {
  hideLineage();
  hoverG = svg('g', { opacity: 0.9 });
  for (const [a, b] of lineage(id)) {
    const p0 = pos.get(a), p1 = pos.get(b);
    if (!p0 || !p1) continue;
    const q = S.status.get(a) === 'quarantined' && S.status.get(b) === 'quarantined';
    const rgb = q ? Q : '255, 255, 255';
    svg('line', { x1: p0.x, y1: p0.y, x2: p1.x, y2: p1.y, stroke: `rgba(${rgb}, ${q ? 0.85 : 0.35})`, 'stroke-width': 1.2, 'stroke-dasharray': q ? '' : '3 3' }, hoverG);
    svg('circle', { cx: (a === id ? p1 : p0).x, cy: (a === id ? p1 : p0).y, r: 6, fill: 'none', stroke: `rgba(${rgb}, .6)`, 'stroke-width': 1 }, hoverG);
  }
}
function hideLineage() { hoverG?.remove(); hoverG = null; }

function tipFor(id) {
  const r = S.recs.get(id);
  const s = S.status.get(id);
  const st = F.STATUS[s] || { label: s, cls: 'n' };
  const amt = r.payload?.amount != null ? ` · ${F.eur(r.payload.amount)}` : '';
  const flags = [r.gate ? 'irreversible action' : '', r.verified ? 'verified' : ''].filter(Boolean).join(' · ');
  return `<div class="tt">${F.esc(r.label)}</div>
    <div class="td"><span>${F.kindLabel(r.kind)}${amt}</span></div>
    <div class="td"><span class="mono">${F.hm(r.ts)}</span><span class="st-${st.cls}">● ${st.label}</span>${flags ? `<span>${flags}</span>` : ''}</div>`;
}

export function bindMap() {
  const wrap = $('#companies');
  wrap.addEventListener('click', (e) => {
    const audit = e.target.closest('[data-audit]');
    if (audit) { emit('open-audit', audit.dataset.audit); return; }
    const d = e.target.closest('.dot');
    if (d) emit('open-proof', d.dataset.id);
  });
  wrap.addEventListener('pointerover', (e) => {
    const d = e.target.closest('.dot');
    if (!d) return;
    const r = d.getBoundingClientRect();
    showTip(tipFor(d.dataset.id), r.left + r.width / 2, r.top);
    showLineage(d.dataset.id);
  });
  wrap.addEventListener('pointerout', (e) => {
    if (e.target.closest('.dot')) { hideTip(); hideLineage(); }
  });
  wrap.addEventListener('focusin', (e) => {
    const d = e.target.closest('.dot');
    if (!d) return;
    const r = d.getBoundingClientRect();
    showTip(tipFor(d.dataset.id), r.left + r.width / 2, r.top);
    showLineage(d.dataset.id);
  });
  wrap.addEventListener('focusout', () => { hideTip(); hideLineage(); });
  $('#feed').addEventListener('click', (e) => {
    const row = e.target.closest('[data-record]');
    if (row && S.recs.has(row.dataset.record)) emit('open-proof', row.dataset.record);
  });
  new ResizeObserver(() => measure()).observe($('#map'));
}

export function highlight(id) {
  pulse(id, 'pulse-a');
}
