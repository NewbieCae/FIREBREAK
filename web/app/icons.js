// FIREBREAK icon set: 24 px grid, 1.5 px stroke, round caps, single stroke.
// All hand-drawn on the same grid (2–3 px margin, 1.5–2 radii).

const P = {
  // The 8 record families (+ internal operations)
  order: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V4"/><path d="M9 10h6M9 13.5h6M9 17h3.5"/>',
  asn: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M8.5 15h7M13 12.5l2.5 2.5-2.5 2.5"/>',
  cert: '<circle cx="12" cy="9.5" r="5.5"/><path d="M9.5 14.5 8 21l4-2.2 4 2.2-1.5-6.5"/><path d="m10 9.6 1.4 1.4 2.6-2.7"/>',
  invoice: '<path d="M6 3h12v18l-2.25-1.5L13.5 21l-1.5-1-1.5 1-2.25-1.5L6 21z"/><path d="M9 8h6M9 11.5h6M9 15h3.5"/>',
  payment: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3 10h18M7 14.5h3.5"/>',
  lot: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
  shipment: '<rect x="9" y="6.5" width="12" height="11" rx="1.5"/><path d="M13 6.5v4h4v-4"/><path d="M3 9.5h3.5M2 12.5h4.5M3 15.5h3.5"/>',
  receipt: '<path d="M4 13.5V18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4.5"/><path d="M4 13.5h4l1.5 2.5h5l1.5-2.5h4"/><path d="M12 3v8M8.75 7.75 12 11l3.25-3.25"/>',
  internal: '<path d="M5 4v3M5 11v9M12 4v9M12 17v3M19 4v1M19 9v11"/><circle cx="5" cy="9" r="2"/><circle cx="12" cy="15" r="2"/><circle cx="19" cy="7" r="2"/>',

  // The 4 companies: factory, workshop, truck, shop
  supplier: '<path d="M3 20V11l5 3v-3l5 3V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v15"/><path d="M2 20h20M7 17h2M12 17h2"/>',
  maker: '<circle cx="12" cy="12" r="3"/><path d="M12 2.75v2.5M12 18.75v2.5M2.75 12h2.5M18.75 12h2.5M5.46 5.46l1.77 1.77M16.77 16.77l1.77 1.77M5.46 18.54l1.77-1.77M16.77 7.23l1.77-1.77"/><circle cx="12" cy="12" r="6.25"/>',
  distributor: '<path d="M13 16V6H3.5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1H5M9 16h6M13 9h4.2l3.3 3.6V15a1 1 0 0 1-1 1H19"/><circle cx="7" cy="16.5" r="2"/><circle cx="17" cy="16.5" r="2"/>',
  customer: '<path d="M3.5 9 5 4h14l1.5 5"/><path d="M3.5 9a2.83 2.83 0 0 0 5.67 0 2.83 2.83 0 0 0 5.66 0 2.83 2.83 0 0 0 5.67 0"/><path d="M5 11.5V20h14v-8.5M10 20v-4.5h4V20"/>',

  // Semantics
  gate: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3M12 14.5V17"/>',
  gateOpen: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 7.75-1.4M12 14.5V17"/>',
  verified: '<path d="M12 3 19.5 6v5.5c0 4.5-3.2 8.2-7.5 9.5-4.3-1.3-7.5-5-7.5-9.5V6z"/><path d="m8.75 12.25 2.25 2.25 4.25-4.5"/>',
  alert: '<path d="M14.5 17H4a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 4 5h14a1.5 1.5 0 0 1 1.5 1.5V11"/><path d="m2.75 6 8.25 6 8.25-6"/><circle cx="18.5" cy="17" r="3.5"/><path d="m17.1 17 1 1 1.8-1.9"/>',
  alertBad: '<path d="M14.5 17H4a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 4 5h14a1.5 1.5 0 0 1 1.5 1.5V11"/><path d="m2.75 6 8.25 6 8.25-6"/><circle cx="18.5" cy="17" r="3.5"/><path d="m3 3 18 18"/>',
  taint: '<path d="M12 3.5c3 3.6 5.5 6.9 5.5 10a5.5 5.5 0 0 1-11 0c0-3.1 2.5-6.4 5.5-10z"/><path d="M9.5 14a2.5 2.5 0 0 0 2.5 2.5"/>',
  quarantine: '<circle cx="12" cy="12" r="8.5" stroke-dasharray="2.6 2.9"/><circle cx="12" cy="12" r="2.5"/>',
  release: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  falseAlarm: '<path d="M18 15.5V11a6 6 0 0 0-9.3-5M6 11v4.5L4.5 18H17"/><path d="M10 21h4M3.5 3.5l17 17"/>',
  audit: '<path d="M10 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1 1"/><path d="M14 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5l1-1"/>',
  compare: '<rect x="3" y="5" width="7.5" height="14" rx="1.5"/><rect x="13.5" y="5" width="7.5" height="14" rx="1.5"/>',
  declaration: '<circle cx="12" cy="12" r="2"/><path d="M8.1 8.1a5.5 5.5 0 0 0 0 7.8M15.9 8.1a5.5 5.5 0 0 1 0 7.8M5.3 5.3a9.5 9.5 0 0 0 0 13.4M18.7 5.3a9.5 9.5 0 0 1 0 13.4"/>',
  leak: '<path d="M10.3 4.7a2 2 0 0 1 3.4 0l7.3 12.6a2 2 0 0 1-1.7 3H4.7a2 2 0 0 1-1.7-3z"/><path d="M12 10v3.5M12 16.75v.01"/>',
  remediate: '<path d="M12 3 19.5 6v5.5c0 4.5-3.2 8.2-7.5 9.5-4.3-1.3-7.5-5-7.5-9.5V6z"/><path d="M14.5 10.5 12 8l-2.5 2.5M12 8v7"/>',
  human: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>',
  source: '<path d="M4 12a8 8 0 1 0 8-8"/><path d="M12 4 9 1.75M12 4 9 6.25"/><circle cx="12" cy="12" r="2.5"/>',

  // UI
  reset: '<path d="M4 12a8 8 0 1 0 2.35-5.65"/><path d="M4 4v4.5h4.5"/>',
  replay: '<path d="M4 12a8 8 0 1 0 2.35-5.65"/><path d="M4 4v4.5h4.5"/><path d="m10.25 9.25 4.5 2.75-4.5 2.75z"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  upload: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M12 18v-6M9.5 14.5 12 12l2.5 2.5"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.75"/>',
  spark: '<path d="M12 3.5 13.7 9 19 10.5 13.7 12 12 17.5 10.3 12 5 10.5 10.3 9z"/><path d="M18.5 16.5v4M16.5 18.5h4"/>',
  copy: '<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M15.5 8.5V5.5a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"/>',
  lockKey: '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15.5" r="1.25"/>',
  chain: '<path d="M7 7.5h10M7 16.5h10"/><rect x="3" y="4.5" width="18" height="15" rx="3"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 16.5h4"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6.5 8.5 6 8.5-6"/>',
  globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.5 3.5 5.5 3.5 8.5s-1 6-3.5 8.5c-2.5-2.5-3.5-5.5-3.5-8.5s1-6 3.5-8.5z"/>',
  dot: '<circle cx="12" cy="12" r="3"/>',
};

export function icon(name, cls = '') {
  const body = P[name] || P.dot;
  return `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
}

export const COMPANY_ICON = {
  fournisseur: 'supplier',
  fabricant: 'maker',
  distributeur: 'distributor',
  client: 'customer',
};

// Logo: a grid of dots (the forest, the operations) cut by a vertical bar
// (the firebreak). On the left, what burns; on the right, what is protected.
export function logo(cls = '') {
  const near = [4, 10].flatMap((x, i) => [5, 12, 19].map((y, j) =>
    `<circle class="l-dot near" cx="${x}" cy="${y}" r="2.2" style="animation-delay:${(i * 3 + j) * 0.07}s"/>`)).join('');
  const far = [5, 12, 19].map((y) => `<circle class="l-dot far" cx="23" cy="${y}" r="2.2"/>`).join('');
  return `<svg class="logo ${cls}" viewBox="0 0 27 24" aria-hidden="true">${near}<rect class="l-bar" x="15.4" y="1.5" width="2.2" height="21" rx="1.1"/>${far}</svg>`;
}
