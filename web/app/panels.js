// Panels: the proof (operation details), the audit log,
// document import, and the "With or without Firebreak" screen.
import { S, $, api, el, emit, fail, toast, companyName, API } from './core.js';
import { icon, COMPANY_ICON } from './icons.js';
import * as F from './format.js';

// =====================================================================
// Side drawer (a single one, swappable content)
// =====================================================================

let lastFocus = null;
let drawerKind = null;
let drawerToken = 0;

export function drawerOpen() { return $('#drawer').classList.contains('on'); }
export function drawerIs(kind, id) { return drawerOpen() && drawerKind === kind && (id == null || $('#drawer').dataset.id === id); }

function openDrawer(kind, html, id = '') {
  const d = $('#drawer');
  if (!drawerOpen()) lastFocus = document.activeElement;
  drawerKind = kind;
  d.dataset.id = id;
  d.innerHTML = html;
  d.inert = false;
  d.classList.add('on');
  $('#scrim').classList.add('on');
  syncInert();
  d.querySelector('[data-close]')?.addEventListener('click', closeDrawer);
  requestAnimationFrame(() => d.focus({ preventScroll: true }));
  drawerToken++;
  return drawerToken;
}

export function closeDrawer() {
  const d = $('#drawer');
  if (!drawerOpen()) return;
  d.classList.remove('on');
  d.inert = true;
  $('#scrim').classList.remove('on');
  drawerKind = null;
  drawerToken++;
  syncInert();
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
}

// The scene behind a drawer or the "with vs without" screen is no longer keyboard-reachable.
function syncInert() {
  $('#app').inert = drawerOpen() || versusOpen();
}

const closeBtn = `<button class="btn ghost icon" data-close aria-label="Close (Esc)" title="Close (Esc)">${icon('close', 's20')}</button>`;

function head({ ico, tone = '', title, sub }) {
  return `<header class="drawer-head">
    <div class="d-ico ${tone}">${icon(ico)}</div>
    <div style="min-width:0"><h2 class="d-title">${title}</h2><div class="d-sub">${sub || ''}</div></div>
    ${closeBtn}
  </header>`;
}

// =====================================================================
// 4.5 The proof
// =====================================================================

function statusBadge(s) {
  const st = F.STATUS[s] || { label: s, cls: 'n' };
  return `<span class="badge ${st.cls}">${st.label}</span>`;
}

function alertFrom(origin, company) {
  return (S.state.alerts || []).filter((a) => a.from === origin && a.to === company && a.type === 'taint').pop();
}

function pathHtml(recs, currentId) {
  if (!recs.length) return '';
  const first = recs[0];
  const items = [];
  // Seed received from a partner: the proof starts with its signed alert.
  if (first.token && first.origin && first.origin !== first.company) {
    const a = alertFrom(first.origin, first.company);
    const ok = !a || a.verified !== false;
    items.push(`<li class="alert">
      <div class="p-node">${icon(ok ? 'alert' : 'alertBad', 's18')}</div>
      <div><div class="p-label">Signed alert received · ${F.esc(companyName(first.origin))}</div>
      <div class="p-meta"><span class="badge ${ok ? 'a' : 'q'}">${ok ? 'signature verified' : 'signature rejected'}</span>
      <span>token <span class="mono">${F.tok(first.token)}</span></span><span>no label or amount shared</span></div></div></li>`);
  }
  recs.forEach((r, i) => {
    const s = S.status.get(r.id) || r.status;
    const tone = s === 'quarantined' ? '' : s === 'released' ? 'r' : 'ok';
    const origin = i === 0 ? '<span class="badge q">origin</span>' : '';
    const from = r.origin && r.origin !== r.company ? `<span>issued by ${F.esc(companyName(r.origin))}</span>` : '';
    const lbl = r.id === currentId
      ? `<div class="p-label">${F.esc(r.label)}</div>`
      : `<button class="p-label" data-goto="${F.esc(r.id)}">${F.esc(r.label)}</button>`;
    items.push(`<li class="${tone} ${r.id === currentId ? 'current' : ''}" style="animation-delay:${(i + 1) * 70}ms">
      <div class="p-node">${icon(F.kindIcon(r.kind), 's18')}</div>
      <div>${lbl}<div class="p-meta">${origin}<span>${F.kindLabel(r.kind)}</span><span class="mono">${F.hm(r.ts)}</span>${from}${r.gate ? `<span>${icon('gate', 's16')}</span>` : ''}</div></div></li>`);
  });
  return `<ol class="path">${items.join('')}</ol>`;
}

