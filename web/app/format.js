// Display labels, record families and formatting. No made-up numbers:
// we only format what the API returns.

export const FAMILIES = [
  { id: 'order', label: 'Orders', icon: 'order' },
  { id: 'asn', label: 'Shipping notices', icon: 'asn' },
  { id: 'cert', label: 'Certificates', icon: 'cert' },
  { id: 'invoice', label: 'Invoices and bank details', icon: 'invoice' },
  { id: 'payment', label: 'Payments', icon: 'payment' },
  { id: 'lot', label: 'Lots and packaging', icon: 'lot' },
  { id: 'shipment', label: 'Shipments', icon: 'shipment' },
  { id: 'receipt', label: 'Receipts', icon: 'receipt' },
  { id: 'internal', label: 'Internal operations', icon: 'internal' },
];

const KIND_FAMILY = {
  purchase_order: 'order', sales_order: 'order', reservation: 'order', work_plan: 'order',
  asn: 'asn',
  quality_cert: 'cert', quality_release: 'cert',
  invoice: 'invoice', bank_details_change: 'invoice', vendor_master_update: 'invoice',
  payment: 'payment',
  production_lot: 'lot', packaging: 'lot', packing: 'lot',
  shipment: 'shipment',
  goods_receipt: 'receipt', stock_entry: 'receipt',
};

export const KIND_LABEL = {
  purchase_order: 'Purchase order',
  sales_order: 'Sales order',
  reservation: 'Reservation',
  work_plan: 'Site work plan',
  asn: 'Advance shipping notice',
  quality_cert: 'Quality certificate',
  quality_release: 'Quality release',
  invoice: 'Invoice',
  bank_details_change: 'Bank details change',
  vendor_master_update: 'Vendor master record',
  payment: 'Payment',
  production_lot: 'Production lot',
  packaging: 'Packaging',
  packing: 'Packing',
  shipment: 'Shipment',
  goods_receipt: 'Goods receipt',
  stock_entry: 'Stock entry',
  quality_check: 'Quality check',
  inventory_count: 'Inventory count',
  stock_adjustment: 'Stock adjustment',
  catalog_update: 'Catalogue update',
  internal_transfer: 'Internal transfer',
  maintenance: 'Maintenance',
  callback_verification: 'Callback verification',
  epcis_event: 'EPCIS event',
};

export function familyOf(kind) { return KIND_FAMILY[kind] || 'internal'; }
export function kindLabel(kind) { return KIND_LABEL[kind] || (kind ? kind.replaceAll('_', ' ') : 'Unknown type'); }
export function kindIcon(kind) { return FAMILIES.find((f) => f.id === familyOf(kind)).icon; }

export const ROLE_LABEL = {
  fournisseur: 'the supplier', fabricant: 'the manufacturer', distributeur: 'the distributor', client: 'the customer',
};
export const ROLE_SHORT = {
  fournisseur: 'Supplier', fabricant: 'Manufacturer', distributeur: 'Distributor', client: 'Customer',
};

export const STATUS = {
  ok: { label: 'Flowing', cls: 'ok' },
  quarantined: { label: 'Blocked', cls: 'q' },
  released: { label: 'Released', cls: 'r' },
};

export const RULE_LABEL = {
  source_compromise: 'compromised source',
  alerte_verifiee: 'verified alert',
  dependance: 'dependency',
  lot_suspect: 'suspect lot',
};

const nf = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
export function n(v) { return nf.format(Math.round(Number(v) || 0)); }
export function eur(v) { return `€${n(v)}`; }
export function pct(v) { return v == null ? '—' : `${n(v * 100)}%`; }
export function pctRaw(v) { return v == null ? '—' : `${n(v)}%`; }

// "2026-10-10T15:10:00" → "15:10"
export function hm(ts) { return ts ? String(ts).slice(11, 16) : ''; }
// "2026-10-10T14:00:00" → "14:00", "14:30" → "14:30"
export function hourFr(ts) {
  const [h, m] = hm(ts).split(':');
  if (!h) return '';
  return `${Number(h)}:${m || '00'}`;
}
export function dayFr(ts) {
  if (!ts) return '';
  const d = new Date(String(ts).slice(0, 10) + 'T12:00:00');
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
}

// Truncated opaque token: 7d4b…5efba
export function tok(t, a = 4, b = 5) {
  if (!t) return '';
  return t.length > a + b + 1 ? `${t.slice(0, a)}…${t.slice(-b)}` : t;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// API texts quote labels between « » or “ ”: we highlight them.
export function richText(s) {
  return esc(s)
    .replace(/«\s?([^»]+?)\s?»/g, '«&nbsp;<b>$1</b>&nbsp;»')
    .replace(/“([^”]+?)”/g, '“<b>$1</b>”');
}

export const STEP_META = {
  declaration: { icon: 'declaration', tone: 'q', label: 'Declaration' },
  seed: { icon: 'taint', tone: 'q', label: 'Contamination' },
  quarantine: { icon: 'quarantine', tone: 'q', label: 'Quarantine' },
  gate_blocked: { icon: 'gate', tone: 'q', label: 'Action blocked' },
  alert_sent: { icon: 'alert', tone: 'a', label: 'Alert sent' },
  alert_received: { icon: 'alert', tone: 'a', label: 'Alert received' },
  release: { icon: 'release', tone: 'ok', label: 'Released' },
  remediation: { icon: 'remediate', tone: 'r', label: 'Remediation' },
  withdrawal: { icon: 'falseAlarm', tone: 'ok', label: 'False alarm' },
  document_confirmed: { icon: 'file', tone: 'a', label: 'Document' },
  epcis_import: { icon: 'upload', tone: 'a', label: 'Import EPCIS' },
  lot_suspect: { icon: 'lot', tone: 'q', label: 'Suspect lot' },
  lot_suspect_withdrawn: { icon: 'release', tone: 'ok', label: 'Lot released' },
  report_sent: { icon: 'alert', tone: 'a', label: 'Report sent' },
  report_received: { icon: 'alert', tone: 'a', label: 'Report received' },
  report_decided: { icon: 'check', tone: 'a', label: 'Decision' },
};

export const AUDIT_EVENT = {
  declaration: 'Compromise declaration',
  declaration_withdrawn: 'Declaration withdrawn',
  alert_sent: 'Signed alert sent',
  alert_received: 'Signed alert received',
  quarantine: 'Quarantined',
  remediation: 'Remediation',
  release: 'Released from quarantine',
  document_confirmed: 'Document confirmed',
  epcis_import: 'Import EPCIS',
  lot_suspect: 'Lot declared suspect',
  lot_suspect_withdrawn: 'Suspect lot released',
  quality_report_sent: 'Quality report sent',
  quality_report_received: 'Quality report received',
  quality_report_decided: 'Quality report decided',
};

export const ACTION_ICON = { revalidate: 'verified', human_approval: 'human', trusted_source: 'source' };
