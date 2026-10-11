"""Inbound inspection: trust score of a received lot.

When a delivery is received, what the company already knows (master data:
supplier records, parts and bills of materials, open purchase orders) is
cross-checked against what arrives (shipping notice, certificate, received
invoices, active alerts). Each check is deterministic, weighted and explained;
the score starts at 100 and each failed check subtracts its penalty.

Rules propose, a human decides: below the threshold, the receipt is put on
hold (if the lot was already physically checked, only when it is suspect)
(the receipt and everything that depends on it), and a human accepts or
rejects it. The English explanation is generated from the checks; an AI
may rephrase it, never change the score or the decision.

Receipt data is read from the payloads (`bc`, `part`, `qty`, `lot` of the
receipt, `lot_no` of shipping notices and certificates — `lot` is reserved
there for the genealogy's lot carriers —, `cert_no`, `grade`, `rib`) and,
failing that, from the labels ("BC-1008", "CQ-2003"), so it works on
incomplete data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import Ledger
    from .model import Record

TRUST_THRESHOLD = 80   # below: on hold + human decision
SUSPECT_THRESHOLD = 60  # below: "suspect" band
RECEIPT_KINDS = {"goods_receipt"}

_BC_RE = re.compile(r"\bBC-[A-Z0-9]+\b")
_CERT_RE = re.compile(r"\bCQ-\d+\b")


@dataclass(frozen=True)
class SupplierProfile:
    id: str
    name: str
    rib: str
    cert_pattern: str  # regex of the expected certificate numbers
    lot_pattern: str   # regex of the expected lot numbers
    lead_tolerance: timedelta = timedelta(hours=4)


@dataclass(frozen=True)
class PurchaseOrder:
    bc: str
    supplier: str
    part: str
    qty: float
    grade: str
    due: datetime
    status: str = "open"  # open | closed


@dataclass
class Referentiel:
    """A company's master data (its ERP, simplified)."""

    suppliers: dict[str, SupplierProfile] = field(default_factory=dict)
    parts: dict[str, list[str]] = field(default_factory=dict)  # part number -> products that use it (bill of materials)
    orders: dict[str, PurchaseOrder] = field(default_factory=dict)


def default_referentiels() -> dict[str, Referentiel]:
    """The manufacturer's master data for the 2026-10-10 demo day:
    purchase orders BC-1001 to BC-1008 (morning coils and the 14:45 delivery),
    BC-1009 (invoice of the rib scenario) and BC-1010 (coil COIL-210 expected
    in the afternoon), all with Aciers Durand. A missing order (e.g. BC-9999)
    is an unknown purchase order."""
    from .scenario import RIB_OK  # local import: scenario imports simulation

    day = datetime(2026, 10, 10)
    supplier = SupplierProfile(
        id="fournisseur", name="Aciers Durand", rib=RIB_OK,
        cert_pattern=r"^CQ-2\d{3}$", lot_pattern=r"^COIL-\d{3}$",
    )
    part = "BOBINE-S235-2MM"
    orders = {}
    for i in range(1, 8):  # morning deliveries, ASNs between 08:40 and 11:40
        due = day.replace(hour=8, minute=30) + timedelta(minutes=30 * (i - 1) + 40)
        orders[f"BC-{1000 + i}"] = PurchaseOrder(f"BC-{1000 + i}", "fournisseur", part, 12, "S235", due)
    orders["BC-1008"] = PurchaseOrder("BC-1008", "fournisseur", part, 12, "S235", day.replace(hour=15))
    orders["BC-1009"] = PurchaseOrder("BC-1009", "fournisseur", part, 12, "S235", day.replace(hour=16))
    orders["BC-1010"] = PurchaseOrder("BC-1010", "fournisseur", part, 12, "S235", day.replace(hour=14, minute=40))
    fabricant = Referentiel(
        suppliers={"fournisseur": supplier},
        parts={part: ["SUPPORT-CHANTIER", "ASM-950"]},
        orders=orders,
    )
    return {"fabricant": fabricant}


@dataclass
class Check:
    id: str
    label: str
    ok: bool
    penalty: int
    detail: str

    def as_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "ok": self.ok,
                "penalty": self.penalty if not self.ok else 0, "detail": self.detail}


def _first(records: list[Record], kind: str) -> Record | None:
    return next((r for r in records if r.kind == kind), None)


def _from_label(record: Record | None, regex: re.Pattern) -> str | None:
    if record is None:
        return None
    m = regex.search(record.label)
    return m.group(0) if m else None


