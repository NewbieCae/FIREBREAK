// Panneaux : la preuve (détail d'une opération), le journal d'audit,
// l'import de documents, et l'écran « Avec ou sans Firebreak ».
import { S, $, api, el, emit, fail, toast, companyName, API } from './core.js';
import { icon, COMPANY_ICON } from './icons.js';
import * as F from './format.js';

// =====================================================================
// Tiroir latéral (un seul, contenu interchangeable)
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

// La scène derrière un tiroir ou l'écran « avec vs sans » n'est plus atteignable au clavier.
function syncInert() {
  $('#app').inert = drawerOpen() || versusOpen();
}

const closeBtn = `<button class="btn ghost icon" data-close aria-label="Fermer (Échap)" title="Fermer (Échap)">${icon('close', 's20')}</button>`;

function head({ ico, tone = '', title, sub }) {
  return `<header class="drawer-head">
    <div class="d-ico ${tone}">${icon(ico)}</div>
    <div style="min-width:0"><h2 class="d-title">${title}</h2><div class="d-sub">${sub || ''}</div></div>
    ${closeBtn}
  </header>`;
}

// =====================================================================
// 4.5 La preuve
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
  // Seed reçu d'un partenaire : la preuve commence par son alerte signée.
  if (first.token && first.origin && first.origin !== first.company) {
    const a = alertFrom(first.origin, first.company);
    const ok = !a || a.verified !== false;
    items.push(`<li class="alert">
      <div class="p-node">${icon(ok ? 'alert' : 'alertBad', 's18')}</div>
      <div><div class="p-label">Alerte signée reçue · ${F.esc(companyName(first.origin))}</div>
      <div class="p-meta"><span class="badge ${ok ? 'a' : 'q'}">${ok ? 'signature vérifiée' : 'signature rejetée'}</span>
      <span>jeton <span class="mono">${F.tok(first.token)}</span></span><span>ni libellé ni montant transmis</span></div></div></li>`);
  }
  recs.forEach((r, i) => {
    const s = S.status.get(r.id) || r.status;
    const tone = s === 'quarantined' ? '' : s === 'released' ? 'r' : 'ok';
    const origin = i === 0 ? '<span class="badge q">origine</span>' : '';
    const from = r.origin && r.origin !== r.company ? `<span>émis par ${F.esc(companyName(r.origin))}</span>` : '';
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
  if (r.payload?.amount != null) facts.push(`<div class="fact surface"><div class="f-k">Montant</div><div class="f-v big">${F.eur(r.payload.amount)}</div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">Type</div><div class="f-v">${F.kindLabel(r.kind)}</div></div>`);
  if (r.payload?.rib) facts.push(`<div class="fact surface wide"><div class="f-k">RIB ${r.payload.previous_rib ? '(nouveau)' : ''}</div><div class="f-v mono">${F.esc(r.payload.rib)}</div></div>`);
  if (r.payload?.lot) facts.push(`<div class="fact surface"><div class="f-k">Lot</div><div class="f-v mono">${F.esc(r.payload.lot)}</div></div>`);
  if (r.origin && r.origin !== r.company) facts.push(`<div class="fact surface"><div class="f-k">Émis par</div><div class="f-v">${F.esc(companyName(r.origin))}</div></div>`);
  if (r.token) facts.push(`<div class="fact surface wide"><div class="f-k">Jeton reçu (sha256, opaque)</div><div class="f-v mono">${F.tok(r.token, 10, 10)}<button class="copy" data-copy="${F.esc(r.token)}" title="Copier le jeton" aria-label="Copier le jeton">${icon('copy', 's16')}</button></div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">Identifiant</div><div class="f-v mono">${F.esc(r.id)}</div></div>`);

  const chips = [statusBadge(s)];
  if (r.gate) chips.push(`<span class="badge n">${icon('gate', 's16')}Action irréversible</span>`);
  if (r.verified) chips.push(`<span class="badge a">${icon('verified', 's16')}Vérifiée</span>`);

  let pathSec;
  if (path.length) {
    pathSec = `<section><h3 class="sec-title">${icon('taint', 's16')}Chemin de contamination<span class="aside">${path.length} opération${path.length > 1 ? 's' : ''} · registre ${F.esc(companyName(r.company))}</span></h3>${pathHtml(path, id)}</section>`;
  } else if (s === 'released') {
    pathSec = `<section><h3 class="sec-title">${icon('release', 's16')}Remédiée</h3><div class="surface explain">Débloquée par une action humaine. Elle ne sera plus contaminée et arrête la propagation : ses descendants reprennent.</div></section>`;
  } else {
    pathSec = `<section><h3 class="sec-title">${icon('verified', 's16')}Aucune dépendance suspecte</h3><div class="surface explain">${r.verified
      ? 'Confirmée par une source de confiance (contrôle physique, contre-appel). Elle n\'est jamais contaminée et <b>arrête la propagation</b>.'
      : 'Aucune de ses entrées ne dépend d\'une donnée suspecte : l\'opération continue normalement.'}</div></section>`;
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
        <h3 class="sec-title">${icon('spark', 's16')}Explication<span class="aside" id="pfAi"></span></h3>
        <div class="surface explain" id="pfExplain"><span class="sk line"></span><span class="sk line"></span><span class="sk line" style="width:70%"></span></div>
        <div class="explain-foot">${icon('verified', 's16')}<span>La décision vient du graphe. L'IA explique.</span></div>
      </section>
      ${s === 'quarantined' ? `<section><h3 class="sec-title">${icon('release', 's16')}Plan de reprise</h3><div class="plan" id="pfPlan"><div class="sk block"></div><div class="sk block"></div><div class="sk block"></div></div></section>` : ''}
      <section>
        <button class="btn ghost" data-audit="${F.esc(r.company)}">${icon('audit', 's16')}<span>Journal d'audit · ${F.esc(companyName(r.company))}</span></button>
      </section>
    </div>`, id);

  const d = $('#drawer');
  d.querySelectorAll('[data-goto]').forEach((b) => b.addEventListener('click', () => openProof(b.dataset.goto)));
  d.querySelector('[data-copy]')?.addEventListener('click', (e) => {
    navigator.clipboard?.writeText(e.currentTarget.dataset.copy).then(() => toast('Jeton copié.', { tone: 'info', ttl: 2000 }), () => {});
  });
  d.querySelector('[data-audit]')?.addEventListener('click', (e) => openAudit(e.currentTarget.dataset.audit));
  emit('highlight', id);

  try {
    const ex = await api('GET', `/api/records/${encodeURIComponent(id)}/explain`);
    if (token !== drawerToken) return;
    setAi(ex.source);
    $('#pfAi').innerHTML = `<span class="badge a">IA : ${ex.source === 'bedrock' ? 'Bedrock' : 'simulée'}</span>`;
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
    $('#pfExplain').textContent = "L'explication n'a pas pu être chargée.";
    fail(e, () => openProof(id));
  }
}

export function setAi(source) {
  if (!source) return;
  S.ai = source;
  $('#aiLabel').textContent = `IA : ${source === 'bedrock' ? 'Bedrock' : 'simulée'}`;
}

// =====================================================================
// Journal d'audit chaîné
// =====================================================================

function auditLine(e) {
  const d = e.details || {};
  const rec = d.record ? S.recs.get(d.record) : null;
  const icoMap = {
    declaration: 'declaration', declaration_withdrawn: 'falseAlarm', alert_sent: 'alert', alert_received: 'alert',
    quarantine: 'quarantine', remediation: 'remediate', release: 'release', document_confirmed: 'file', epcis_import: 'upload',
  };
  let detail = '';
  if (rec) detail = `« ${F.esc(rec.label)} »`;
  if (e.event === 'quarantine') detail += ` — règle : ${F.RULE_LABEL[d.rule] || d.rule}`;
  if (e.event === 'remediation') detail += ` — ${F.esc(d.action)}`;
  if (e.event.startsWith('alert')) {
    const n = (d.tokens || []).length;
    detail = `${d.type === 'release' ? 'Levée' : 'Contamination'} · ${F.esc(companyName(d.from))} → ${F.esc(companyName(d.to))} · ${n} jeton${n > 1 ? 's' : ''}`;
    if (e.event === 'alert_received') detail += ` · ${d.verified ? 'signature vérifiée' : 'signature rejetée'}`;
  }
  if (e.event === 'declaration' || e.event === 'declaration_withdrawn') detail = `Source : ${F.esc(companyName(d.source))}, depuis ${F.hourFr(d.effective_since || d.since)}`;
  if (e.event === 'epcis_import') detail = `${(d.records || []).length} opération(s) ajoutée(s)`;
  const bad = e.event === 'alert_received' && d.verified === false;
  return `<li>
    <div class="ci" style="${bad ? 'color:var(--q)' : ''}">${icon(icoMap[e.event] || 'dot', 's16')}</div>
    <div>
      <div class="ce">${F.AUDIT_EVENT[e.event] || F.esc(e.event)} <span class="badge n" style="height:20px;font-size:11px">${e.actor === 'humain' ? 'humain' : 'règle'}</span></div>
      ${detail ? `<div class="cd">${detail}</div>` : ''}
      <div class="ch mono"><span>#${e.index}</span><span>${F.hm(e.ts)}</span><span>${F.tok(e.prev_hash, 4, 4)}</span><span class="arrow">→</span><span>${F.tok(e.hash, 4, 4)}</span></div>
    </div></li>`;
}

export async function openAudit(company) {
  // En vue partenaire, on ne voit que son propre journal.
  const companies = S.state.companies.filter((c) => S.view === 'all' || c.id === S.view);
  if (S.view !== 'all') company = S.view;
  const tabs = companies.map((c) => `<button role="tab" data-co="${F.esc(c.id)}" aria-selected="${c.id === company}">${F.ROLE_SHORT[c.id] || F.esc(c.name)}</button>`).join('');
  const token = openDrawer('audit', `
    ${head({ ico: 'audit', title: "Journal d'audit", sub: '<span>Ajout seul, chaîné par hash (sha256) : une entrée modifiée casse la chaîne.</span>' })}
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
      ? `Chaîne locale intacte : ${F.n(j?.entries ?? log.entries.length)} entrée${(j?.entries ?? log.entries.length) > 1 ? 's vérifiées' : ' vérifiée'}`
      : `Chaîne cassée à l'entrée #${j?.first_broken_index}`}</span><span class="mono">${F.tok(log.head, 6, 6)}</span>`;
    const oc = j?.onchain;
    if (oc) {
      const box = el('div', `verify surface ${oc.matches ? 'ok' : 'bad'}`);
      const link = oc.explorer_link ? ` · <a href="${F.esc(oc.explorer_link)}" target="_blank" rel="noopener" style="color:var(--accent)">explorateur</a>` : '';
      box.innerHTML = `${icon(oc.matches ? 'chain' : 'leak', 's20')}<span>${oc.matches
        ? `Ancré sur Avalanche, bloc ${F.n(oc.block)} : le journal correspond (${F.n(oc.anchored_entries)} entrées)`
        : `Ne correspond plus à l'ancrage Avalanche du bloc ${F.n(oc.block)} : journal réécrit`}${link}</span><span class="mono">${F.tok(oc.anchored_head, 6, 6)}</span>`;
      if (oc.matches) box.querySelector('svg').style.color = 'var(--accent)';
      $('#auVerify').after(box);
      if (oc.matches && S.chain?.mode !== 'off' && log.entries.length) {
        const ev = log.entries.find((e) => e.event === 'alert_received') || log.entries[0];
        const b = el('button', 'btn ghost', `${icon('leak', 's16')}<span>Simuler une réécriture du journal (démo)</span>`);
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
      : `<li><div class="ci">${icon('audit', 's16')}</div><div class="cd" style="padding-top:6px">Journal vide : aucun événement depuis la réinitialisation.</div></li>`;
  } catch (e) {
    if (token === drawerToken) fail(e, () => openAudit(company));
  }
}

// =====================================================================
// Preuves sur Avalanche (optionnel : affiché seulement si la chaîne est active)
// =====================================================================

const ANCHOR_KIND = { audit: 'Tête de journal d\'audit', alert: 'Alerte signée', incident: 'Déclaration d\'incident', ack: 'Accusé de réception' };
const ANCHOR_ICON = { audit: 'audit', alert: 'alert', incident: 'declaration', ack: 'check' };
const ANCHOR_STATUS = {
  confirmed: ['a', 'confirmé'], sent: ['r', 'envoyé'], pending: ['r', 'en attente'], failed: ['q', 'échec'],
};

export async function openChain() {
  const token = openDrawer('chain', `
    ${head({ ico: 'chain', title: 'Preuves sur Avalanche', sub: '<span>Des empreintes, jamais de données métier. La chaîne ne décide rien : elle rend la preuve infalsifiable.</span>' })}
    <div class="drawer-body">
      <section class="facts" id="chFacts"><div class="sk block"></div><div class="sk block"></div></section>
      <section><h3 class="sec-title">${icon('chain', 's16')}Ancrages<span class="aside" id="chCount"></span></h3>
        <ol class="chainlist" id="chList"><li><div class="sk block" style="grid-column:span 2"></div></li></ol></section>
    </div>`);
  try {
    const [st, anchors] = await Promise.all([api('GET', '/api/chain/status'), api('GET', '/api/chain/anchors')]);
    if (token !== drawerToken) return;
    S.chain = st;
    const q = st.queue || {};
    $('#chFacts').innerHTML = `
      <div class="fact surface"><div class="f-k">Mode</div><div class="f-v">${st.mode === 'l1' ? 'Avalanche L1' : st.mode === 'tester' ? 'EVM en mémoire (test)' : 'désactivé'}</div></div>
      <div class="fact surface"><div class="f-k">Connexion</div><div class="f-v" style="color:${st.connected ? 'var(--accent)' : 'var(--q)'}">${st.connected ? 'connectée' : 'hors ligne'}</div></div>
      <div class="fact surface"><div class="f-k">Chain ID</div><div class="f-v mono">${F.esc(st.chain_id ?? '—')}</div></div>
      <div class="fact surface"><div class="f-k">Dernier bloc</div><div class="f-v mono">${F.esc(st.last_block ?? '—')}</div></div>
      <div class="fact surface wide"><div class="f-k">Contrat</div><div class="f-v mono">${F.esc(st.contract || '—')}</div></div>
      <div class="fact surface wide"><div class="f-k">File d'envoi</div><div class="f-v">${F.n(q.confirmed || 0)} confirmé(s) · ${F.n((q.pending || 0) + (q.sent || 0))} en cours · ${F.n(q.failed || 0)} échec(s)</div></div>`;
    $('#chCount').textContent = `${anchors.length} ancrage${anchors.length > 1 ? 's' : ''}`;
    $('#chList').innerHTML = anchors.length ? [...anchors].reverse().map((a) => {
      const [tone, label] = ANCHOR_STATUS[a.status] || ['n', a.status];
      const link = a.explorer_link ? `<a href="${F.esc(a.explorer_link)}" target="_blank" rel="noopener" style="color:var(--accent)">explorateur</a>` : '';
      return `<li><div class="ci">${icon(ANCHOR_ICON[a.kind] || 'chain', 's16')}</div><div>
        <div class="ce">${ANCHOR_KIND[a.kind] || F.esc(a.kind)} <span class="badge ${tone}" style="height:20px;font-size:11px" ${a.error ? `title="${F.esc(a.error)}"` : ''}>${label}</span></div>
        <div class="cd">${F.esc(companyName(a.company))}${a.block != null ? ` · bloc ${F.n(a.block)}` : ''} ${link}</div>
        <div class="ch mono"><span>${F.tok(a.hash, 6, 6)}</span>${a.tx_hash ? `<span class="arrow">tx</span><span>${F.tok(a.tx_hash, 6, 6)}</span>` : ''}</div></div></li>`;
    }).join('') : `<li><div class="ci">${icon('chain', 's16')}</div><div class="cd" style="padding-top:6px">Aucun ancrage pour l'instant : déclarez une compromission.</div></li>`;
  } catch (e) {
    if (token === drawerToken) fail(e, openChain);
  }
}

