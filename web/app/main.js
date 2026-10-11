// FIREBREAK — final UI (docs/brief-ui.md).
// A single page, no navigation: screens are states of the same scene.
import { S, $, $$, api, el, on, fail, toast, hydrateIcons, companyName, wait } from './core.js';
import { icon, logo } from './icons.js';
import * as F from './format.js';
import {
  applyState, applyView, bindMap, clearFx, feedLoad, feedReset, highlight, measure, play,
  snapshotBefore, takeSnapshot,
} from './scene.js';
import {
  closeDrawer, closeVersus, drawerIs, drawerOpen, openAudit, openChain, openIngest, openProof, openRecall, openVersus,
  setAi, setSnapshotFn, versusOpen,
} from './panels.js';

// =====================================================================
// Boot
// =====================================================================

async function boot() {
  hydrateIcons();
  $('#logo').innerHTML = logo('play');
  bindMap();
  bindHeader();
  bindKeys();
  setSnapshotFn(takeSnapshot);
  feedReset();
  try {
    const [state, scenarios, tl] = await Promise.all([
      api('GET', '/api/state'),
      api('GET', '/api/scenarios'),
      api('GET', '/api/timeline'),
    ]);
    S.scenarios = scenarios;
    applyState(state, { render: true });
    await loadReports();
    $('#app').classList.remove('boot');
    renderScenario();
    renderMenus();
    feedReset();
    if (tl.steps.length) {
      S.snapshot = snapshotBefore(tl.steps);
      S.lastAction = 'Last action';
      feedLoad(tl.steps, 'Last action');
    }
    renderActionbar();
    refreshHeads();
    probeChain();
    probeAi();
  } catch (e) {
    fail(e, () => location.reload());
  }
}

// =====================================================================
// Header: scenario, partner view, AI, import, reset
// =====================================================================

function renderScenario() {
  const sc = S.state.scenario || {};
  $('#scTitle').textContent = sc.label || 'Scenario';
  $('#scDesc').innerHTML = `<span title="${F.esc(sc.description || '')}">${F.esc(sc.description || '')}</span>`;
  const blocked = [...S.status.values()].includes('quarantined');
  const inc = S.compromised.size > 0 || blocked;
  const st = $('#sceneState');
  st.className = `s-state ${S.playing ? (S.healing ? 'healing' : 'incident') : inc ? 'incident' : ''}`;
  document.body.classList.toggle('incident', S.playing ? !S.healing : inc);
  st.querySelector('span:last-child').textContent = S.playing
    ? (S.healing ? 'Cascading release…' : 'Propagating…')
    : incident()
      ? (blocked ? 'Quality incident · lot isolated' : S.reports.length ? 'Quality report in progress' : 'The chain is running')
      : inc
        ? 'Incident in progress · targeted containment'
        : 'The chain is running';
}

function menu(btn, list, items, onPick) {
  list.innerHTML = items.map((it) => `<button role="option" data-v="${F.esc(it.value)}" aria-selected="${it.selected}">
    <span class="tick">${icon('check', 's16')}</span><span class="t">${F.esc(it.title)}</span>${it.desc ? `<span class="d">${F.esc(it.desc)}</span>` : '<span></span>'}</button>`).join('');
  list.querySelectorAll('[role="option"]').forEach((o) => o.addEventListener('click', () => {
    closeMenus();
    onPick(o.dataset.v);
  }));
}

function renderMenus() {
  const sc = S.state.scenario?.id;
  const cur = S.scenarios.find((s) => s.id === sc);
  $('#scenarioBtn').innerHTML = `${icon('lot', 's18')}<span class="lbl">Scenario</span><span>${F.esc(cur?.label || sc || '—')}</span>${icon('chevron', 's16')}`;
  menu($('#scenarioBtn'), $('#scenarioMenu'), S.scenarios.map((s) => ({
    value: s.id, title: s.label, desc: s.description, selected: s.id === sc,
  })), (v) => resetTo(v));

  const view = S.view;
  $('#viewBtn').innerHTML = `${icon('eye', 's18')}<span class="lbl">View as</span><span>${view === 'all' ? 'Whole chain' : F.ROLE_SHORT[view] || companyName(view)}</span>${icon('chevron', 's16')}`;
  menu($('#viewBtn'), $('#viewMenu'), [
    { value: 'all', title: 'Whole chain', desc: 'Demo view: all four ledgers.', selected: view === 'all' },
    ...S.state.companies.map((c) => ({
      value: c.id, title: `${F.ROLE_SHORT[c.id] || c.name} — ${c.name}`,
      desc: 'Sees only its own ledger and the signed alerts it receives.', selected: view === c.id,
    })),
  ], (v) => { S.view = v; applyView(); renderMenus(); });
}

