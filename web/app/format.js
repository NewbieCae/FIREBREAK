// Libellés français, familles de records et formatage. Aucun chiffre inventé :
// on ne fait que mettre en forme ce que renvoie l'API.

export const FAMILIES = [
  { id: 'order', label: 'Commandes', icon: 'order' },
  { id: 'asn', label: "Avis d'expédition", icon: 'asn' },
  { id: 'cert', label: 'Certificats', icon: 'cert' },
  { id: 'invoice', label: 'Factures et RIB', icon: 'invoice' },
  { id: 'payment', label: 'Paiements', icon: 'payment' },
  { id: 'lot', label: 'Lots et conditionnement', icon: 'lot' },
  { id: 'shipment', label: 'Expéditions', icon: 'shipment' },
  { id: 'receipt', label: 'Réceptions', icon: 'receipt' },
  { id: 'internal', label: 'Opérations internes', icon: 'internal' },
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
  purchase_order: "Bon de commande",
  sales_order: 'Commande client',
  reservation: 'Réservation',
  work_plan: 'Planning de chantier',
  asn: "Avis d'expédition",
  quality_cert: 'Certificat qualité',
  quality_release: 'Libération qualité',
  invoice: 'Facture',
  bank_details_change: 'Changement de RIB',
  vendor_master_update: 'Fiche fournisseur',
  payment: 'Paiement',
  production_lot: 'Lot de production',
  packaging: 'Conditionnement',
  packing: 'Emballage',
  shipment: 'Expédition',
  goods_receipt: 'Réception',
  stock_entry: 'Entrée en stock',
  quality_check: 'Contrôle qualité',
  inventory_count: 'Inventaire',
  stock_adjustment: 'Ajustement de stock',
  catalog_update: 'Mise à jour du catalogue',
  internal_transfer: 'Transfert interne',
  maintenance: 'Maintenance',
  callback_verification: 'Contre-appel de vérification',
  epcis_event: 'Événement EPCIS',
};

export function familyOf(kind) { return KIND_FAMILY[kind] || 'internal'; }
export function kindLabel(kind) { return KIND_LABEL[kind] || (kind ? kind.replaceAll('_', ' ') : 'Type inconnu'); }
export function kindIcon(kind) { return FAMILIES.find((f) => f.id === familyOf(kind)).icon; }

export const ROLE_LABEL = {
  fournisseur: 'le fournisseur', fabricant: 'le fabricant', distributeur: 'le distributeur', client: 'le client',
};
export const ROLE_SHORT = {
  fournisseur: 'Fournisseur', fabricant: 'Fabricant', distributeur: 'Distributeur', client: 'Client',
};

export const STATUS = {
  ok: { label: 'Continue', cls: 'ok' },
  quarantined: { label: 'Bloquée', cls: 'q' },
  released: { label: 'Libérée', cls: 'r' },
};

export const RULE_LABEL = {
  source_compromise: 'source compromise',
  alerte_verifiee: 'alerte vérifiée',
  dependance: 'dépendance',
  lot_suspect: 'lot suspect',
};

const nf = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
export function n(v) { return nf.format(Math.round(Number(v) || 0)); }
export function eur(v) { return `${n(v)} €`; }
export function pct(v) { return v == null ? '—' : `${n(v * 100)} %`; }
export function pctRaw(v) { return v == null ? '—' : `${n(v)} %`; }

// "2026-10-10T15:10:00" → "15:10"
export function hm(ts) { return ts ? String(ts).slice(11, 16) : ''; }
// "2026-10-10T14:00:00" → "14 h", "14:30" → "14 h 30"
export function hourFr(ts) {
  const [h, m] = hm(ts).split(':');
  if (!h) return '';
  return m && m !== '00' ? `${Number(h)} h ${m}` : `${Number(h)} h`;
}
export function dayFr(ts) {
  if (!ts) return '';
  const d = new Date(String(ts).slice(0, 10) + 'T12:00:00');
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
}

// Jeton opaque tronqué : 7d4b…5efba
export function tok(t, a = 4, b = 5) {
  if (!t) return '';
  return t.length > a + b + 1 ? `${t.slice(0, a)}…${t.slice(-b)}` : t;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Les textes de l'API citent les libellés entre « » : on les met en valeur.
export function richText(s) {
  return esc(s).replace(/«\s?([^»]+?)\s?»/g, '«&nbsp;<b>$1</b>&nbsp;»');
}

export const STEP_META = {
  declaration: { icon: 'declaration', tone: 'q', label: 'Déclaration' },
  seed: { icon: 'taint', tone: 'q', label: 'Contamination' },
  quarantine: { icon: 'quarantine', tone: 'q', label: 'Quarantaine' },
  gate_blocked: { icon: 'gate', tone: 'q', label: 'Action bloquée' },
  alert_sent: { icon: 'alert', tone: 'a', label: 'Alerte émise' },
  alert_received: { icon: 'alert', tone: 'a', label: 'Alerte reçue' },
  release: { icon: 'release', tone: 'ok', label: 'Levée' },
  remediation: { icon: 'remediate', tone: 'r', label: 'Remédiation' },
  withdrawal: { icon: 'falseAlarm', tone: 'ok', label: 'Fausse alerte' },
  document_confirmed: { icon: 'file', tone: 'a', label: 'Document' },
  epcis_import: { icon: 'upload', tone: 'a', label: 'Import EPCIS' },
  lot_suspect: { icon: 'lot', tone: 'q', label: 'Lot suspect' },
  lot_suspect_withdrawn: { icon: 'release', tone: 'ok', label: 'Lot levé' },
  report_sent: { icon: 'alert', tone: 'a', label: 'Signalement émis' },
  report_received: { icon: 'alert', tone: 'a', label: 'Signalement reçu' },
  report_decided: { icon: 'check', tone: 'a', label: 'Décision' },
};

export const AUDIT_EVENT = {
  declaration: 'Déclaration de compromission',
  declaration_withdrawn: 'Déclaration retirée',
  alert_sent: 'Alerte signée émise',
  alert_received: 'Alerte signée reçue',
  quarantine: 'Mise en quarantaine',
  remediation: 'Remédiation',
  release: 'Sortie de quarantaine',
  document_confirmed: 'Document confirmé',
  epcis_import: 'Import EPCIS',
  lot_suspect: 'Lot déclaré suspect',
  lot_suspect_withdrawn: 'Lot suspect levé',
  quality_report_sent: 'Signalement qualité émis',
  quality_report_received: 'Signalement qualité reçu',
  quality_report_decided: 'Signalement qualité décidé',
};

export const ACTION_ICON = { revalidate: 'verified', human_approval: 'human', trusted_source: 'source' };
