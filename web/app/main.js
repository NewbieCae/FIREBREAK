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
  closeDrawer, closeVersus, drawerIs, drawerOpen, openAudit, openChain, openIngest, openProof, openRecall, openVersus,
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
    await loadReports();
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
  const blocked = [...S.status.values()].includes('quarantined');
  const inc = S.compromised.size > 0 || blocked;
  const st = $('#sceneState');
  st.className = `s-state ${S.playing ? (S.healing ? 'healing' : 'incident') : inc ? 'incident' : ''}`;
  document.body.classList.toggle('incident', S.playing ? !S.healing : inc);
  st.querySelector('span:last-child').textContent = S.playing
    ? (S.healing ? 'Levée en cascade…' : 'Propagation en cours…')
    : incident()
      ? (blocked ? 'Incident qualité · lot isolé' : S.reports.length ? 'Signalement qualité en cours' : 'La chaîne tourne')
      : inc
        ? 'Incident en cours · confinement ciblé'
        : 'La chaîne tourne';
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
  // Ancrage Avalanche (optionnel) : rien n'est affiché si absent ou éteint.
  try {
    const st = await api('GET', '/api/chain/status');
    S.chain = st;
    const on = st && st.mode !== 'off';
    $('#chainChip').hidden = !on;
    if (!on) return;
    $('#chainChip').classList.toggle('off', !st.connected);
    const q = st.queue || {};
    const busy = (q.pending || 0) + (q.sent || 0);
    $('#chainLabel').textContent = !st.connected ? 'Avalanche · hors ligne'
      : busy ? `Avalanche · ${busy} en cours` : `Avalanche · ${F.n(q.confirmed || 0)} ancré(s)`;
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
      const h = document.querySelector(`.company[data-company="${F.esc(j.company)}"] [data-head]`);
      if (!h) continue;
      h.textContent = j.entries ? `${F.n(j.entries)} · ${F.tok(j.head, 4, 4)}` : 'vide';
      const mark = h.nextElementSibling;
      mark.className = j.entries ? (j.ok ? 'okmark' : 'badmark') : '';
      mark.innerHTML = j.entries ? icon(j.ok ? 'check' : 'close', 's16') : '';
      mark.title = j.ok ? 'Chaîne de hash intacte' : 'Chaîne de hash cassée';
      if (j.onchain) {
        mark.className = j.ok && j.onchain.matches ? 'okmark' : 'badmark';
        mark.innerHTML = icon(j.onchain.matches ? 'chain' : 'leak', 's16');
        if (j.onchain.matches) mark.style.color = 'var(--accent)';
        mark.title = j.onchain.matches ? `Ancré sur Avalanche, bloc ${j.onchain.block}` : "Ne correspond plus à l'ancrage Avalanche";
      } else mark.style.color = '';
    }
    if (loud) {
      const n = v.journals.reduce((a, j) => a + j.entries, 0);
      const chain = v.onchain_ok == null ? '' : v.onchain_ok
        ? ' Têtes ancrées sur Avalanche : elles correspondent.'
        : ' Attention : un journal ne correspond plus à son ancrage Avalanche.';
      const good = v.ok && v.onchain_ok !== false;
      toast(v.ok
        ? n ? `Journaux d'audit intacts : ${F.n(n)} entrée${n > 1 ? 's' : ''}, ${v.journals.length} chaînes de hash vérifiées.${chain}`
          : `Journaux d'audit vides et intacts : aucun événement depuis la réinitialisation.`
        : `Chaîne cassée : ${companyName(v.first_broken.company)}, entrée #${v.first_broken.index}.`,
      { tone: good ? 'info' : 'err', ttl: 5000 });
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
  const q = [...S.status.values()].filter((s) => s === 'quarantined').length;
  const proofHint = `<span class="hint">${q ? `${icon('arrow', 's16')}Cliquez sur une opération rouge : chemin, explication, reprise` : `${icon('check', 's16')}Plus aucune opération bloquée`}</span>`;
  if (incident()) {
    const steps = qualitySteps();
    const i = steps.findIndex((x) => !x.done());
    if (i >= 0) {
      const st = steps[i];
      bar.innerHTML = `<div class="dock"><span class="step">Étape <b>${i + 1}</b>/${steps.length} · ${F.esc(F.ROLE_SHORT[st.who] || st.who)}</span>
        <button class="btn declare" id="qualityBtn">${i === 0 ? '<span class="rec"></span>' : ''}<span>${F.esc(st.label)}</span>${i ? icon('arrow', 's18') : ''}</button>
        <span class="hint"><span class="kbd">→</span>geste suivant</span></div>`;
      $('#qualityBtn').addEventListener('click', () => st.go());
    } else {
      bar.innerHTML = `<div class="dock"><span class="step"><b>Incident traité</b> · fournisseur non blacklisté</span>
        ${isolated(qualityLot()) ? `<button class="btn" id="liftBtn">${icon('release')}<span>Lever le lot ${F.esc(qualityLot())}</span></button>` : ''}
        <span class="sep"></span>${proofHint}</div>`;
      $('#liftBtn')?.addEventListener('click', liftLot);
    }
  } else if (!inc) {
    bar.innerHTML = `<div class="dock"><button class="btn declare" id="declareBtn"><span class="rec"></span><span>${F.esc(declareLabel())}</span></button>
      <span class="hint"><span class="kbd">→</span>geste suivant</span></div>`;
    $('#declareBtn').addEventListener('click', declare);
  } else {
    bar.innerHTML = `<div class="dock"><button class="btn compare" id="compareBtn">${icon('compare')}<span>Avec vs sans Firebreak</span></button>
      <button class="btn" id="withdrawBtn">${icon('falseAlarm')}<span>Fausse alerte</span></button>
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
  // Les ancrages partent en arrière-plan : on relit l'état de la chaîne un peu après.
  probeChain(); setTimeout(probeChain, 2500);
});
on('audit-changed', () => refreshHeads());

// =====================================================================
// Actions
// =====================================================================

let busy = false;
async function run(title, call, { source = null } = {}) {
  if (S.playing || busy) {
    toast('Une séquence est en cours : attendez sa fin.', { tone: 'info', ttl: 2500 });
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
  return run('Déclaration de compromission', () => api('POST', '/api/compromise', { company: c.company, since: c.since }), { source: c.company });
}

function withdraw() {
  const src = [...S.compromised][0];
  if (!src) return;
  return run('Fausse alerte : déclaration retirée', () => api('POST', '/api/compromise/withdraw', { company: src }), { source: src });
}

function remediate(id, action) {
  const r = S.recs.get(id);
  return run(`Remédiation : ${r?.label || id}`, () => api('POST', `/api/records/${encodeURIComponent(id)}/remediate`, { action }));
}

async function replay() {
  if (S.playing || busy || !S.snapshot) return;
  closeDrawer();
  closeVersus();
  try {
    await play({ title: `Rejeu — ${S.lastAction || 'dernière action'}`, snapshot: S.snapshot });
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
    if (!quiet) toast(`Scénario « ${st.scenario?.label || scenario} » prêt : ${F.n(st.records.length)} opérations, aucune déclaration.`, { tone: 'info', ttl: 3200 });
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
// Incident qualité (scénarios « lot » et « recall ») : pas de compromission,
// une suite de décisions humaines guidée dans le dock. Le fournisseur n'est
// jamais blacklisté : seul le lot en cause et ce qui en dérive est isolé.
// =====================================================================

function incident() { return S.state?.scenario?.incident || null; }
function qualityLot() { const inc = incident(); return inc?.lot || inc?.suspect_lot; }

async function loadReports() {
  if (!incident()) { S.reports = []; return; }
  try { S.reports = await api('GET', '/api/reports'); } catch { S.reports = S.reports || []; }
}

// Le lot est isolé quand une opération qui le porte est bloquée.
function isolated(lot) {
  return !!lot && S.state.records.some((r) => r.payload?.lot === lot && r.status === 'quarantined');
}

// Réception du produit en cause dans un registre (là où le défaut est constaté).
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
      { who: fab, label: `Isoler le lot ${inc.lot}`, done: () => isolated(inc.lot), go: () => isolateLot(fab, inc.lot, inc.reason) },
      { who: fab, label: 'Signaler au fournisseur', done: () => sent(fab).length > 0, go: () => report(fab, inc.lot, inc.reason) },
      { who: 'fournisseur', label: 'Le fournisseur confirme', done: () => decided(fab), go: () => decide(fab) },
    ];
  }
  const tgt = inc.target, lot = inc.suspect_lot;
  return [
    { who: 'client', label: `Signaler une casse sur ${tgt}`, done: () => sent('client').length > 0,
      go: () => report('client', receiptOf('client', tgt), 'Casse sur chantier : produit fini défectueux') },
    { who: 'distributeur', label: 'Confirmer le signalement', done: () => decided('client'), go: () => decide('client') },
    { who: 'distributeur', label: 'Remonter au fabricant', done: () => sent('distributeur').length > 0,
      go: () => report('distributeur', receiptOf('distributeur', tgt), 'Signalement client confirmé, remonté au fabricant') },
    { who: fab, label: `Analyser l'origine de ${tgt}`, done: () => isolated(lot),
      go: () => openRecall({ company: fab, ref: sent('distributeur')[0]?.records?.[0] || tgt, lot, reason: inc.reason }) },
    { who: fab, label: 'Signaler au fournisseur', done: () => sent(fab).length > 0, go: () => report(fab, lot, inc.reason) },
    { who: 'fournisseur', label: 'Le fournisseur confirme', done: () => decided(fab), go: () => decide(fab) },
  ];
}