function closeMenus() {
  for (const b of $$('.menu-btn[aria-expanded="true"]')) {
    const m = b.nextElementSibling;
    const hadFocus = m?.contains(document.activeElement);
    m?.classList.remove('open');
    b.setAttribute('aria-expanded', 'false');
    if (hadFocus) b.focus({ preventScroll: true });
  }
}

function bindHeader() {
  for (const [b, m] of [['#scenarioBtn', '#scenarioMenu'], ['#viewBtn', '#viewMenu']]) {
    $(b).addEventListener('click', (e) => {
      e.stopPropagation();
      const open = !$(m).classList.contains('open');
      closeMenus();
      if (open) {
        $(m).classList.add('open');
        $(b).setAttribute('aria-expanded', 'true');
        ($(m).querySelector('[aria-selected="true"]') || $(m).querySelector('[role="option"]'))?.focus();
      }
    });
    $(m).addEventListener('keydown', (e) => {
      const opts = $$('[role="option"]', $(m));
      const i = opts.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') { e.preventDefault(); opts[(i + 1) % opts.length].focus(); }
      if (e.key === 'ArrowUp') { e.preventDefault(); opts[(i - 1 + opts.length) % opts.length].focus(); }
    });
  }
  document.addEventListener('click', (e) => { if (!e.target.closest('.menu-wrap')) closeMenus(); });
  $('#resetBtn').addEventListener('click', () => resetTo(S.state?.scenario?.id));
  $('#importBtn').addEventListener('click', () => S.state && openIngest());
  $('#replayBtn').addEventListener('click', replay);
  $('#verifyBtn').addEventListener('click', () => refreshHeads(true));
  $('#chainChip').addEventListener('click', openChain);
  $('#scrim').addEventListener('click', closeDrawer);
}

async function probeChain() {
  // Avalanche anchoring (optional): nothing is shown if missing or off.
  try {
    const st = await api('GET', '/api/chain/status');
    S.chain = st;
    const on = st && st.mode !== 'off';
    $('#chainChip').hidden = !on;
    if (!on) return;
    $('#chainChip').classList.toggle('off', !st.connected);
    const q = st.queue || {};
    const busy = (q.pending || 0) + (q.sent || 0);
    $('#chainLabel').textContent = !st.connected ? 'Avalanche · offline'
      : busy ? `Avalanche · ${busy} pending` : `Avalanche · ${F.n(q.confirmed || 0)} anchored`;
  } catch { /* endpoint missing: expected */ }
}

async function probeAi() {
  // AI indicator: read `source` from an explanation (simulated template by default).
  const any = S.state.records.find((r) => r.status === 'quarantined') || S.state.records[0];
  if (!any || S.ai) return;
  try {
    const ex = await api('GET', `/api/records/${encodeURIComponent(any.id)}/explain`);
    if (!S.ai) setAi(ex.source);
  } catch { /* silent: the indicator keeps its value */ }
}

// Audit log heads, verified (hash chain).
async function refreshHeads(loud = false) {
  try {
    const v = await api('GET', '/api/audit/verify');
    for (const j of v.journals) {
      const h = document.querySelector(`.company[data-company="${F.esc(j.company)}"] [data-head]`);
      if (!h) continue;
      h.textContent = j.entries ? `${F.n(j.entries)} · ${F.tok(j.head, 4, 4)}` : 'empty';
      const mark = h.nextElementSibling;
      mark.className = j.entries ? (j.ok ? 'okmark' : 'badmark') : '';
      mark.innerHTML = j.entries ? icon(j.ok ? 'check' : 'close', 's16') : '';
      mark.title = j.ok ? 'Hash chain intact' : 'Hash chain broken';
      if (j.onchain) {
        mark.className = j.ok && j.onchain.matches ? 'okmark' : 'badmark';
        mark.innerHTML = icon(j.onchain.matches ? 'chain' : 'leak', 's16');
        if (j.onchain.matches) mark.style.color = 'var(--accent)';
        mark.title = j.onchain.matches ? `Anchored on Avalanche, block ${j.onchain.block}` : 'No longer matches the Avalanche anchor';
      } else mark.style.color = '';
    }
    if (loud) {
      const n = v.journals.reduce((a, j) => a + j.entries, 0);
      const chain = v.onchain_ok == null ? '' : v.onchain_ok
        ? ' Heads anchored on Avalanche: they match.'
        : ' Warning: a log no longer matches its Avalanche anchor.';
      const good = v.ok && v.onchain_ok !== false;
      toast(v.ok
        ? n ? `Audit logs intact: ${F.n(n)} entr${n > 1 ? 'ies' : 'y'}, ${v.journals.length} hash chains verified.${chain}`
          : `Audit logs empty and intact: no events since the reset.`
        : `Chain broken: ${companyName(v.first_broken.company)}, entry #${v.first_broken.index}.`,
      { tone: good ? 'info' : 'err', ttl: 5000 });
    }
  } catch (e) {
    if (loud) fail(e, () => refreshHeads(true));
  }
}