export async function openProof(id) {
  const r = S.recs.get(id);
  if (!r) return;
  const s = S.status.get(id) || r.status;
  const tone = s === 'quarantined' ? 'q' : s === 'released' ? 'r' : 'ok';
  const path = (r.taint_path || []).map((x) => S.recs.get(x)).filter(Boolean);
  const facts = [];
  if (r.payload?.amount != null) facts.push(`<div class="fact surface"><div class="f-k">Amount</div><div class="f-v big">${F.eur(r.payload.amount)}</div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">Type</div><div class="f-v">${F.kindLabel(r.kind)}</div></div>`);
  if (r.payload?.rib) facts.push(`<div class="fact surface wide"><div class="f-k">Bank details ${r.payload.previous_rib ? '(new)' : ''}</div><div class="f-v mono">${F.esc(r.payload.rib)}</div></div>`);
  if (r.payload?.lot) facts.push(`<div class="fact surface"><div class="f-k">Lot</div><div class="f-v mono">${F.esc(r.payload.lot)}</div></div>`);
  if (r.origin && r.origin !== r.company) facts.push(`<div class="fact surface"><div class="f-k">Issued by</div><div class="f-v">${F.esc(companyName(r.origin))}</div></div>`);
  if (r.token) facts.push(`<div class="fact surface wide"><div class="f-k">Received token (sha256, opaque)</div><div class="f-v mono">${F.tok(r.token, 10, 10)}<button class="copy" data-copy="${F.esc(r.token)}" title="Copy token" aria-label="Copy token">${icon('copy', 's16')}</button></div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">ID</div><div class="f-v mono">${F.esc(r.id)}</div></div>`);

  const chips = [statusBadge(s)];
  if (r.gate) chips.push(`<span class="badge n">${icon('gate', 's16')}Irreversible action</span>`);
  if (r.verified) chips.push(`<span class="badge a">${icon('verified', 's16')}Verified</span>`);

  let pathSec;
  if (path.length) {
    pathSec = `<section><h3 class="sec-title">${icon('taint', 's16')}Contamination path<span class="aside">${path.length} operation${path.length > 1 ? 's' : ''} · ledger ${F.esc(companyName(r.company))}</span></h3>${pathHtml(path, id)}</section>`;
  } else if (s === 'released') {
    pathSec = `<section><h3 class="sec-title">${icon('release', 's16')}Remediated</h3><div class="surface explain">Unblocked by a human action. It will no longer be contaminated and stops the propagation: its descendants resume.</div></section>`;
  } else {
    pathSec = `<section><h3 class="sec-title">${icon('verified', 's16')}No suspect dependency</h3><div class="surface explain">${r.verified
      ? 'Confirmed by a trusted source (physical check, callback). It is never contaminated and <b>stops the propagation</b>.'
      : 'None of its inputs depends on suspect data: the operation continues normally.'}</div></section>`;
  }

  const token = openDrawer('proof', `
    ${head({
      ico: F.kindIcon(r.kind), tone,
      title: F.esc(r.label),
      sub: `<span>${F.esc(companyName(r.company))}</span><span class="mono">${F.dayFr(r.ts)} · ${F.hm(r.ts)}</span>${chips.join('')}`,
    })}
    <div class="drawer-body">
      <section class="facts">${facts.join('')}</section>
      ${pathSec}
      <section>
        <h3 class="sec-title">${icon('spark', 's16')}Explanation<span class="aside" id="pfAi"></span></h3>
        <div class="surface explain" id="pfExplain"><span class="sk line"></span><span class="sk line"></span><span class="sk line" style="width:70%"></span></div>
        <div class="explain-foot">${icon('verified', 's16')}<span>The decision comes from the graph. The AI explains.</span></div>
      </section>
      ${s === 'quarantined' ? `<section><h3 class="sec-title">${icon('release', 's16')}Recovery plan</h3><div class="plan" id="pfPlan"><div class="sk block"></div><div class="sk block"></div><div class="sk block"></div></div></section>` : ''}
      <section>
        <button class="btn ghost" data-audit="${F.esc(r.company)}">${icon('audit', 's16')}<span>Audit log · ${F.esc(companyName(r.company))}</span></button>
      </section>
    </div>`, id);

  const d = $('#drawer');
  d.querySelectorAll('[data-goto]').forEach((b) => b.addEventListener('click', () => openProof(b.dataset.goto)));
  d.querySelector('[data-copy]')?.addEventListener('click', (e) => {
    navigator.clipboard?.writeText(e.currentTarget.dataset.copy).then(() => toast('Token copied.', { tone: 'info', ttl: 2000 }), () => {});
  });
  d.querySelector('[data-audit]')?.addEventListener('click', (e) => openAudit(e.currentTarget.dataset.audit));
  emit('highlight', id);

  try {
    const ex = await api('GET', `/api/records/${encodeURIComponent(id)}/explain`);
    if (token !== drawerToken) return;
    setAi(ex.source);
    $('#pfAi').innerHTML = `<span class="badge a">AI: ${ex.source === 'bedrock' ? 'Bedrock' : 'simulated'}</span>`;
    $('#pfExplain').innerHTML = F.richText(ex.explanation);
    const plan = $('#pfPlan');
    if (plan) {
      plan.innerHTML = ex.remediation_plan.map((p) => `
        <button data-action="${F.esc(p.action)}">
          <span class="pl-ico">${icon(F.ACTION_ICON[p.action] || 'release', 's18')}</span>
          <span class="pl-t">${F.esc(p.label)}</span>
          <span class="pl-d">${F.esc(p.rationale)}</span>
          <span class="pl-go">${icon('arrow', 's18')}</span>
        </button>`).join('');
      plan.querySelectorAll('[data-action]').forEach((b) => b.addEventListener('click', () => {
        closeDrawer();
        emit('remediate', { id, action: b.dataset.action });
      }));
    }
  } catch (e) {
    if (token !== drawerToken) return;
    $('#pfExplain').textContent = 'The explanation could not be loaded.';
    fail(e, () => openProof(id));
  }
}