// =====================================================================
// 4.7 Import de documents (PDF, mail, texte, EPCIS)
// =====================================================================

const SAMPLES = [
  { file: 'facture-rib-modifie.pdf', type: 'application/pdf', title: 'Facture au RIB modifié', desc: 'PDF · F-9999', ico: 'invoice' },
  { file: 'avis-expedition.eml', type: 'message/rfc822', title: "Avis d'expédition", desc: 'Mail .eml · BC-1009', ico: 'mail' },
  { file: 'bon-de-commande.txt', type: 'text/plain', title: 'Bon de commande', desc: 'Texte · BC-7001', ico: 'order' },
  { file: 'epcis-sample.json', type: 'application/json', title: 'Événements EPCIS', desc: 'GS1 EPCIS 2.0 · 11 événements', ico: 'globe', epcis: true },
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
    ${head({ ico: 'upload', title: 'Importer un document', sub: "<span>L'IA lit, un humain confirme, puis le graphe décide.</span>" })}
    <div class="drawer-body">
      <div class="field">Registre qui reçoit le document<div class="seg" id="inCo">${seg}</div></div>
      <label class="drop" id="inDrop" tabindex="0">
        ${icon('upload')}
        <span class="dt">Glissez un document ici</span>
        <span class="dd">PDF, mail .eml, texte, ou JSON EPCIS 2.0 — 2 Mo max</span>
        <input type="file" id="inFile" hidden accept=".pdf,.eml,.txt,.json,.jsonld,application/pdf,message/rfc822,text/plain,application/json">
      </label>
      <section><h3 class="sec-title">${icon('file', 's16')}Exemples prêts</h3>
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
      if (!res.ok) throw new Error(`Exemple introuvable : ${s.file}`);
      const blob = await res.blob();
      readFile(blob, s.type, s.file);
    } catch (e) { fail(e); }
  }));
}