function isolateLot(company, lot, reason) {
  return run(`Lot ${lot} isolé · ${F.ROLE_SHORT[company] || companyName(company)}`,
    () => api('POST', '/api/lots/suspect', { company, lot, reason }), { source: company });
}

function report(company, ref, reason) {
  return run(`Signalement qualité · ${F.ROLE_SHORT[company] || companyName(company)}`, async () => {
    await api('POST', '/api/reports', { company, ref, reason });
    S.reports = await api('GET', '/api/reports');
    return api('GET', '/api/state');
  }, { source: company });
}

function decide(from) {
  const r = (S.reports || []).find((x) => x.from === from && x.status === 'pending');
  if (!r) return;
  return run(`Signalement confirmé · ${F.ROLE_SHORT[r.to] || companyName(r.to)}`, async () => {
    await api('POST', `/api/reports/${encodeURIComponent(r.id)}/decision`, { company: r.to, decision: 'confirm' });
    S.reports = await api('GET', '/api/reports');
    return api('GET', '/api/state');
  }, { source: r.to });
}

function liftLot() {
  const inc = incident();
  return run(`Lot ${qualityLot()} levé`, () => api('POST', '/api/lots/suspect/withdraw', { company: inc.company, lot: qualityLot() }), { source: inc.company });
}

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
  if (S.playing || busy) return;
  closeMenus();
  if (incident()) {
    // Incident qualité : l'étape suivante se déduit des signalements et des statuts.
    const inc = incident();
    if (drawerIs('recall')) { closeDrawer(); return isolateLot(inc.company, qualityLot(), inc.reason); }
    const step = qualitySteps().find((x) => !x.done());
    if (step) return step.go();
    closeDrawer(); closeVersus(); return refreshHeads(true);
  }
  // Le geste se déduit de l'état : un clic à la souris ou un rechargement ne décale rien.
  const declared = S.compromised.size > 0;
  if (!declared) {
    // Après une remédiation puis un retrait, des records restent « released » :
    // on repart d'une scène propre pour que les chiffres soient ceux du pitch.
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