export function setAi(source) {
  if (!source) return;
  S.ai = source;
  $('#aiLabel').textContent = `AI: ${source === 'bedrock' ? 'Bedrock' : 'simulated'}`;
}

// =====================================================================
// Chained audit log
// =====================================================================

function auditLine(e) {
  const d = e.details || {};
  const rec = d.record ? S.recs.get(d.record) : null;
  const icoMap = {
    declaration: 'declaration', declaration_withdrawn: 'falseAlarm', alert_sent: 'alert', alert_received: 'alert',
    quarantine: 'quarantine', remediation: 'remediate', release: 'release', document_confirmed: 'file', epcis_import: 'upload',
    lot_suspect: 'lot', lot_suspect_withdrawn: 'release', quality_report_sent: 'alert', quality_report_received: 'alert', quality_report_decided: 'check',
  };
  let detail = '';
  if (rec) detail = `“${F.esc(rec.label)}”`;
  if (e.event === 'quarantine') detail += ` — rule: ${F.RULE_LABEL[d.rule] || d.rule}`;
  if (e.event === 'remediation') detail += ` — ${F.esc(d.action)}`;
  if (e.event.startsWith('alert')) {
    const n = (d.tokens || []).length;
    detail = `${d.type === 'release' ? 'Release' : 'Contamination'} · ${F.esc(companyName(d.from))} → ${F.esc(companyName(d.to))} · ${n} token${n > 1 ? 's' : ''}`;
    if (e.event === 'alert_received') detail += ` · ${d.verified ? 'signature verified' : 'signature rejected'}`;
  }
  if (e.event === 'declaration' || e.event === 'declaration_withdrawn') detail = `Source: ${F.esc(companyName(d.source))}, since ${F.hourFr(d.effective_since || d.since)}`;
  if (e.event === 'epcis_import') detail = `${(d.records || []).length} operation(s) added`;
  const bad = e.event === 'alert_received' && d.verified === false;
  return `<li>
    <div class="ci" style="${bad ? 'color:var(--q)' : ''}">${icon(icoMap[e.event] || 'dot', 's16')}</div>
    <div>
      <div class="ce">${F.AUDIT_EVENT[e.event] || F.esc(e.event)} <span class="badge n" style="height:20px;font-size:11px">${e.actor === 'humain' ? 'human' : 'rule'}</span></div>
      ${detail ? `<div class="cd">${detail}</div>` : ''}
      <div class="ch mono"><span>#${e.index}</span><span>${F.hm(e.ts)}</span><span>${F.tok(e.prev_hash, 4, 4)}</span><span class="arrow">→</span><span>${F.tok(e.hash, 4, 4)}</span></div>
    </div></li>`;
}

export async function openAudit(company) {
  // In partner view, you only see your own log.
  const companies = S.state.companies.filter((c) => S.view === 'all' || c.id === S.view);
  if (S.view !== 'all') company = S.view;
  const tabs = companies.map((c) => `<button role="tab" data-co="${F.esc(c.id)}" aria-selected="${c.id === company}">${F.ROLE_SHORT[c.id] || F.esc(c.name)}</button>`).join('');
  const token = openDrawer('audit', `
    ${head({ ico: 'audit', title: 'Audit log', sub: '<span>Append-only, hash-chained (sha256): a modified entry breaks the chain.</span>' })}
    <div class="drawer-body">
      <div class="tabs" role="tablist">${tabs}</div>
      <div id="auVerify" class="verify surface"><span class="sk line" style="width:60%"></span></div>
      <ol class="chainlist" id="auList"><li><div class="sk block" style="grid-column:span 2"></div></li></ol>
    </div>`, company);
  $('#drawer').querySelectorAll('[data-co]').forEach((b) => b.addEventListener('click', () => openAudit(b.dataset.co)));
  try {
    const [log, ver] = await Promise.all([
      api('GET', `/api/audit?company=${encodeURIComponent(company)}`),
      api('GET', `/api/audit/verify?company=${encodeURIComponent(company)}`),
    ]);
    if (token !== drawerToken) return;
    const j = ver.journals?.[0];
    const ok = ver.ok;
    $('#auVerify').className = `verify surface ${ok ? 'ok' : 'bad'}`;
    $('#auVerify').innerHTML = `${icon(ok ? 'verified' : 'leak', 's20')}<span>${ok
      ? `Local chain intact: ${F.n(j?.entries ?? log.entries.length)} entr${(j?.entries ?? log.entries.length) > 1 ? 'ies verified' : 'y verified'}`
      : `Chain broken at entry #${j?.first_broken_index}`}</span><span class="mono">${F.tok(log.head, 6, 6)}</span>`;
    const oc = j?.onchain;
    if (oc) {
      const box = el('div', `verify surface ${oc.matches ? 'ok' : 'bad'}`);
      const link = oc.explorer_link ? ` · <a href="${F.esc(oc.explorer_link)}" target="_blank" rel="noopener" style="color:var(--accent)">explorer</a>` : '';
      box.innerHTML = `${icon(oc.matches ? 'chain' : 'leak', 's20')}<span>${oc.matches
        ? `Anchored on Avalanche, block ${F.n(oc.block)}: the log matches (${F.n(oc.anchored_entries)} entries)`
        : `No longer matches the Avalanche anchor in block ${F.n(oc.block)}: log rewritten`}${link}</span><span class="mono">${F.tok(oc.anchored_head, 6, 6)}</span>`;
      if (oc.matches) box.querySelector('svg').style.color = 'var(--accent)';
      $('#auVerify').after(box);
      if (oc.matches && S.chain?.mode !== 'off' && log.entries.length) {
        const ev = log.entries.find((e) => e.event === 'alert_received') || log.entries[0];
        const b = el('button', 'btn ghost', `${icon('leak', 's16')}<span>Simulate a log rewrite (demo)</span>`);
        b.addEventListener('click', async () => {
          try {
            await api('POST', '/api/demo/rewrite', { company, drop_event: ev.event });
            emit('audit-changed');
            openAudit(company);
          } catch (err) { fail(err); }
        });
        box.after(b);
      }
    }
    $('#auList').innerHTML = log.entries.length
      ? log.entries.map(auditLine).join('')
      : `<li><div class="ci">${icon('audit', 's16')}</div><div class="cd" style="padding-top:6px">Empty log: no events since the reset.</div></li>`;
  } catch (e) {
    if (token === drawerToken) fail(e, () => openAudit(company));
  }
}