// =====================================================================
// Action bar
// =====================================================================

function declareLabel() {
  const c = S.state.scenario?.compromise;
  if (!c) return 'Declare a compromise';
  return `Declare ${F.ROLE_LABEL[c.company] || companyName(c.company)} compromised since ${F.hourFr(c.since)}`;
}

function renderActionbar() {
  const bar = $('#actionbar');
  const inc = S.compromised.size > 0;
  const q = [...S.status.values()].filter((s) => s === 'quarantined').length;
  const proofHint = `<span class="hint">${q ? `${icon('arrow', 's16')}Click a red operation: path, explanation, recovery` : `${icon('check', 's16')}No more blocked operations`}</span>`;
  if (incident()) {
    const steps = qualitySteps();
    const i = steps.findIndex((x) => !x.done());
    if (i >= 0) {
      const st = steps[i];
      bar.innerHTML = `<div class="dock"><span class="step">Step <b>${i + 1}</b>/${steps.length} · ${F.esc(F.ROLE_SHORT[st.who] || st.who)}</span>
        <button class="btn declare" id="qualityBtn">${i === 0 ? '<span class="rec"></span>' : ''}<span>${F.esc(st.label)}</span>${i ? icon('arrow', 's18') : ''}</button>
        <span class="hint"><span class="kbd">→</span>next step</span></div>`;
      $('#qualityBtn').addEventListener('click', () => st.go());
    } else {
      bar.innerHTML = `<div class="dock"><span class="step"><b>Incident handled</b> · supplier not blacklisted</span>
        ${isolated(qualityLot()) ? `<button class="btn" id="liftBtn">${icon('release')}<span>Release lot ${F.esc(qualityLot())}</span></button>` : ''}
        <span class="sep"></span>${proofHint}</div>`;
      $('#liftBtn')?.addEventListener('click', liftLot);
    }
  } else if (!inc) {
    bar.innerHTML = `<div class="dock"><button class="btn declare" id="declareBtn"><span class="rec"></span><span>${F.esc(declareLabel())}</span></button>
      <span class="hint"><span class="kbd">→</span>next step</span></div>`;
    $('#declareBtn').addEventListener('click', declare);
  } else {
    bar.innerHTML = `<div class="dock"><button class="btn compare" id="compareBtn">${icon('compare')}<span>With vs without Firebreak</span></button>
      <button class="btn" id="withdrawBtn">${icon('falseAlarm')}<span>False alarm</span></button>
      <span class="sep"></span>${proofHint}</div>`;
    $('#compareBtn').addEventListener('click', openVersus);
    $('#withdrawBtn').addEventListener('click', withdraw);
  }
  bar.querySelectorAll('button').forEach((b) => { b.disabled = S.playing; });
  $('#replayBtn').disabled = S.playing || !S.snapshot;
  $('#resetBtn').disabled = false;
  renderScenario();
}

on('playing', () => renderActionbar());
on('settled', async () => {
  await loadReports();
  renderActionbar(); renderMenus(); refreshHeads(); applyView();
  // Anchors are sent in the background: re-read the chain status a bit later.
  probeChain(); setTimeout(probeChain, 2500);
});
on('audit-changed', () => refreshHeads());

// =====================================================================
// Actions
// =====================================================================

let busy = false;
async function run(title, call, { source = null } = {}) {
  if (S.playing || busy) {
    toast('A sequence is running: wait for it to finish.', { tone: 'info', ttl: 2500 });
    return;
  }
  busy = true;
  $$('#actionbar button').forEach((b) => { b.disabled = true; });
  const snapshot = takeSnapshot();
  try {
    const final = await call();
    S.lastAction = title;
    await play({ final, title, snapshot, source });
  } catch (e) {
    fail(e, () => run(title, call, { source }));
  } finally {
    busy = false;
    S.healing = false;
    renderActionbar();
  }
}

function declare() {
  const c = S.state.scenario?.compromise;
  if (!c) return;
  return run('Compromise declaration', () => api('POST', '/api/compromise', { company: c.company, since: c.since }), { source: c.company });
}

