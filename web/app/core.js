// Noyau partagé : accès à l'API, état de l'interface, utilitaires DOM, toasts.
import { icon } from './icons.js';
import { esc } from './format.js';

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
export const EASE = 'cubic-bezier(0.2, 0.8, 0.2, 1)';
export const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// L'interface est servie par l'API (/app/) : même origine. ?api=… pour une autre.
const qs = new URLSearchParams(location.search);
export const API = qs.get('api') ?? (location.protocol === 'file:' ? 'http://localhost:8000' : '');

export async function api(method, path, body, opts = {}) {
  const init = { method, headers: {}, signal: opts.signal };
  if (body !== undefined) {
    if (opts.raw) {
      init.body = body;
      init.headers['Content-Type'] = opts.contentType || 'application/octet-stream';
    } else {
      init.body = JSON.stringify(body);
      init.headers['Content-Type'] = 'application/json';
    }
  }
  let res;
  try {
    res = await fetch(API + path, init);
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw Object.assign(new Error("Serveur injoignable : l'API FIREBREAK ne répond pas."), { status: 0 });
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* corps non JSON */ }
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : `Erreur ${res.status}`;
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return data;
}

// État de l'interface. `status` est le statut AFFICHÉ (il suit l'animation),
// `state` la dernière réponse complète de l'API.
export const S = {
  state: null,
  recs: new Map(),
  status: new Map(),
  compromised: new Set(),
  scenarios: [],
  view: 'all',
  playing: false,
  abort: null,
  snapshot: null,
  lastAction: null,
  ai: null,
  companyName: {},
};

export function companyName(id) { return S.companyName[id] || id; }

export function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

// Remplace les marqueurs ICON:nom du HTML statique par les icônes SVG.
export function hydrateIcons(root = document.body) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const hits = [];
  while (walker.nextNode()) if (walker.currentNode.nodeValue.includes('ICON:')) hits.push(walker.currentNode);
  for (const node of hits) {
    const span = document.createElement('span');
    span.innerHTML = node.nodeValue.replace(/ICON:(\w+)/g, (_, n) => icon(n, 's18'));
    node.replaceWith(...span.childNodes);
  }
}

// ---------- Toasts ----------
export function toast(message, { retry, tone = 'err', ttl = 7000 } = {}) {
  const box = el('div', `toast glass ${tone}`);
  box.setAttribute('role', tone === 'err' ? 'alert' : 'status');
  box.innerHTML = `${icon(tone === 'err' ? 'leak' : 'spark', 's20')}<span>${esc(message)}</span>`;
  if (retry) {
    const b = el('button', 'btn', `${icon('reset', 's16')}<span>Réessayer</span>`);
    b.onclick = () => { box.remove(); retry(); };
    box.append(b);
  }
  const close = el('button', 'btn ghost icon', icon('close', 's16'));
  close.setAttribute('aria-label', 'Fermer');
  close.onclick = () => box.remove();
  box.append(close);
  $('#toasts').append(box);
  if (ttl) setTimeout(() => box.remove(), ttl);
}

export function fail(e, retry) {
  if (e && e.name === 'AbortError') return;
  console.error(e);
  toast(e?.message || 'Erreur inattendue.', { retry });
}

// ---------- Infobulle ----------
const tipEl = () => $('#tip');
export function showTip(html, x, y) {
  const t = tipEl();
  t.innerHTML = html;
  t.classList.add('on');
  const w = t.offsetWidth, h = t.offsetHeight;
  let left = x + 14, top = y - h - 12;
  if (left + w > innerWidth - 8) left = x - w - 14;
  if (top < 8) top = y + 16;
  t.style.left = `${left}px`;
  t.style.top = `${top}px`;
}
export function hideTip() { tipEl().classList.remove('on'); }

// Petit bus d'événements entre modules (évite les imports circulaires).
const bus = new EventTarget();
export const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));
export const emit = (type, detail) => bus.dispatchEvent(new CustomEvent(type, { detail }));