// =====================================================================
// Quality recall: trace a faulty product back to its possible causes
// =====================================================================

export async function openRecall({ company, ref, lot, reason }) {
  const token = openDrawer('recall', `
    ${head({ ico: 'lot', title: `Recall analysis · ${F.esc(ref)}`, sub: `<span>${F.esc(companyName(company))} traces the genealogy: which inputs may have caused the defect, and what a recall would affect.</span>` })}
    <div class="drawer-body">
      <section><h3 class="sec-title">${icon('lot', 's16')}Possible causes<span class="aside" id="rcCount"></span></h3>
        <div class="cands" id="rcList"><div class="sk block"></div><div class="sk block"></div><div class="sk block"></div></div></section>
      <div class="explain-foot">${icon('verified', 's16')}<span>Read-only: nothing is blocked until a human isolates a lot.</span></div>
    </div>`, ref);
  try {
    const rc = await api('GET', `/api/recall?company=${encodeURIComponent(company)}&ref=${encodeURIComponent(ref)}`);
    if (token !== drawerToken) return;
    $('#rcCount').textContent = `${rc.candidates.length} input${rc.candidates.length > 1 ? 's' : ''} · target ${rc.target?.label || ref}`;
    $('#rcList').innerHTML = rc.candidates.map((c) => {
      const hit = lot && c.lot === lot;
      const what = c.lot || c.record;
      const partners = (c.impact_partners || []).map((x) => F.ROLE_SHORT[x] || companyName(x)).join(', ');
      return `<div class="cand surface ${hit ? 'hit' : ''}">
        <div class="c-t">${icon(F.kindIcon(c.kind), 's16')}<span>${F.esc(c.label)}</span>${hit ? '<span class="badge q">likely cause</span>' : ''}</div>
        <div class="c-m">${c.lot ? `<span class="mono">${F.esc(c.lot)}</span>` : ''}<span>${c.received ? `received from ${F.esc(companyName(c.origin))}` : 'internal'}</span>
          <span>a recall would affect <b>${F.n(c.impact_records)}</b> operations, ${F.n(c.impact_gates)} of them irreversible${partners ? ` · ${F.esc(partners)}` : ''}</span></div>
        <button class="btn ${hit ? 'primary' : ''}" data-isolate="${F.esc(what)}">${icon('quarantine', 's16')}<span>Isolate</span></button>
      </div>`;
    }).join('') || '<div class="surface explain">No upstream input found for this reference.</div>';
    $('#drawer').querySelectorAll('[data-isolate]').forEach((b) => b.addEventListener('click', () => {
      closeDrawer();
      emit('isolate-lot', { company, lot: b.dataset.isolate, reason });
    }));
  } catch (e) {
    if (token === drawerToken) fail(e, () => openRecall({ company, ref, lot, reason }));
  }
}

// =====================================================================
// Proofs on Avalanche (optional: shown only if the chain is active)
// =====================================================================

const ANCHOR_KIND = { audit: 'Audit log head', alert: 'Signed alert', incident: 'Incident declaration', ack: 'Acknowledgement' };
const ANCHOR_ICON = { audit: 'audit', alert: 'alert', incident: 'declaration', ack: 'check' };
const ANCHOR_STATUS = {
  confirmed: ['a', 'confirmed'], sent: ['r', 'sent'], pending: ['r', 'pending'], failed: ['q', 'failed'],
};