function withdraw() {
  const src = [...S.compromised][0];
  if (!src) return;
  return run('False alarm: declaration withdrawn', () => api('POST', '/api/compromise/withdraw', { company: src }), { source: src });
}

function remediate(id, action) {
  const r = S.recs.get(id);
  return run(`Remediation: ${r?.label || id}`, () => api('POST', `/api/records/${encodeURIComponent(id)}/remediate`, { action }));
}

async function replay() {
  if (S.playing || busy || !S.snapshot) return;
  closeDrawer();
  closeVersus();
  try {
    await play({ title: `Replay — ${S.lastAction || 'last action'}`, snapshot: S.snapshot });
  } catch (e) {
    fail(e, replay);
  } finally {
    S.healing = false;
    renderActionbar();
  }
}

async function resetTo(scenario, { quiet = false } = {}) {
  S.abort?.abort();
  closeDrawer();
  if (versusOpen()) closeVersus();
  try {
    const st = await api('POST', '/api/reset', scenario ? { scenario } : undefined);
    clearFx();
    S.snapshot = null;
    S.lastAction = null;
    S.reports = [];
    demo = 0;
    applyState(st, { render: true });
    feedReset();
    renderMenus();
    renderActionbar();
    refreshHeads();
    if (!quiet) toast(`Scenario “${st.scenario?.label || scenario}” ready: ${F.n(st.records.length)} operations, no declaration.`, { tone: 'info', ttl: 3200 });
  } catch (e) {
    fail(e, () => resetTo(scenario, { quiet }));
  }
}

on('open-proof', (id) => { closeVersus(); openProof(id); });
on('open-audit', (co) => openAudit(co));
on('remediate', ({ id, action }) => remediate(id, action));
on('isolate-lot', ({ company, lot, reason }) => isolateLot(company, lot, reason));
on('highlight', (id) => highlight(id));
on('ingested', async ({ state, snapshot, title }) => {
  S.lastAction = title;
  try {
    await play({ final: state, title, snapshot });
  } catch (e) {
    fail(e);
    applyState(state, { render: true });
  } finally {
    S.healing = false;
    renderActionbar();
  }
});

// =====================================================================
// Quality incident ("lot" and "recall" scenarios): no compromise, a
// sequence of human decisions guided in the dock. The supplier is never
// blacklisted: only the faulty lot and what derives from it is isolated.
// =====================================================================

function incident() { return S.state?.scenario?.incident || null; }
function qualityLot() { const inc = incident(); return inc?.lot || inc?.suspect_lot; }

async function loadReports() {
  if (!incident()) { S.reports = []; return; }
  try { S.reports = await api('GET', '/api/reports'); } catch { S.reports = S.reports || []; }
}

// The lot is isolated when an operation carrying it is blocked.
function isolated(lot) {
  return !!lot && S.state.records.some((r) => r.payload?.lot === lot && r.status === 'quarantined');
}

// Receipt of the faulty product in a ledger (where the defect is found).
function receiptOf(company, ref) {
  const r = S.state.records.find((x) => x.company === company && x.kind === 'goods_receipt'
    && (x.payload?.lot === ref || (x.label || '').includes(ref)));
  return r?.id || ref;
}

function qualitySteps() {
  const inc = incident();
  if (!inc) return [];
  const reports = S.reports || [];
  const sent = (from) => reports.filter((r) => r.from === from);
  const decided = (from) => sent(from).some((r) => r.status !== 'pending');
  const fab = inc.company;
  if (inc.type === 'lot') {
    return [
      { who: fab, label: `Isolate lot ${inc.lot}`, done: () => isolated(inc.lot), go: () => isolateLot(fab, inc.lot, inc.reason) },
      { who: fab, label: 'Report to the supplier', done: () => sent(fab).length > 0, go: () => report(fab, inc.lot, inc.reason) },
      { who: 'fournisseur', label: 'The supplier confirms', done: () => decided(fab), go: () => decide(fab) },
    ];
  }
  const tgt = inc.target, lot = inc.suspect_lot;
  return [
    { who: 'client', label: `Report a breakage on ${tgt}`, done: () => sent('client').length > 0,
      go: () => report('client', receiptOf('client', tgt), 'Breakage on site: defective finished product') },
    { who: 'distributeur', label: 'Confirm the report', done: () => decided('client'), go: () => decide('client') },
    { who: 'distributeur', label: 'Escalate to the manufacturer', done: () => sent('distributeur').length > 0,
      go: () => report('distributeur', receiptOf('distributeur', tgt), 'Customer report confirmed, escalated to the manufacturer') },
    { who: fab, label: `Trace the origin of ${tgt}`, done: () => isolated(lot),
      go: () => openRecall({ company: fab, ref: sent('distributeur')[0]?.records?.[0] || tgt, lot, reason: inc.reason }) },
    { who: fab, label: 'Report to the supplier', done: () => sent(fab).length > 0, go: () => report(fab, lot, inc.reason) },
    { who: 'fournisseur', label: 'The supplier confirms', done: () => decided(fab), go: () => decide(fab) },
  ];
}

