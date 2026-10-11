// Shared core: API access, UI state, DOM helpers, toasts.
import { icon } from './icons.js';
import { esc } from './format.js';

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
export const EASE = 'cubic-bezier(0.2, 0.8, 0.2, 1)';
export const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// The UI is served by the API (/app/): same origin. Use ?api=… for another one.
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
    throw Object.assign(new Error('Server unreachable: the FIREBREAK API is not responding.'), { status: 0 });
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* non-JSON body */ }
  if (!res.ok) {
    const detail = data && typeof data.detail === 'string' ? data.detail : `Error ${res.status}`;
    throw Object.assign(new Error(detail), { status: res.status });
  }
  return data;
}

// UI state. `status` is the DISPLAYED status (it follows the animation),
// `state` is the last full API response.
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
  reports: [],
};

export function companyName(id) { return S.companyName[id] || id; }

export function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

// Replaces the ICON:name markers in the static HTML with SVG icons.
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
    const b = el('button', 'btn', `${icon('reset', 's16')}<span>Retry</span>`);
    b.onclick = () => { box.remove(); retry(); };
    box.append(b);
  }
  const close = el('button', 'btn ghost icon', icon('close', 's16'));
  close.setAttribute('aria-label', 'Close');
  close.onclick = () => box.remove();
  box.append(close);
  $('#toasts').append(box);
  if (ttl) setTimeout(() => box.remove(), ttl);
}

export function fail(e, retry) {
  if (e && e.name === 'AbortError') return;
  console.error(e);
  toast(e?.message || 'Unexpected error.', { retry });
}

// ---------- Tooltip ----------
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

// Small event bus between modules (avoids circular imports).
const bus = new EventTarget();
export const on = (type, fn) => bus.addEventListener(type, (e) => fn(e.detail));
export const emit = (type, detail) => bus.dispatchEvent(new CustomEvent(type, { detail }));