export async function openChain() {
  const token = openDrawer('chain', `
    ${head({ ico: 'chain', title: 'Proofs on Avalanche', sub: '<span>Fingerprints, never business data. The chain decides nothing: it makes the proof tamper-proof.</span>' })}
    <div class="drawer-body">
      <section class="facts" id="chFacts"><div class="sk block"></div><div class="sk block"></div></section>
      <section><h3 class="sec-title">${icon('chain', 's16')}Anchors<span class="aside" id="chCount"></span></h3>
        <ol class="chainlist" id="chList"><li><div class="sk block" style="grid-column:span 2"></div></li></ol></section>
    </div>`);
  try {
    const [st, anchors] = await Promise.all([api('GET', '/api/chain/status'), api('GET', '/api/chain/anchors')]);
    if (token !== drawerToken) return;
    S.chain = st;
    const q = st.queue || {};
    $('#chFacts').innerHTML = `
      <div class="fact surface"><div class="f-k">Mode</div><div class="f-v">${st.mode === 'l1' ? 'Avalanche L1' : st.mode === 'tester' ? 'In-memory EVM (test)' : 'disabled'}</div></div>
      <div class="fact surface"><div class="f-k">Connection</div><div class="f-v" style="color:${st.connected ? 'var(--accent)' : 'var(--q)'}">${st.connected ? 'connected' : 'offline'}</div></div>
      <div class="fact surface"><div class="f-k">Chain ID</div><div class="f-v mono">${F.esc(st.chain_id ?? '—')}</div></div>
      <div class="fact surface"><div class="f-k">Latest block</div><div class="f-v mono">${F.esc(st.last_block ?? '—')}</div></div>
      <div class="fact surface wide"><div class="f-k">Contract</div><div class="f-v mono">${F.esc(st.contract || '—')}</div></div>
      <div class="fact surface wide"><div class="f-k">Send queue</div><div class="f-v">${F.n(q.confirmed || 0)} confirmed · ${F.n((q.pending || 0) + (q.sent || 0))} pending · ${F.n(q.failed || 0)} failed</div></div>`;
    $('#chCount').textContent = `${anchors.length} anchor${anchors.length > 1 ? 's' : ''}`;
    $('#chList').innerHTML = anchors.length ? [...anchors].reverse().map((a) => {
      const [tone, label] = ANCHOR_STATUS[a.status] || ['n', a.status];
      const link = a.explorer_link ? `<a href="${F.esc(a.explorer_link)}" target="_blank" rel="noopener" style="color:var(--accent)">explorer</a>` : '';
      return `<li><div class="ci">${icon(ANCHOR_ICON[a.kind] || 'chain', 's16')}</div><div>
        <div class="ce">${ANCHOR_KIND[a.kind] || F.esc(a.kind)} <span class="badge ${tone}" style="height:20px;font-size:11px" ${a.error ? `title="${F.esc(a.error)}"` : ''}>${label}</span></div>
        <div class="cd">${F.esc(companyName(a.company))}${a.block != null ? ` · block ${F.n(a.block)}` : ''} ${link}</div>
        <div class="ch mono"><span>${F.tok(a.hash, 6, 6)}</span>${a.tx_hash ? `<span class="arrow">tx</span><span>${F.tok(a.tx_hash, 6, 6)}</span>` : ''}</div></div></li>`;
    }).join('') : `<li><div class="ci">${icon('chain', 's16')}</div><div class="cd" style="padding-top:6px">No anchors yet: declare a compromise.</div></li>`;
  } catch (e) {
    if (token === drawerToken) fail(e, openChain);
  }
}

// =====================================================================
// 4.7 Document import (PDF, email, text, EPCIS)
// =====================================================================

const SAMPLES = [
  { file: 'facture-rib-modifie.pdf', type: 'application/pdf', title: 'Invoice with changed bank details', desc: 'PDF · F-9999', ico: 'invoice' },
  { file: 'avis-expedition.eml', type: 'message/rfc822', title: 'Shipping notice', desc: 'Email .eml · BC-1009', ico: 'mail' },
  { file: 'bon-de-commande.txt', type: 'text/plain', title: 'Purchase order', desc: 'Text · BC-7001', ico: 'order' },
  { file: 'epcis-sample.json', type: 'application/json', title: 'EPCIS events', desc: 'GS1 EPCIS 2.0 · 11 events', ico: 'globe', epcis: true },
];

let ingestCompany = 'fabricant';

function typeOf(file) {
  const n = file.name.toLowerCase();
  if (n.endsWith('.pdf')) return 'application/pdf';
  if (n.endsWith('.eml')) return 'message/rfc822';
  if (n.endsWith('.json') || n.endsWith('.jsonld')) return 'application/json';
  return file.type || 'text/plain';
}