function isolateLot(company, lot, reason) {
  return run(`Lot ${lot} isolated · ${F.ROLE_SHORT[company] || companyName(company)}`,
    () => api('POST', '/api/lots/suspect', { company, lot, reason }), { source: company });
}

function report(company, ref, reason) {
  return run(`Quality report · ${F.ROLE_SHORT[company] || companyName(company)}`, async () => {
    await api('POST', '/api/reports', { company, ref, reason });
    S.reports = await api('GET', '/api/reports');
    return api('GET', '/api/state');
  }, { source: company });
}

function decide(from) {
  const r = (S.reports || []).find((x) => x.from === from && x.status === 'pending');
  if (!r) return;
  return run(`Report confirmed · ${F.ROLE_SHORT[r.to] || companyName(r.to)}`, async () => {
    await api('POST', `/api/reports/${encodeURIComponent(r.id)}/decision`, { company: r.to, decision: 'confirm' });
    S.reports = await api('GET', '/api/reports');
    return api('GET', '/api/state');
  }, { source: r.to });
}

function liftLot() {
  const inc = incident();
  return run(`Lot ${qualityLot()} released`, () => api('POST', '/api/lots/suspect/withdraw', { company: inc.company, lot: qualityLot() }), { source: inc.company });
}

// =====================================================================
// Keyboard: Esc closes, → chains the five demo steps
// =====================================================================

// 3-minute demo (brief §6): declare, with vs without, prove, heal, verify.
let demo = 0;
function proofTarget() {
  const q = S.state.records.filter((r) => S.status.get(r.id) === 'quarantined');
  return (q.find((r) => r.kind === 'payment') || q.find((r) => r.gate) || q[0])?.id;
}
function healTarget() {
  // The lot receipt: remediating there releases the whole downstream branch up to the customer.
  const q = S.state.records.filter((r) => S.status.get(r.id) === 'quarantined');
  const receipt = q.find((r) => r.kind === 'goods_receipt' && r.company === 'fabricant')
    || q.find((r) => r.kind === 'goods_receipt');
  return (receipt || q[0])?.id;
}

async function nextGesture() {
  if (S.playing || busy) return;
  closeMenus();
  if (incident()) {
    // Quality incident: the next step is derived from reports and statuses.
    const inc = incident();
    if (drawerIs('recall')) { closeDrawer(); return isolateLot(inc.company, qualityLot(), inc.reason); }
    const step = qualitySteps().find((x) => !x.done());
    if (step) return step.go();
    closeDrawer(); closeVersus(); return refreshHeads(true);
  }
  // The step is derived from state: a mouse click or a reload does not shift anything.
  const declared = S.compromised.size > 0;
  if (!declared) {
    // After a remediation then a withdrawal, some records stay "released":
    // start again from a clean scene so the numbers match the pitch.
    if ([...S.status.values()].some((s) => s !== 'ok')) await resetTo(S.state.scenario?.id, { quiet: true });
    demo = 1;
    return declare();
  }
  if (demo < 1) demo = 1;
  const gestures = [
    null,
    () => { closeDrawer(); openVersus(); },
    () => { closeVersus(); const id = proofTarget(); if (id) openProof(id); },
    () => { closeDrawer(); closeVersus(); const id = healTarget(); if (id) remediate(id, 'human_approval'); },
    () => { closeDrawer(); closeVersus(); refreshHeads(true); },
  ];
  const g = gestures[Math.min(demo, gestures.length - 1)];
  demo = Math.min(demo + 1, gestures.length - 1);
  await g();
}

function bindKeys() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if ($('.menu.open')) { closeMenus(); return; }
      if (drawerOpen()) { closeDrawer(); return; }
      if (versusOpen()) { closeVersus(); return; }
    }
    const typing = e.target.closest?.('input, textarea, select, [contenteditable]');
    if (typing || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight' && !e.target.closest?.('.menu, .tabs')) { e.preventDefault(); nextGesture(); }
  });
}

boot();