def _value(key: str, *records: Record | None):
    for r in records:
        if r is not None and r.payload.get(key) not in (None, ""):
            return r.payload[key]
    return None


# Display labels for the band codes (the codes themselves are part of the API contract).
BAND_LABELS = {"confiance": "trusted", "doute": "doubtful", "suspect": "suspect"}


def band_of(score: int) -> str:
    if score >= TRUST_THRESHOLD:
        return "confiance"
    if score >= SUSPECT_THRESHOLD:
        return "doute"
    return "suspect"


def evaluate_receipt(ledger: Ledger, receipt_id: str, ref: Referentiel | None) -> dict:
    """Trust score of a receipt. Read-only, deterministic."""
    receipt = ledger.records[receipt_id]
    if receipt.kind not in RECEIPT_KINDS:
        raise ValueError(f"{receipt_id} is not a goods receipt")
    inputs = [ledger.records[i] for i in receipt.inputs if i in ledger.records]
    asn = _first(inputs, "asn")
    cert = _first(inputs, "quality_cert")
    supplier_id = next((r.origin for r in (asn, cert) if r is not None and r.origin != ledger.company_id),
                       receipt.origin)
    ref = ref or Referentiel()
    profile = ref.suppliers.get(supplier_id)

    bc = _value("bc", receipt, asn) or _from_label(asn, _BC_RE) or _from_label(receipt, _BC_RE)
    lot = _value("lot", receipt) or _value("lot_no", asn) or _value("lot", asn)
    if cert is None and lot is not None:
        # Certificate not linked to the receipt: look for the one the
        # same supplier sent for this lot.
        cert = next((r for r in ledger.records.values()
                     if r.kind == "quality_cert" and r.origin == supplier_id
                     and lot in (r.payload.get("lot_no"), r.payload.get("lot"))), None)
    part = _value("part", receipt, asn, cert)
    qty = _value("qty", receipt, asn)
    cert_no = _value("cert_no", cert) or _from_label(cert, _CERT_RE)
    cert_lot = _value("lot_no", cert) or _value("lot", cert)
    grade = _value("grade", cert)
    po = ref.orders.get(bc) if bc else None

    checks: list[Check] = []

    # 1. Purchase order
    if not ref.orders:
        checks.append(Check("order", "Purchase order", True, 0, "purchase order master data unavailable"))
    elif bc is None:
        checks.append(Check("order", "Purchase order", False, 30, "no purchase order number on the shipping notice"))
    elif po is None:
        checks.append(Check("order", "Purchase order", False, 40, f"purchase order {bc} unknown to the ERP"))
    elif po.supplier != supplier_id:
        checks.append(Check("order", "Purchase order", False, 30,
                            f"purchase order {bc} placed with {po.supplier}, delivered by {supplier_id}"))
    elif po.status != "open":
        checks.append(Check("order", "Purchase order", False, 20, f"purchase order {bc} already closed"))
    else:
        checks.append(Check("order", "Purchase order", True, 0, f"purchase order {bc} open with this supplier"))

    # 2. Part and bill of materials
    if part is None:
        checks.append(Check("part", "Part number and bill of materials", True, 0, "part number not provided"))
    elif po is not None and part != po.part:
        checks.append(Check("part", "Part number and bill of materials", False, 25,
                            f"part {part} delivered, {po.part} ordered"))
    elif ref.parts and part not in ref.parts:
        checks.append(Check("part", "Part number and bill of materials", False, 10,
                            f"part {part} missing from the bills of materials"))
    else:
        checks.append(Check("part", "Part number and bill of materials", True, 0, f"{part} listed in the bill of materials"))

    # 3. Quantity
    if qty is None or po is None:
        checks.append(Check("qty", "Quantity", True, 0, "quantity not comparable"))
    elif float(qty) > po.qty * 1.10:
        checks.append(Check("qty", "Quantity", False, 15, f"{qty} delivered for {po.qty:g} ordered"))
    else:
        checks.append(Check("qty", "Quantity", True, 0, f"{qty} for {po.qty:g} ordered"))

    # 4. Lead time
    if po is None:
        checks.append(Check("date", "Delivery date", True, 0, "no expected date"))
    else:
        tol = profile.lead_tolerance if profile else timedelta(hours=4)
        gap = receipt.ts - po.due
        if abs(gap) > tol:
            sens = "early" if gap < timedelta(0) else "late"
            checks.append(Check("date", "Delivery date", False, 10,
                                f"{abs(gap) // timedelta(minutes=1)} min {sens} against the planned date"))
        else:
            checks.append(Check("date", "Delivery date", True, 0, "within the planned window"))

    # 5. Certificate present and consistent
    if cert is None:
        checks.append(Check("cert", "Material certificate", False, 20, "no certificate received for this lot"))
    else:
        problems, penalty = [], 0
        if cert_lot and lot and cert_lot != lot:
            problems.append(f"certificate for {cert_lot}, lot received {lot}")
            penalty += 20
        if grade and po is not None and grade != po.grade:
            problems.append(f"grade {grade} certified, {po.grade} ordered")
            penalty += 30  # non-conforming material: serious deviation
        if problems:
            checks.append(Check("cert", "Material certificate", False, min(penalty, 40),
                                "; ".join(problems)))
        else:
            checks.append(Check("cert", "Material certificate", True, 0, "certificate received and consistent"))

    # 6. Certificate number
    if cert_no is None or profile is None:
        checks.append(Check("cert_no", "Certificate number", True, 0, "not verifiable"))
    elif not re.match(profile.cert_pattern, cert_no):
        checks.append(Check("cert_no", "Certificate number", False, 15,
                            f"{cert_no} outside the supplier's usual sequence"))
    else:
        checks.append(Check("cert_no", "Certificate number", True, 0, f"{cert_no} compliant"))

    # 7. Lot: format and duplicate
    if lot is None:
        checks.append(Check("lot", "Lot number", False, 10, "no lot number"))
    else:
        dup = [r.id for r in ledger.records.values()
               if r.id != receipt.id and r.kind in RECEIPT_KINDS and r.payload.get("lot") == lot
               and r.ts < receipt.ts]
        if dup:
            checks.append(Check("lot", "Lot number", False, 30, f"lot {lot} already received ({dup[0]})"))
        elif profile is not None and not re.match(profile.lot_pattern, lot):
            checks.append(Check("lot", "Lot number", False, 10, f"unusual lot format {lot}"))
        else:
            checks.append(Check("lot", "Lot number", True, 0, f"lot {lot} never received before"))

    # 8. Supplier bank details (received before the delivery)
    if profile is None:
        checks.append(Check("rib", "Bank details", True, 0, "no supplier record"))
    else:
        changed = [r for r in ledger.records.values()
                   if r.origin == supplier_id and r.ts <= receipt.ts
                   and r.payload.get("rib") not in (None, profile.rib)]
        if changed:
            checks.append(Check("rib", "Bank details", False, 15,
                                "bank details (RIB) different from the supplier record received today"))
        else:
            checks.append(Check("rib", "Bank details", True, 0, "bank details (RIB) match the record"))

    # 9. Active alerts
    flagged = ledger.declaration(supplier_id) is not None or any(
        r.status == "quarantined" for r in inputs)
    if flagged:
        checks.append(Check("alerts", "Active alerts", False, 40,
                            "supplier declared compromised or input data in quarantine"))
    else:
        checks.append(Check("alerts", "Active alerts", True, 0, "no alert on this supplier"))

    score = max(0, 100 - sum(c.penalty for c in checks if not c.ok))
    band = band_of(score)
    failed = [c for c in checks if not c.ok]
    # A physical check already done at receipt counts: in the doubt zone, we
    # flag without blocking; we only put on hold if the lot is suspect.
    physically_checked = bool(receipt.verified)
    hold = score < SUSPECT_THRESHOLD if physically_checked else score < TRUST_THRESHOLD
    return {
        "receipt": receipt_id,
        "label": receipt.label,
        "supplier": supplier_id,
        "lot": lot,
        "order": bc,
        "score": score,
        "band": band,
        "hold": hold,
        "physically_checked": physically_checked,
        "checks": [c.as_dict() for c in checks],
        "explanation": explain(receipt.label, supplier_id, score, band, failed, hold,
                               physically_checked),
    }


def explain(label: str, supplier: str, score: int, band: str, failed: list[Check],
            hold: bool | None = None, physically_checked: bool = False) -> str:
    """Deterministic English explanation (an AI may rephrase it)."""
    if hold is None:
        hold = score < TRUST_THRESHOLD
    if not failed:
        return f"\"{label}\": {score}/100, no deviation from what is known about supplier {supplier}."
    reasons = "; ".join(c.detail for c in sorted(failed, key=lambda c: -c.penalty))
    if hold:
        action = "put on hold: a human must accept or reject the lot before any use"
    elif physically_checked:
        action = "monitor (lot already physically checked at receipt, no hold)"
    else:
        action = "monitor"
    return f"\"{label}\": {score}/100 ({BAND_LABELS.get(band, band)}). {reasons}. Proposal: {action}."