export function openIngest() {
  const seg = S.state.companies.map((c) => `<button data-co="${F.esc(c.id)}" aria-pressed="${c.id === ingestCompany}">${F.ROLE_SHORT[c.id] || F.esc(c.name)}</button>`).join('');
  openDrawer('ingest', `
    ${head({ ico: 'upload', title: 'Import a document', sub: '<span>The AI reads, a human confirms, then the graph decides.</span>' })}
    <div class="drawer-body">
      <div class="field">Ledger receiving the document<div class="seg" id="inCo">${seg}</div></div>
      <label class="drop" id="inDrop" tabindex="0">
        ${icon('upload')}
        <span class="dt">Drop a document here</span>
        <span class="dd">PDF, .eml email, text, or EPCIS 2.0 JSON — 2 MB max</span>
        <input type="file" id="inFile" hidden accept=".pdf,.eml,.txt,.json,.jsonld,application/pdf,message/rfc822,text/plain,application/json">
      </label>
      <section><h3 class="sec-title">${icon('file', 's16')}Ready-made samples</h3>
        <div class="samples">${SAMPLES.map((s, i) => `<button data-sample="${F.esc(i)}">${icon(s.ico, 's20')}<span><span class="st">${s.title}</span><br><span class="sd">${s.desc}</span></span></button>`).join('')}</div>
      </section>
      <div id="inResult"></div>
    </div>`);
  const d = $('#drawer');
  d.querySelectorAll('#inCo [data-co]').forEach((b) => b.addEventListener('click', () => {
    ingestCompany = b.dataset.co;
    d.querySelectorAll('#inCo [data-co]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));
  const drop = $('#inDrop');
  const input = $('#inFile');
  drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', (e) => {
    e.preventDefault();
    drop.classList.remove('over');
    const f = e.dataTransfer.files?.[0];
    if (f) readFile(f, typeOf(f));
  });
  input.addEventListener('change', () => { const f = input.files?.[0]; if (f) readFile(f, typeOf(f)); });
  d.querySelectorAll('[data-sample]').forEach((b) => b.addEventListener('click', async () => {
    const s = SAMPLES[Number(b.dataset.sample)];
    try {
      const res = await fetch(`${API}/samples/${s.file}`);
      if (!res.ok) throw new Error(`Sample not found: ${s.file}`);
      const blob = await res.blob();
      readFile(blob, s.type, s.file);
    } catch (e) { fail(e); }
  }));
}

function resultSkeleton() {
  $('#inResult').innerHTML = `<section><h3 class="sec-title">${icon('spark', 's16')}Reading the document</h3><div class="sk block"></div><div class="sk line"></div><div class="sk line" style="width:60%"></div></section>`;
}

async function readFile(blob, type, name = blob.name) {
  if (blob.size > 2 * 1024 * 1024) { toast('Document too large: 2 MB maximum.'); return; }
  resultSkeleton();
  const co = ingestCompany;
  const token = drawerToken;
  try {
    if (type === 'application/json' && /epcis/i.test(name || '') || (type === 'application/json' && (await blob.slice(0, 600).text()).includes('EPCISDocument'))) {
      const before = new Set(S.recs.keys());
      const snapshot = { status: new Map([...S.status].filter(([id]) => before.has(id))), compromised: new Set(S.compromised) };
      const res = await api('POST', `/api/ingest/epcis?company=${encodeURIComponent(co)}`, blob, { raw: true, contentType: 'application/json' });
      // The records are already in the ledger server-side: show them whatever happens to the drawer.
      emit('ingested', { state: res.state, snapshot, title: 'Import EPCIS' });
      if (token === drawerToken) showEpcis(res, co);
      return;
    }
    const prop = await api('POST', `/api/ingest/document?company=${encodeURIComponent(co)}`, blob, { raw: true, contentType: type });
    if (token === drawerToken) showProposal(prop, name);
  } catch (e) {
    if (token === drawerToken && $('#inResult')) $('#inResult').innerHTML = '';
    fail(e, () => readFile(blob, type, name));
  }
}

function showProposal(p, name) {
  setAi(p.source);
  const r = p.record;
  const pl = r.payload || {};
  const facts = [
    `<div class="fact surface"><div class="f-k">Detected type</div><div class="f-v">${r.kind ? F.kindLabel(r.kind) : '<span style="color:var(--q)">not recognised</span>'}</div></div>`,
    `<div class="fact surface"><div class="f-k">Issuer</div><div class="f-v">${r.origin ? F.esc(companyName(r.origin)) : '<span style="color:var(--q)">not recognised</span>'}</div></div>`,
  ];
  if (pl.amount != null) facts.push(`<div class="fact surface"><div class="f-k">Amount</div><div class="f-v big">${F.eur(pl.amount)}</div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">Received on</div><div class="f-v mono">${F.dayFr(r.ts)} · ${F.hm(r.ts)}</div></div>`);
  if (pl.rib) facts.push(`<div class="fact surface wide"><div class="f-k">Bank details</div><div class="f-v mono">${F.esc(pl.rib)}</div></div>`);
  if (pl.previous_rib) facts.push(`<div class="fact surface wide"><div class="f-k">Previous bank details</div><div class="f-v mono">${F.esc(pl.previous_rib)}</div></div>`);
  if (pl.references?.length) facts.push(`<div class="fact surface wide"><div class="f-k">References</div><div class="f-v mono">${pl.references.map(F.esc).join(' · ')}</div></div>`);
  const warn = pl.bank_details_change
    ? `<div class="warnline surface">${icon('leak', 's20')}<span><b>New bank details.</b> ${pl.rib_unknown_for_origin ? 'These bank details have never been seen for this issuer in the ledger.' : 'The document announces a change of bank details.'}</span></div>`
    : '';
  const missing = p.missing?.length ? `<div class="cd" style="font-size:12.5px;color:var(--text-2)">Missing expected fields: ${p.missing.map(F.esc).join(', ')}</div>` : '';
  const conf = Math.round((p.confidence || 0) * 100);
  const canConfirm = r.kind && r.origin;
  $('#inResult').innerHTML = `<section>
    <h3 class="sec-title">${icon('spark', 's16')}AI proposal<span class="aside"><span class="badge a">AI: ${p.source === 'bedrock' ? 'Bedrock' : 'simulated'}</span></span></h3>
    <div class="surface explain" style="margin-bottom:10px"><div style="display:flex;gap:10px;align-items:center">${icon(F.kindIcon(r.kind))}<b>${F.esc(r.label || name || 'Document')}</b></div>
      <div style="display:flex;align-items:center;gap:10px;margin-top:10px;font-size:12.5px;color:var(--text-2)"><span>Confidence</span><div class="gauge" style="flex:1"><span style="width:${conf}%"></span></div><span class="mono">${conf}%</span></div>
    </div>
    <div class="facts">${facts.join('')}</div>
    ${warn ? `<div style="margin-top:10px">${warn}</div>` : ''}
    ${missing}
    <div style="display:flex;gap:8px;margin-top:14px">
      <button class="btn primary" id="inConfirm" ${canConfirm ? '' : 'disabled'}>${icon('check', 's18')}<span>Confirm and record in the ledger</span></button>
      <button class="btn ghost" id="inCancel">Cancel</button>
    </div>
    <div class="explain-foot">${icon('verified', 's16')}<span>Nothing enters the ledger without human confirmation. Then the graph rules apply.</span></div>
  </section>`;
  $('#inCancel').addEventListener('click', () => { $('#inResult').innerHTML = ''; });
  $('#inConfirm').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const snapshot = emitSnapshot();
      const st = await api('POST', `/api/ingest/document/${encodeURIComponent(p.id)}/confirm`);
      closeDrawer();
      emit('ingested', { state: st, snapshot, title: 'Document confirmed' });
    } catch (err) {
      btn.disabled = false;
      fail(err);
    }
  });
}

