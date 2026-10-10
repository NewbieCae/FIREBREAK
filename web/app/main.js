// FIREBREAK — interface finale (docs/brief-ui.md).
// Une seule page, sans navigation : les écrans sont des états de la même scène.
import { S, $, $$, api, el, on, fail, toast, hydrateIcons, companyName, wait } from './core.js';
import { icon, logo } from './icons.js';
import * as F from './format.js';
import {
  applyState, applyView, bindMap, clearFx, feedLoad, feedReset, highlight, measure, play,
  snapshotBefore, takeSnapshot,
} from './scene.js';
import {
  closeDrawer, closeVersus, drawerIs, drawerOpen, openAudit, openIngest, openProof, openVersus,
  setAi, setSnapshotFn, versusOpen,
} from './panels.js';

// =====================================================================
// Démarrage
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
    $('#app').classList.remove('boot');
    renderScenario();
    renderMenus();
    feedReset();
    if (tl.steps.length) {
      S.snapshot = snapshotBefore(tl.steps);
      S.lastAction = 'Dernière action';
      feedLoad(tl.steps, 'Dernière action');
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
// En-tête : scénario, vue partenaire, IA, import, réinitialisation
// =====================================================================

function renderScenario() {
  const sc = S.state.scenario || {};
  $('#scTitle').textContent = sc.label || 'Scénario';
  $('#scDesc').innerHTML = `<span title="${F.esc(sc.description || '')}">${F.esc(sc.description || '')}</span>`;
  const inc = S.compromised.size > 0;
  const st = $('#sceneState');
  st.className = `s-state ${S.playing ? (S.healing ? 'healing' : 'incident') : inc ? 'incident' : ''}`;
  st.querySelector('span:last-child').textContent = S.playing
    ? (S.healing ? 'Levée en cascade…' : 'Propagation en cours…')
    : inc
      ? 'Incident en cours · confinement ciblé'
      : 'La chaîne tourne';
}

function menu(btn, list, items, onPick) {
  list.innerHTML = items.map((it) => `<button role="option" data-v="${it.value}" aria-selected="${it.selected}">
    <span class="tick">${icon('check', 's16')}</span><span class="t">${F.esc(it.title)}</span>${it.desc ? `<span class="d">${F.esc(it.desc)}</span>` : '<span></span>'}</button>`).join('');
  list.querySelectorAll('[role="option"]').forEach((o) => o.addEventListener('click', () => {
    closeMenus();
    onPick(o.dataset.v);
  }));
}

function renderMenus() {
  const sc = S.state.scenario?.id;
  const cur = S.scenarios.find((s) => s.id === sc);
  $('#scenarioBtn').innerHTML = `${icon('lot', 's18')}<span class="lbl">Scénario</span><span>${F.esc(cur?.label || sc || '—')}</span>${icon('chevron', 's16')}`;
  menu($('#scenarioBtn'), $('#scenarioMenu'), S.scenarios.map((s) => ({
    value: s.id, title: s.label, desc: s.description, selected: s.id === sc,
  })), (v) => resetTo(v));

  const view = S.view;
  $('#viewBtn').innerHTML = `${icon('eye', 's18')}<span class="lbl">Voir comme</span><span>${view === 'all' ? 'Toute la chaîne' : F.ROLE_SHORT[view] || companyName(view)}</span>${icon('chevron', 's16')}`;
  menu($('#viewBtn'), $('#viewMenu'), [
    { value: 'all', title: 'Toute la chaîne', desc: 'Vue de démonstration : les quatre registres.', selected: view === 'all' },
    ...S.state.companies.map((c) => ({
      value: c.id, title: `${F.ROLE_SHORT[c.id] || c.name} — ${c.name}`,
      desc: 'Ne voit que son registre et les alertes signées reçues.', selected: view === c.id,
    })),
  ], (v) => { S.view = v; applyView(); renderMenus(); });
}

function closeMenus() {
  $$('.menu.open').forEach((m) => m.classList.remove('open'));
  $$('.menu-btn[aria-expanded="true"]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
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
  $('#scrim').addEventListener('click', closeDrawer);
}

async function probeChain() {
  // Ancrage Avalanche (optionnel) : rien n'est affiché si absent ou éteint.
  try {
    const st = await api('GET', '/api/chain/status');
    if (!st || st.mode === 'off') return;
    $('#chainChip').hidden = false;
    $('#chainChip').classList.toggle('off', !st.connected);
    $('#chainLabel').textContent = `Avalanche · ${st.connected ? 'ancré' : 'hors ligne'}`;
  } catch { /* endpoint absent : normal */ }
}

async function probeAi() {
  // Indicateur d'IA : on lit `source` d'une explication (gabarit simulé par défaut).
  const any = S.state.records.find((r) => r.status === 'quarantined') || S.state.records[0];
  if (!any || S.ai) return;
  try {
    const ex = await api('GET', `/api/records/${encodeURIComponent(any.id)}/explain`);
    if (!S.ai) setAi(ex.source);
  } catch { /* silencieux : l'indicateur garde sa valeur */ }
}

// Têtes des journaux d'audit, vérifiées (chaîne de hash).
async function refreshHeads(loud = false) {
  try {
    const v = await api('GET', '/api/audit/verify');
    for (const j of v.journals) {
      const h = document.querySelector(`.company[data-company="${j.company}"] [data-head]`);
      if (h) h.innerHTML = j.entries
        ? `${F.n(j.entries)} · ${F.tok(j.head, 4, 4)} <span class="${j.ok ? 'okmark' : 'badmark'}">${icon(j.ok ? 'check' : 'close', 's16')}</span>`
        : 'vide';
    }
    if (loud) {
      const n = v.journals.reduce((a, j) => a + j.entries, 0);
      toast(v.ok
        ? `Journaux d'audit intacts : ${F.n(n)} entrées, ${v.journals.length} chaînes de hash vérifiées.`
        : `Chaîne cassée : ${companyName(v.first_broken.company)}, entrée #${v.first_broken.index}.`,
      { tone: v.ok ? 'info' : 'err', ttl: 4000 });
    }
  } catch (e) {
    if (loud) fail(e, () => refreshHeads(true));
  }
}

// =====================================================================
// Barre d'action
// =====================================================================

function declareLabel() {
  const c = S.state.scenario?.compromise;
  if (!c) return 'Déclarer une compromission';
  return `Déclarer ${F.ROLE_LABEL[c.company] || companyName(c.company)} compromis depuis ${F.hourFr(c.since)}`;
}

function renderActionbar() {
  const bar = $('#actionbar');
  const inc = S.compromised.size > 0;
  if (!inc) {
    bar.innerHTML = `<button class="btn declare" id="declareBtn">${icon('declaration')}<span>${F.esc(declareLabel())}</span></button>
      <span class="hint"><span class="kbd">→</span>geste suivant</span>`;
    $('#declareBtn').addEventListener('click', declare);
  } else {
    const q = [...S.status.values()].filter((s) => s === 'quarantined').length;
    bar.innerHTML = `<button class="btn compare" id="compareBtn">${icon('compare')}<span>Avec vs sans Firebreak</span></button>
      <button class="btn" id="withdrawBtn">${icon('falseAlarm')}<span>Fausse alerte</span></button>
      <span class="sep"></span>
      <span class="hint">${q ? `${icon('arrow', 's16')}Cliquez une opération rouge : chemin, explication, reprise` : `${icon('check', 's16')}Plus aucune opération bloquée`}</span>`;
    $('#compareBtn').addEventListener('click', openVersus);
    $('#withdrawBtn').addEventListener('click', withdraw);
  }
  bar.querySelectorAll('button').forEach((b) => { b.disabled = S.playing; });
  $('#replayBtn').disabled = S.playing || !S.snapshot;
  $('#resetBtn').disabled = false;
  renderScenario();
}

on('playing', () => renderActionbar());
on('settled', () => { renderActionbar(); renderMenus(); refreshHeads(); applyView(); });

// =====================================================================
// Actions
// =====================================================================

async function run(title, call, { healing = false, source = null } = {}) {
  if (S.playing) return;
  const snapshot = takeSnapshot();
  try {
    const final = await call();
    S.lastAction = title;
    S.healing = healing;
    await play({ final, title, snapshot, source });
  } catch (e) {
    fail(e, () => run(title, call, { healing, source }));
  } finally {
    S.healing = false;
    renderScenario();
  }
}

function declare() {
  const c = S.state.scenario?.compromise;
  if (!c) return;
  return run('Déclaration de compromission', () => api('POST', '/api/compromise', { company: c.company, since: c.since }), { source: c.company });
}

function withdraw() {
  const src = [...S.compromised][0];
  if (!src) return;
  return run('Fausse alerte : déclaration retirée', () => api('POST', '/api/compromise/withdraw', { company: src }), { healing: true, source: src });
}

function remediate(id, action) {
  const r = S.recs.get(id);
  return run(`Remédiation : ${r?.label || id}`, () => api('POST', `/api/records/${encodeURIComponent(id)}/remediate`, { action }), { healing: true });
}

async function replay() {
  if (S.playing || !S.snapshot) return;
  closeDrawer();
  if (versusOpen()) closeVersus();
  S.healing = /Remédiation|Fausse/.test(S.lastAction || '');
  await play({ title: `Rejeu — ${S.lastAction || 'dernière action'}`, snapshot: S.snapshot });
  S.healing = false;
  renderScenario();
}

async function resetTo(scenario) {
  S.abort?.abort();
  closeDrawer();
  if (versusOpen()) closeVersus();
  try {
    const st = await api('POST', '/api/reset', scenario ? { scenario } : undefined);
    clearFx();
    S.snapshot = null;
    S.lastAction = null;
    demo = 0;
    applyState(st, { render: true });
    feedReset();
    renderMenus();
    renderActionbar();
    refreshHeads();
    toast(`Scénario « ${st.scenario?.label || scenario} » prêt : ${F.n(st.records.length)} opérations, aucune déclaration.`, { tone: 'info', ttl: 3200 });
  } catch (e) {
    fail(e, () => resetTo(scenario));
  }
}

on('open-proof', (id) => { if (versusOpen()) closeVersus(); openProof(id); });
on('open-audit', (co) => openAudit(co));
on('remediate', ({ id, action }) => remediate(id, action));
on('highlight', (id) => highlight(id));
on('ingested', ({ state, snapshot, title }) => {
  S.lastAction = title;
  play({ final: state, title, snapshot });
});

// =====================================================================
// Clavier : Échap ferme, → enchaîne les cinq gestes de la démo
// =====================================================================

// Démo de 3 minutes (brief §6) : déclarer, avec vs sans, prouver, guérir, vérifier.
let demo = 0;
function proofTarget() {
  const q = S.state.records.filter((r) => S.status.get(r.id) === 'quarantined');
  return (q.find((r) => r.kind === 'payment') || q.find((r) => r.gate) || q[0])?.id;
}
function healTarget() {
  // La réception de lot : remédier là libère toute la branche aval jusqu'au client.
  const q = S.state.records.filter((r) => S.status.get(r.id) === 'quarantined');
  const receipt = q.find((r) => r.kind === 'goods_receipt' && r.company === 'fabricant')
    || q.find((r) => r.kind === 'goods_receipt');
  return (receipt || q[0])?.id;
}

async function nextGesture() {
  if (S.playing) return;
  closeMenus();
  if (S.compromised.size === 0) demo = 0;
  const gestures = [
    () => declare(),
    () => openVersus(),
    () => { closeVersus(); const id = proofTarget(); if (id) openProof(id); },
    () => { closeDrawer(); const id = healTarget(); if (id) remediate(id, 'human_approval'); },
    () => refreshHeads(true),
  ];
  const g = gestures[Math.min(demo, gestures.length - 1)];
  demo = Math.min(demo + 1, gestures.length);
  await g();
}

function bindKeys() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if ($('.menu.open')) { closeMenus(); return; }
      if (versusOpen()) { closeVersus(); return; }
      if (drawerOpen()) { closeDrawer(); return; }
    }
    const typing = e.target.closest?.('input, textarea, select, [contenteditable]');
    if (typing || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight' && !e.target.closest?.('.menu, .tabs')) { e.preventDefault(); nextGesture(); }
  });
}

boot();