function resultSkeleton() {
  $('#inResult').innerHTML = `<section><h3 class="sec-title">${icon('spark', 's16')}Lecture du document</h3><div class="sk block"></div><div class="sk line"></div><div class="sk line" style="width:60%"></div></section>`;
}

async function readFile(blob, type, name = blob.name) {
  if (blob.size > 2 * 1024 * 1024) { toast('Document trop gros : 2 Mo maximum.'); return; }
  resultSkeleton();
  const co = ingestCompany;
  const token = drawerToken;
  try {
    if (type === 'application/json' && /epcis/i.test(name || '') || (type === 'application/json' && (await blob.slice(0, 600).text()).includes('EPCISDocument'))) {
      const before = new Set(S.recs.keys());
      const snapshot = { status: new Map([...S.status].filter(([id]) => before.has(id))), compromised: new Set(S.compromised) };
      const res = await api('POST', `/api/ingest/epcis?company=${encodeURIComponent(co)}`, blob, { raw: true, contentType: 'application/json' });
      // Les records sont déjà au registre côté serveur : on les montre quoi qu'il arrive au tiroir.
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
    `<div class="fact surface"><div class="f-k">Type reconnu</div><div class="f-v">${r.kind ? F.kindLabel(r.kind) : '<span style="color:var(--q)">non reconnu</span>'}</div></div>`,
    `<div class="fact surface"><div class="f-k">Émetteur</div><div class="f-v">${r.origin ? F.esc(companyName(r.origin)) : '<span style="color:var(--q)">non reconnu</span>'}</div></div>`,
  ];
  if (pl.amount != null) facts.push(`<div class="fact surface"><div class="f-k">Montant</div><div class="f-v big">${F.eur(pl.amount)}</div></div>`);
  facts.push(`<div class="fact surface"><div class="f-k">Reçu le</div><div class="f-v mono">${F.dayFr(r.ts)} · ${F.hm(r.ts)}</div></div>`);
  if (pl.rib) facts.push(`<div class="fact surface wide"><div class="f-k">RIB</div><div class="f-v mono">${F.esc(pl.rib)}</div></div>`);
  if (pl.previous_rib) facts.push(`<div class="fact surface wide"><div class="f-k">RIB précédent</div><div class="f-v mono">${F.esc(pl.previous_rib)}</div></div>`);
  if (pl.references?.length) facts.push(`<div class="fact surface wide"><div class="f-k">Références</div><div class="f-v mono">${pl.references.map(F.esc).join(' · ')}</div></div>`);
  const warn = pl.bank_details_change
    ? `<div class="warnline surface">${icon('leak', 's20')}<span><b>Coordonnées bancaires nouvelles.</b> ${pl.rib_unknown_for_origin ? "Ce RIB n'a jamais été vu pour cet émetteur dans le registre." : 'Le document annonce un changement de RIB.'}</span></div>`
    : '';
  const missing = p.missing?.length ? `<div class="cd" style="font-size:12.5px;color:var(--text-2)">Champs attendus absents : ${p.missing.map(F.esc).join(', ')}</div>` : '';
  const conf = Math.round((p.confidence || 0) * 100);
  const canConfirm = r.kind && r.origin;
  $('#inResult').innerHTML = `<section>
    <h3 class="sec-title">${icon('spark', 's16')}Proposition de l'IA<span class="aside"><span class="badge a">IA : ${p.source === 'bedrock' ? 'Bedrock' : 'simulée'}</span></span></h3>
    <div class="surface explain" style="margin-bottom:10px"><div style="display:flex;gap:10px;align-items:center">${icon(F.kindIcon(r.kind))}<b>${F.esc(r.label || name || 'Document')}</b></div>
      <div style="display:flex;align-items:center;gap:10px;margin-top:10px;font-size:12.5px;color:var(--text-2)"><span>Confiance</span><div class="gauge" style="flex:1"><span style="width:${conf}%"></span></div><span class="mono">${conf}&nbsp;%</span></div>
    </div>
    <div class="facts">${facts.join('')}</div>
    ${warn ? `<div style="margin-top:10px">${warn}</div>` : ''}
    ${missing}
    <div style="display:flex;gap:8px;margin-top:14px">
      <button class="btn primary" id="inConfirm" ${canConfirm ? '' : 'disabled'}>${icon('check', 's18')}<span>Confirmer et inscrire au registre</span></button>
      <button class="btn ghost" id="inCancel">Annuler</button>
    </div>
    <div class="explain-foot">${icon('verified', 's16')}<span>Rien n'entre au registre sans confirmation humaine. Ensuite, les règles du graphe s'appliquent.</span></div>
  </section>`;
  $('#inCancel').addEventListener('click', () => { $('#inResult').innerHTML = ''; });
  $('#inConfirm').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const snapshot = emitSnapshot();
      const st = await api('POST', `/api/ingest/document/${encodeURIComponent(p.id)}/confirm`);
      closeDrawer();
      emit('ingested', { state: st, snapshot, title: 'Document confirmé' });
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
      <div class="fact surface"><div class="f-k">Événements lus</div><div class="f-v big">${F.n(res.events)}</div></div>
      <div class="fact surface"><div class="f-k">Opérations ajoutées</div><div class="f-v big">${F.n(added)}</div></div>
      <div class="fact surface wide"><div class="f-k">Registre</div><div class="f-v">${F.esc(companyName(co))}${res.ignored?.length ? ` · ${res.ignored.length} ignoré(s)` : ''}</div></div>
    </div>
    <div class="explain-foot">${icon('verified', 's16')}<span>Données structurées GS1 : ajoutées tout de suite, puis soumises aux mêmes règles que les autres.</span></div>
  </section>`;
  const token = drawerToken;
  setTimeout(() => { if (token === drawerToken) closeDrawer(); }, 1600);
}

// =====================================================================
// 4.4 Avec ou sans Firebreak
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
    const tag = cut ? '<span class="cut-tag">coupé</span>'
      : leaks ? `<span class="leak-tag" title="${leaks} contaminée(s) non bloquée(s)">${icon('leak', 's16')}${leaks}</span>` : '';
    return `<div class="vs-co ${cut ? 'cut' : ''}"><div class="vc-h">${icon(COMPANY_ICON[c.id] || 'dot', 's16')}<b>${F.esc(F.ROLE_SHORT[c.id] || c.name)}</b>${tag}</div><div class="vc-dots">${dots}</div></div>`;
  }).join('');
  const leak = side.leaked > 0;
  return `
    <div class="vs-h"><div class="vs-ico">${icon(sideKey === 'without' ? 'leak' : 'verified')}</div>
      <div><div class="vs-t">${F.esc(side.title)}</div><div class="vs-s">${F.esc(side.subtitle)}</div></div></div>
    <div class="vs-stats">
      <div class="vs-stat surface q"><div class="v">${F.n(side.blocked)}</div><div class="l">opérations bloquées</div></div>
      <div class="vs-stat surface ${side.healthy_blocked ? 'q' : 'ok'}"><div class="v">${F.n(side.healthy_blocked)}</div><div class="l">saines bloquées pour rien</div></div>
      <div class="vs-stat surface ${leak ? 'alarm' : 'ok'}"><div class="v">${F.n(side.leaked)}</div><div class="l">${!leak ? 'aucune contaminée ne passe' : side.leaked > 1 ? 'contaminées passent quand même' : 'contaminée passe quand même'}</div></div>
      <div class="vs-stat surface ${side.activity_preserved_pct >= 99.95 ? 'ok' : ''}"><div class="v">${F.pctRaw(side.activity_preserved_pct)}</div><div class="l">activité saine préservée</div></div>
    </div>
    <div class="vs-map">${cols}</div>`;
}

function meter(label, a, b, fmt, max, toneA = 'q', toneB = 'ok') {
  const w = (v) => (max ? Math.max(2, Math.round(((v || 0) / max) * 100)) : 0);
  return `<div class="vs-metric"><div class="m-l"><span>${label}</span></div>
    <div class="row"><span>Sans</span><div class="gauge ${toneA}"><span style="width:${w(a)}%"></span></div><b>${fmt(a)}</b></div>
    <div class="row"><span>Avec</span><div class="gauge ${toneB}"><span style="width:${w(b)}%"></span></div><b>${fmt(b)}</b></div></div>`;
}

const dec1 = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export async function openVersus() {
  const box = $('#versus');
  box.innerHTML = `<div class="vs-top"><h2>Avec ou sans Firebreak</h2></div><div class="vs-cols"><div class="vs glass left"><div class="sk block"></div><div class="sk block"></div></div><div class="vs glass right"><div class="sk block"></div><div class="sk block"></div></div></div><div></div>`;
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
    ? `<div>${icon('chain', 's16')} <b>Banc d'essai, ${F.n(cmp.bench.seeds_per_group)} mondes simulés :</b> ${dec1.format(c0.healthy_blocked_mean)} opérations saines bloquées en moyenne avec Firebreak, contre ${dec1.format(b0.healthy_blocked_mean)} sans.</div>`
    : '';
  const real = (cmp.real_world || []).map((x) => `<a href="${F.esc(x.source)}" target="_blank" rel="noopener">${F.esc(x.name)} (${F.esc(x.date)})</a>`).join(' · ');
  box.innerHTML = `
    <div class="vs-top">${icon('compare')}<h2>Avec ou sans Firebreak</h2>
      <span class="lead">Même incident, même vérité terrain : ${F.n(cmp.truth.contaminated)} opérations réellement contaminées.</span>
      <button class="btn" id="vsClose">${icon('close', 's18')}<span>Fermer</span><span class="kbd">Échap</span></button></div>
    <div class="vs-cols">
      <section class="vs glass left" aria-label="${F.esc(W.title)}">${vsSide(W, cmp, 'without', truth)}</section>
      <section class="vs glass right" aria-label="${F.esc(C.title)}">${vsSide(C, cmp, 'with', truth)}</section>
    </div>
    <div class="vs-bottom glass">
      ${meter('Précision (bloquées vraiment contaminées)', W.precision, C.precision, F.pct, 1)}
      ${meter('Rappel (contaminées bien bloquées)', W.recall, C.recall, F.pct, 1)}
      ${meter('Paiements bloqués', W.payments_blocked_eur, C.payments_blocked_eur, F.eur, Math.max(W.payments_blocked_eur, C.payments_blocked_eur), 'q', 'q')}
      <div class="vs-note">
        <div class="vs-legend" style="margin-bottom:8px">
          <span><i class="vd b"></i>contaminée bloquée</span>
          <span><i class="vd h"></i>saine bloquée</span>
          <span><i class="vd leak"></i>contaminée non bloquée</span>
          <span><i class="vd"></i>continue</span>
        </div>
        ${bench}
        ${real ? `<div style="margin-top:4px">Coupures totales réelles : ${real}</div>` : ''}
      </div>
    </div>`;
  $('#vsClose').addEventListener('click', closeVersus);
  $('#vsClose').focus({ preventScroll: true });
}