let snapshotFn = () => null;
export function setSnapshotFn(fn) { snapshotFn = fn; }
function emitSnapshot() { return snapshotFn(); }

function showEpcis(res, co) {
  const added = res.imported.length;
  $('#inResult').innerHTML = `<section>
    <h3 class="sec-title">${icon('globe', 's16')}Import EPCIS</h3>
    <div class="facts">
      <div class="fact surface"><div class="f-k">Events read</div><div class="f-v big">${F.n(res.events)}</div></div>
      <div class="fact surface"><div class="f-k">Operations added</div><div class="f-v big">${F.n(added)}</div></div>
      <div class="fact surface wide"><div class="f-k">Ledger</div><div class="f-v">${F.esc(companyName(co))}${res.ignored?.length ? ` · ${res.ignored.length} ignored` : ''}</div></div>
    </div>
    <div class="explain-foot">${icon('verified', 's16')}<span>Structured GS1 data: added right away, then subject to the same rules as the rest.</span></div>
  </section>`;
  const token = drawerToken;
  setTimeout(() => { if (token === drawerToken) closeDrawer(); }, 1600);
}

// =====================================================================
// 4.4 With or without Firebreak
// =====================================================================

export function versusOpen() { return $('#versus').classList.contains('on'); }
let versusFocus = null;
export function closeVersus() {
  if (!versusOpen()) return;
  $('#versus').classList.remove('on');
  $('#versus').innerHTML = '';
  syncInert();
  emit('versus', false);
  if (versusFocus && document.contains(versusFocus)) versusFocus.focus({ preventScroll: true });
}

function vsSide(side, cmp, sideKey, truth) {
  const blocked = new Set(side.blocked_ids || []);
  const scopeCut = new Set(Object.values(side.scope || {}).flat());
  const companies = S.state.companies;
  const cols = companies.map((c) => {
    const recs = S.state.records.filter((r) => r.company === c.id).sort((a, b) => a.ts.localeCompare(b.ts));
    const dots = recs.map((r) => {
      const b = blocked.has(r.id), t = truth.has(r.id);
      const cls = b ? (t ? 'b' : 'h') : (t ? 'leak' : '');
      return `<i class="vd ${cls}" title="${F.esc(r.label)}"></i>`;
    }).join('');
    const cut = sideKey === 'without' && scopeCut.has(c.id);
    const leaks = recs.filter((r) => truth.has(r.id) && !blocked.has(r.id)).length;
    const tag = cut ? '<span class="cut-tag">cut off</span>'
      : leaks ? `<span class="leak-tag" title="${leaks} contaminated, not blocked">${icon('leak', 's16')}${leaks}</span>` : '';
    return `<div class="vs-co ${cut ? 'cut' : ''}"><div class="vc-h">${icon(COMPANY_ICON[c.id] || 'dot', 's16')}<b>${F.esc(F.ROLE_SHORT[c.id] || c.name)}</b>${tag}</div><div class="vc-dots">${dots}</div></div>`;
  }).join('');
  const leak = side.leaked > 0;
  return `
    <div class="vs-h"><div class="vs-ico">${icon(sideKey === 'without' ? 'leak' : 'verified')}</div>
      <div><div class="vs-t">${F.esc(side.title)}</div><div class="vs-s">${F.esc(side.subtitle)}</div></div></div>
    <div class="vs-stats">
      <div class="vs-stat surface q"><div class="v">${F.n(side.blocked)}</div><div class="l">operations blocked</div></div>
      <div class="vs-stat surface ${side.healthy_blocked ? 'q' : 'ok'}"><div class="v">${F.n(side.healthy_blocked)}</div><div class="l">healthy ones blocked for nothing</div></div>
      <div class="vs-stat surface ${leak ? 'alarm' : 'ok'}"><div class="v">${F.n(side.leaked)}</div><div class="l">${!leak ? 'no contaminated one gets through' : side.leaked > 1 ? 'contaminated ones still get through' : 'contaminated one still gets through'}</div></div>
      <div class="vs-stat surface ${side.activity_preserved_pct >= 99.95 ? 'ok' : ''}"><div class="v">${F.pctRaw(side.activity_preserved_pct)}</div><div class="l">healthy activity preserved</div></div>
    </div>
    <div class="vs-map">${cols}</div>`;
}

function meter(label, a, b, fmt, max, toneA = 'q', toneB = 'ok') {
  const w = (v) => (max ? Math.max(2, Math.round(((v || 0) / max) * 100)) : 0);
  return `<div class="vs-metric"><div class="m-l"><span>${label}</span></div>
    <div class="row"><span>Without</span><div class="gauge ${toneA}"><span style="width:${w(a)}%"></span></div><b>${fmt(a)}</b></div>
    <div class="row"><span>With</span><div class="gauge ${toneB}"><span style="width:${w(b)}%"></span></div><b>${fmt(b)}</b></div></div>`;
}

const dec1 = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export async function openVersus() {
  const box = $('#versus');
  box.innerHTML = `<div class="vs-top"><h2>With or without Firebreak</h2></div><div class="vs-cols"><div class="vs glass left"><div class="sk block"></div><div class="sk block"></div></div><div class="vs glass right"><div class="sk block"></div><div class="sk block"></div></div></div><div></div>`;
  if (!versusOpen()) versusFocus = document.activeElement;
  box.classList.add('on');
  syncInert();
  emit('versus', true);
  let cmp;
  try {
    cmp = await api('GET', '/api/compare');
  } catch (e) {
    closeVersus();
    fail(e, openVersus);
    return;
  }
  if (!versusOpen()) return;
  const truth = new Set(cmp.truth?.ids || []);
  const W = cmp.without, C = cmp.with;
  const g = cmp.bench?.groups || {};
  const b0 = g['p0.0:B'], c0 = g['p0.0:C'];
  const bench = b0 && c0
    ? `<div>${icon('chain', 's16')} <b>Benchmark, ${F.n(cmp.bench.seeds_per_group)} simulated worlds:</b> ${dec1.format(c0.healthy_blocked_mean)} healthy operations blocked on average with Firebreak, versus ${dec1.format(b0.healthy_blocked_mean)} without.</div>`
    : '';
  const real = (cmp.real_world || []).map((x) => `<a href="${F.esc(x.source)}" target="_blank" rel="noopener">${F.esc(x.name)} (${F.esc(x.date)})</a>`).join(' · ');
  box.innerHTML = `
    <div class="vs-top">${icon('compare')}<h2>With or without Firebreak</h2>
      <span class="lead">Same incident, same ground truth: ${F.n(cmp.truth.contaminated)} operations actually contaminated.</span>
      <button class="btn" id="vsClose">${icon('close', 's18')}<span>Close</span><span class="kbd">Esc</span></button></div>
    <div class="vs-cols">
      <section class="vs glass left" aria-label="${F.esc(W.title)}">${vsSide(W, cmp, 'without', truth)}</section>
      <section class="vs glass right" aria-label="${F.esc(C.title)}">${vsSide(C, cmp, 'with', truth)}</section>
    </div>
    <div class="vs-bottom glass">
      ${meter('Precision (blocked ones truly contaminated)', W.precision, C.precision, F.pct, 1)}
      ${meter('Recall (contaminated ones actually blocked)', W.recall, C.recall, F.pct, 1)}
      ${meter('Payments blocked', W.payments_blocked_eur, C.payments_blocked_eur, F.eur, Math.max(W.payments_blocked_eur, C.payments_blocked_eur), 'q', 'q')}
      <div class="vs-note">
        <div class="vs-legend" style="margin-bottom:8px">
          <span><i class="vd b"></i>contaminated, blocked</span>
          <span><i class="vd h"></i>healthy, blocked</span>
          <span><i class="vd leak"></i>contaminated, not blocked</span>
          <span><i class="vd"></i>flowing</span>
        </div>
        ${bench}
        ${real ? `<div style="margin-top:4px">Real-world total shutdowns: ${real}</div>` : ''}
      </div>
    </div>`;
  $('#vsClose').addEventListener('click', closeVersus);
  $('#vsClose').focus({ preventScroll: true });
}
