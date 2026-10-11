"""Deterministic Firebreak scenarios: the day of 2026-10-10.

Chain: Aciers Durand (supplier) -> Mécano Précision Loire (manufacturer)
-> Logidis Rhône (distributor) -> Bâtiments Azur (customer).

All scenarios share the same clean morning (7 deliveries before 14:00
and internal operations); the supplier is compromised since 14:00 and
only the attack changes:

- "mixed" (default): fake ASN, fake certificate and invoice with a modified RIB;
- "rib": RIB change by email + invoice -> fraudulent payment;
- "cert": fake quality certificate on a real coil -> non-compliant
  production lot, sub-assembly made with it, shipments;
- "asn": fake shipping notice -> phantom goods receipt, production started
  on non-existent stock, delivery promised to the customer;
- "lot" and "recall": nobody compromised; quality incident on a lot
  (`meta()["incident"]`), handled lot by lot on human decision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .engine import Ledger
from .federation import Federation
from .genealogy import transformation_payload
from .model import Company, Record
from .simulation import Simulation

DAY = datetime(2026, 10, 10)
COMPROMISED_SINCE = datetime(2026, 10, 10, 14, 0, 0)
DEFAULT_SCENARIO = "mixed"

COMPANIES = [
    Company("fournisseur", "Aciers Durand", "Steel supplier", "3012345"),
    Company("fabricant", "Mécano Précision Loire", "Parts manufacturer", "3023456"),
    Company("distributeur", "Logidis Rhône", "Regional distributor", "3034567"),
    Company("client", "Bâtiments Azur", "End customer", "3045678"),
]

RIB_OK = "FR76 3000 4028 3798 7654 3210 085"
RIB_FRAUD = "FR76 1234 5678 9000 0000 0000 666"
PART = "BOBINE-S235-2MM"


def _t(h: int, m: int = 0) -> datetime:
    return DAY.replace(hour=h, minute=m)


class _Builder:
    def __init__(self) -> None:
        self.ledgers = {c.id: Ledger(c.id) for c in COMPANIES}
        self.fed = Federation([c.id for c in COMPANIES])
        self.f, self.m, self.d, self.c = (
            self.ledgers[k] for k in ("fournisseur", "fabricant", "distributeur", "client"))

    def rec(self, ledger: Ledger, rid: str, kind: str, ts: datetime, label: str,
            inputs: list[str] | None = None, gate: bool = False,
            verified: bool = False, payload: dict | None = None,
            origin: str | None = None, token: str | None = None) -> Record:
        return ledger.add(Record(
            id=rid, company=ledger.company_id, origin=origin or ledger.company_id,
            kind=kind, ts=ts, label=label, inputs=inputs or [], gate=gate,
            verified=verified, payload=payload or {}, token=token,
        ))

    def send(self, src: Ledger, src_rid: str, dst: Ledger, dst_rid: str,
             kind: str, ts: datetime, label: str, payload: dict | None = None) -> Record:
        token = self.fed.register_send(src.company_id, src_rid, dst.company_id, dst_rid)
        return self.rec(dst, dst_rid, kind, ts, label, origin=src.company_id,
                        token=token, payload=payload)

    def transform(self, ledger: Ledger, rid: str, ts: datetime, label: str,
                  consumed: list[str], lot: str, extra: dict | None = None) -> Record:
        """Production start: consumed lots -> produced lot (gate)."""
        payload = transformation_payload(
            [ledger.records[i] for i in consumed], lot, extra)
        return self.rec(ledger, rid, "production_lot", ts, label, inputs=consumed,
                        gate=True, payload=payload)


def _clean_morning(b: _Builder) -> None:
    """7 clean deliveries, from the received coil to the customer payment."""
    f, m, d, c = b.f, b.m, b.d, b.c
    for i in range(1, 8):
        t0 = _t(8, 30) + timedelta(minutes=30 * (i - 1))  # 08:30 -> 11:30
        amount = 4000 + 317 * i
        bc = f"BC-{1000 + i}"
        coil = f"COIL-{100 + i}"
        ship = {"bc": f"BC-100{i}", "part": PART, "qty": 12, "lot_no": coil,
                "ship_date": t0.isoformat()}
        cert = {"cert_no": f"CQ-200{i}", "lot_no": coil, "part": PART, "grade": "S235"}
        inv = {"amount": amount, "rib": RIB_OK, "bc": f"BC-100{i}"}
        b.rec(f, f"f-asn-{i:02d}", "asn", t0, f"ASN order {bc}", payload=ship)
        b.rec(f, f"f-cert-{i:02d}", "quality_cert", t0 + timedelta(minutes=2),
              f"Quality certificate CQ-{2000 + i}", payload=cert)
        b.rec(f, f"f-inv-{i:02d}", "invoice", t0 + timedelta(minutes=4),
              f"Invoice F-{3000 + i}", payload=inv)
        b.send(f, f"f-asn-{i:02d}", m, f"m-asn-{i:02d}", "asn",
               t0 + timedelta(minutes=10), f"ASN received: {bc}", payload=ship)
        b.send(f, f"f-cert-{i:02d}", m, f"m-cert-{i:02d}", "quality_cert",
               t0 + timedelta(minutes=10), f"Certificate received CQ-{2000 + i}",
               payload=cert)
        b.send(f, f"f-inv-{i:02d}", m, f"m-inv-{i:02d}", "invoice",
               t0 + timedelta(minutes=10), f"Invoice received F-{3000 + i}",
               payload=inv)
        b.rec(m, f"m-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=40),
              f"Goods receipt {bc}", inputs=[f"m-asn-{i:02d}", f"m-cert-{i:02d}"],
              payload={"lot": coil, "part": PART, "qty": 12, "bc": f"BC-100{i}"})
        b.transform(m, f"m-lot-{i:02d}", t0 + timedelta(minutes=90),
                    f"Lot start LOT-{500 + i}", [f"m-gr-{i:02d}"], f"LOT-{500 + i}")
        b.rec(m, f"m-pay-{i:02d}", "payment", t0 + timedelta(minutes=120),
              f"Invoice payment F-{3000 + i}", inputs=[f"m-inv-{i:02d}"],
              gate=True, payload={"amount": amount, "rib": RIB_OK})
        b.rec(m, f"m-ship-{i:02d}", "shipment", t0 + timedelta(minutes=150),
              f"Lot shipment LOT-{500 + i}", inputs=[f"m-lot-{i:02d}"], gate=True)
        b.send(m, f"m-ship-{i:02d}", d, f"d-ship-{i:02d}", "shipment",
               t0 + timedelta(minutes=155), f"Shipment received LOT-{500 + i}")
        b.rec(d, f"d-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=175),
              f"Warehouse receipt LOT-{500 + i}", inputs=[f"d-ship-{i:02d}"])
        b.rec(d, f"d-out-{i:02d}", "shipment", t0 + timedelta(minutes=210),
              f"Reshipment LOT-{500 + i} to customer", inputs=[f"d-gr-{i:02d}"],
              gate=True)
        b.send(d, f"d-out-{i:02d}", c, f"c-ship-{i:02d}", "shipment",
               t0 + timedelta(minutes=215), f"Expected delivery LOT-{500 + i}")
        b.rec(c, f"c-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=240),
              f"Site receipt LOT-{500 + i}", inputs=[f"c-ship-{i:02d}"])
        b.rec(c, f"c-pay-{i:02d}", "payment", t0 + timedelta(minutes=280),
              f"Payment LOT-{500 + i}", inputs=[f"c-gr-{i:02d}"],
              gate=True, payload={"amount": amount + 950})


def _add_fabricant_afternoon(b: _Builder) -> None:
    """Afternoon of legitimate activity at the manufacturer (14:05 -> 17:25).

    ~40 independent records: they depend ONLY on clean morning data
    (m-gr-01..07, m-lot-01..07) or on each other; never on supplier data
    received after 14:00, never on a tainted record. Payments go to other
    suppliers (usual RIB). Shipments go to the distributor (received
    copies + warehouse receipts).
    """
    m, d = b.m, b.d
    ts = _t(14, 5)

    def nxt(minutes: int = 5) -> datetime:
        nonlocal ts
        t = ts
        ts += timedelta(minutes=minutes)
        return t

    # 6 lots produced from checked morning stock
    for i in range(1, 7):
        b.transform(m, f"m-lot-a{i}", nxt(), f"Lot start LOT-A{i}0 (morning stock)",
                    [f"m-gr-0{i}"], f"LOT-A{i}0")
    # 6 lot quality checks
    for i in range(1, 7):
        b.rec(m, f"m-qc-a{i}", "quality_check", nxt(),
              f"Quality check LOT-A{i}0", inputs=[f"m-lot-a{i}"])
    # 6 packagings
    for i in range(1, 7):
        b.rec(m, f"m-pack-a{i}", "packaging", nxt(),
              f"Packaging LOT-A{i}0", inputs=[f"m-qc-a{i}"])
    # 4 internal transfers to the dock
    for i in range(1, 5):
        b.rec(m, f"m-tr-a{i}", "internal_transfer", nxt(),
              f"Dock transfer LOT-A{i}0", inputs=[f"m-pack-a{i}"])
    # 4 shipments to the distributor (+ warehouse receipts on d's side)
    for i in range(1, 5):
        b.rec(m, f"m-ship-a{i}", "shipment", nxt(),
              f"Shipment LOT-A{i}0", inputs=[f"m-tr-a{i}"], gate=True)
        b.send(m, f"m-ship-a{i}", d, f"d-ship-a{i}", "shipment",
               nxt(2), f"Shipment received LOT-A{i}0")
        b.rec(d, f"d-gr-a{i}", "goods_receipt", nxt(5),
              f"Warehouse receipt LOT-A{i}0", inputs=[f"d-ship-a{i}"])
    # 4 orders + payments to other suppliers
    for i, amount in enumerate((2250, 2700, 3150, 3600), start=1):
        b.rec(m, f"m-po-a{i}", "purchase_order", nxt(),
              f"Order BC-A{i}0 alternative supplier")
        b.rec(m, f"m-pay-a{i}", "payment", nxt(),
              f"Order payment BC-A{i}0", inputs=[f"m-po-a{i}"],
              gate=True, payload={"amount": amount, "rib": RIB_OK})
    # 6 miscellaneous internal operations
    b.rec(m, "m-so-a1", "sales_order", nxt(), "Direct site order SO-A1")
    b.rec(m, "m-so-a2", "sales_order", nxt(), "Distributor order SO-A2")
    b.rec(m, "m-ic-a1", "inventory_count", nxt(), "Afternoon coil inventory")
    b.rec(m, "m-mnt-a1", "maintenance", nxt(), "Cutter D1 maintenance")
    b.rec(m, "m-qc-a7", "quality_check", nxt(), "Check LOT-502",
          inputs=["m-lot-02"])
    b.rec(m, "m-adj-a1", "stock_adjustment", nxt(), "Afternoon stock adjustment")


def _internal_ops(b: _Builder) -> None:
    """Internal operations unrelated to the attack."""
    f, m, d, c = b.f, b.m, b.d, b.c
    padding = [
        (f, "f-int-01", "inventory_count", _t(9, 45), "Sheet metal inventory"),
        (f, "f-int-02", "stock_adjustment", _t(11, 15), "Steel stock adjustment"),
        (f, "f-int-03", "catalog_update", _t(13, 0), "Catalog update"),
        (m, "m-int-01", "quality_check", _t(10, 0), "Workshop quality check"),
        (m, "m-int-02", "maintenance", _t(12, 30), "Press P2 maintenance"),
        (m, "m-int-03", "sales_order", _t(9, 30), "Internal tooling order"),
        (m, "m-int-04", "inventory_count", _t(13, 45), "Workshop inventory"),
        (m, "m-int-05", "catalog_update", _t(8, 45), "Routing update"),
        (d, "d-int-01", "inventory_count", _t(10, 30), "Warehouse inventory"),
        (d, "d-int-02", "stock_adjustment", _t(12, 0), "Hub stock adjustment"),
        (d, "d-int-03", "sales_order", _t(11, 0), "Off-chain customer order"),
        (d, "d-int-04", "quality_check", _t(13, 15), "Dock quality check"),
        (c, "c-int-01", "sales_order", _t(9, 15), "Site B order"),
        (c, "c-int-02", "inventory_count", _t(12, 45), "Depot inventory"),
        (c, "c-int-03", "catalog_update", _t(13, 30), "Master data update"),
    ]
    for ledger, rid, kind, ts, label in padding:
        b.rec(ledger, rid, kind, ts, label)


def _legit_ship_08() -> dict:
    return {"bc": "BC-1008", "part": PART, "qty": 12, "lot_no": "COIL-108",
            "ship_date": _t(14, 45).isoformat()}


def _legit_gr_08() -> dict:
    return {"lot": "COIL-108", "part": PART, "qty": 12, "bc": "BC-1008"}


def _attack_mixed(b: _Builder) -> None:
    """The three attacks mixed, then a verified legitimate delivery."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-9999", "part": PART, "qty": 30, "lot_no": "COIL-999",
            "ship_date": _t(14, 10).isoformat()}
    cert = {"cert_no": "CQ-9999", "lot_no": "COIL-999", "part": PART, "grade": "S235"}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "Urgent ASN BC-9999", payload=ship)
    b.rec(f, "f-cert-X", "quality_cert", _t(14, 12), "Quality certificate CQ-9999",
          payload=cert)
    b.rec(f, "f-inv-X", "invoice", _t(14, 14), "Invoice F-9999 (new RIB)",
          payload={"amount": 5210, "rib": RIB_FRAUD, "bank_details_change": True,
                   "bc": "BC-9999"})
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN received: BC-9999",
           payload=ship)
    b.send(f, "f-cert-X", m, "m-cert-X", "quality_cert", _t(14, 17),
           "Certificate received CQ-9999", payload=cert)
    b.send(f, "f-inv-X", m, "m-inv-X", "invoice", _t(14, 19),
           "Invoice received F-9999",
           payload={"amount": 5210, "rib": RIB_FRAUD, "bc": "BC-9999"})
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 40), "Goods receipt BC-9999",
          inputs=["m-asn-X", "m-cert-X"],
          payload={"lot": "COIL-999", "part": PART, "qty": 30, "bc": "BC-9999"})
    b.transform(m, "m-lot-X", _t(15, 0), "Lot start LOT-999", ["m-gr-X"], "LOT-999")
    b.rec(m, "m-pay-X", "payment", _t(15, 10), "Invoice payment F-9999 (modified RIB)",
          inputs=["m-inv-X"], gate=True, payload={"amount": 5210, "rib": RIB_FRAUD})
    b.rec(m, "m-ship-X", "shipment", _t(15, 30), "Lot shipment LOT-999",
          inputs=["m-lot-X"], gate=True)
    b.send(m, "m-ship-X", d, "d-ship-X", "shipment", _t(15, 35),
           "Shipment received LOT-999")
    b.rec(d, "d-gr-X", "goods_receipt", _t(15, 50), "Warehouse receipt LOT-999",
          inputs=["d-ship-X"])
    b.rec(d, "d-out-X", "shipment", _t(16, 10), "Reshipment LOT-999 to customer",
          inputs=["d-gr-X"], gate=True)
    b.send(d, "d-out-X", c, "c-ship-X", "shipment", _t(16, 15),
           "Expected delivery LOT-999")
    b.rec(c, "c-gr-X", "goods_receipt", _t(16, 35), "Site receipt LOT-999",
          inputs=["c-ship-X"])

    # legitimate delivery after 14:00, verified receipt (stop rule)
    ship = _legit_ship_08()
    b.rec(f, "f-asn-08", "asn", _t(14, 45), "ASN order BC-1008", payload=ship)
    b.send(f, "f-asn-08", m, "m-asn-08", "asn", _t(14, 50), "ASN received: BC-1008",
           payload=ship)
    b.rec(m, "m-gr-08", "goods_receipt", _t(15, 10),
          "Goods receipt BC-1008 (physical check)", inputs=["m-asn-08"],
          verified=True, payload=_legit_gr_08())


def _attack_rib(b: _Builder) -> None:
    """RIB fraud: the bank-details change email modifies the supplier
    record, then an invoice is paid to the new RIB. A legitimate invoice
    in the window is confirmed by a callback."""
    f, m = b.f, b.m
    b.rec(f, "f-bank-X", "bank_details_change", _t(14, 5),
          "Email: bank details change",
          payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK, "bank_details_change": True})
    b.rec(f, "f-inv-X", "invoice", _t(14, 14), "Invoice F-9999 (new RIB)",
          payload={"amount": 5210, "rib": RIB_FRAUD, "bank_details_change": True,
                   "bc": "BC-1010"})
    b.send(f, "f-bank-X", m, "m-bank-X", "bank_details_change", _t(14, 8),
           "RIB change received (email)",
           payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK, "bank_details_change": True})
    b.send(f, "f-inv-X", m, "m-inv-X", "invoice", _t(14, 19),
           "Invoice received F-9999",
           payload={"amount": 5210, "rib": RIB_FRAUD, "bc": "BC-1010"})
    b.rec(m, "m-vendor-X", "vendor_master_update", _t(14, 30),
          "Supplier record: RIB replaced", inputs=["m-bank-X"],
          payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK})
    b.rec(m, "m-pay-X", "payment", _t(15, 10), "Invoice payment F-9999 (modified RIB)",
          inputs=["m-inv-X", "m-vendor-X"], gate=True,
          payload={"amount": 5210, "rib": RIB_FRAUD})

    b.rec(f, "f-inv-08", "invoice", _t(14, 40), "Invoice F-3008",
          payload={"amount": 4950, "rib": RIB_OK, "bc": "BC-1008"})
    b.send(f, "f-inv-08", m, "m-inv-08", "invoice", _t(14, 45), "Invoice received F-3008",
           payload={"amount": 4950, "rib": RIB_OK, "bc": "BC-1008"})
    b.rec(m, "m-call-08", "callback_verification", _t(15, 0),
          "Callback to the known number: F-3008 confirmed", inputs=["m-inv-08"],
          verified=True)
    b.rec(m, "m-pay-08", "payment", _t(15, 20), "Invoice payment F-3008",
          inputs=["m-call-08"], gate=True, payload={"amount": 4950, "rib": RIB_OK})


def _attack_cert(b: _Builder) -> None:
    """Fake certificate: coil COIL-210 exists (weighed at receipt), but its
    quality certificate is fake. Lot LOT-901 made with it, sub-assembly
    ASM-950 made with LOT-901 and their shipments are blocked; lot LOT-902
    (other coils) keeps going."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-1010", "part": PART, "qty": 12, "lot_no": "COIL-210",
            "ship_date": _t(14, 10).isoformat()}
    cert = {"cert_no": "CQ-9999", "lot": "COIL-210", "lot_no": "COIL-210", "part": PART, "grade": "S355"}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "ASN order BC-1010 (coil COIL-210)",
          payload=ship)
    b.rec(f, "f-cert-X", "quality_cert", _t(14, 12), "Quality certificate CQ-9999",
          payload=cert)
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN received: BC-1010",
           payload=ship)
    b.send(f, "f-cert-X", m, "m-cert-X", "quality_cert", _t(14, 17),
           "Certificate received CQ-9999 (COIL-210)", payload=cert)
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 40),
          "Coil receipt COIL-210 (weighed and counted)", inputs=["m-asn-X"],
          verified=True,
          payload={"lot": "COIL-210", "part": PART, "qty": 12, "bc": "BC-1010"})
    b.rec(m, "m-qc-X", "quality_release", _t(14, 50),
          "Quality release COIL-210 on certificate CQ-9999",
          inputs=["m-gr-X", "m-cert-X"], payload={"lot": "COIL-210"})
    b.transform(m, "m-lot-901", _t(15, 0), "Lot LOT-901 (coils COIL-210 + COIL-107)",
                ["m-qc-X", "m-gr-07"], "LOT-901")
    b.transform(m, "m-lot-902", _t(15, 5), "Lot LOT-902 (coils COIL-106 + COIL-107)",
                ["m-gr-06", "m-gr-07"], "LOT-902")
    b.transform(m, "m-asm-950", _t(15, 30), "Sub-assembly ASM-950 (LOT-901 + LOT-902)",
                ["m-lot-901", "m-lot-902"], "ASM-950")
    b.rec(m, "m-ship-902", "shipment", _t(15, 40), "Lot shipment LOT-902",
          inputs=["m-lot-902"], gate=True)
    b.rec(m, "m-ship-950", "shipment", _t(15, 45), "Sub-assembly shipment ASM-950",
          inputs=["m-asm-950"], gate=True)
    b.send(m, "m-ship-902", d, "d-ship-902", "shipment", _t(15, 45),
           "Shipment received LOT-902")
    b.rec(d, "d-gr-902", "goods_receipt", _t(16, 0), "Warehouse receipt LOT-902",
          inputs=["d-ship-902"])
    b.send(m, "m-ship-950", d, "d-ship-950", "shipment", _t(15, 50),
           "Shipment received ASM-950")
    b.rec(d, "d-gr-950", "goods_receipt", _t(16, 5), "Warehouse receipt ASM-950",
          inputs=["d-ship-950"])
    b.rec(d, "d-out-950", "shipment", _t(16, 30), "Reshipment ASM-950 to customer",
          inputs=["d-gr-950"], gate=True)
    b.send(d, "d-out-950", c, "c-ship-950", "shipment", _t(16, 35),
           "Expected delivery ASM-950")
    b.rec(c, "c-gr-950", "goods_receipt", _t(16, 55), "Site receipt ASM-950",
          inputs=["c-ship-950"])


def _attack_asn(b: _Builder) -> None:
    """Fake shipping notice: coil COIL-299 does not exist. The goods receipt
    is entered from the ASN without a check, production is started on this
    phantom stock and delivery is promised all the way to the customer. A
    real delivery in the window, physically checked, keeps going."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-9999", "part": PART, "qty": 12, "lot_no": "COIL-299",
            "ship_date": _t(14, 10).isoformat()}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "Urgent ASN BC-9999 (coil COIL-299)",
          payload=ship)
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN received: BC-9999",
           payload=ship)
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 30),
          "Goods receipt COIL-299 entered from the ASN (no check)", inputs=["m-asn-X"],
          payload={"lot": "COIL-299", "part": PART, "qty": 12, "bc": "BC-9999"})
    b.rec(m, "m-stock-X", "stock_entry", _t(14, 35), "Stock entry COIL-299",
          inputs=["m-gr-X"], payload={"lot": "COIL-299"})
    b.transform(m, "m-lot-X", _t(15, 0), "Lot start LOT-999 (COIL-299 + COIL-107)",
                ["m-stock-X", "m-gr-07"], "LOT-999")
    b.rec(m, "m-ship-X", "shipment", _t(15, 30), "Lot shipment LOT-999",
          inputs=["m-lot-X"], gate=True)
    b.send(m, "m-ship-X", d, "d-ship-X", "shipment", _t(15, 35),
           "Announced shipment LOT-999")
    b.rec(d, "d-res-X", "reservation", _t(15, 50), "Customer reservation on LOT-999",
          inputs=["d-ship-X"])
    b.rec(d, "d-out-X", "shipment", _t(16, 10), "Reshipment LOT-999 to customer",
          inputs=["d-res-X"], gate=True)
    b.send(d, "d-out-X", c, "c-ship-X", "shipment", _t(16, 15),
           "Promised delivery LOT-999")
    b.rec(c, "c-plan-X", "work_plan", _t(16, 30), "Site schedule based on LOT-999",
          inputs=["c-ship-X"])

    ship = _legit_ship_08()
    b.rec(f, "f-asn-08", "asn", _t(14, 45), "ASN order BC-1008 (coil COIL-108)",
          payload=ship)
    b.send(f, "f-asn-08", m, "m-asn-08", "asn", _t(14, 50), "ASN received: BC-1008",
           payload=ship)
    b.rec(m, "m-gr-08", "goods_receipt", _t(15, 10),
          "Goods receipt COIL-108 (physical check)", inputs=["m-asn-08"],
          verified=True, payload=_legit_gr_08())
    b.transform(m, "m-lot-908", _t(15, 40), "Lot start LOT-908 (COIL-108)",
                ["m-gr-08"], "LOT-908")


def _attack_none(b: _Builder) -> None:
    """Quality scenarios: nobody is compromised, the base morning and afternoon
    are enough (COIL-104 -> LOT-504 + LOT-A40, COIL-103 -> LOT-503 + LOT-A30).
    Payment m-pay-04 depends on the invoice, not the coil: it stays ok."""


@dataclass(frozen=True)
class ScenarioDef:
    id: str
    label: str
    description: str
    attack: Callable[[_Builder], None]
    incident: dict | None = None

    def meta(self) -> dict:
        meta = {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "compromise": {"company": "fournisseur",
                           "since": COMPROMISED_SINCE.isoformat()},
        }
        if self.incident is not None:
            meta["incident"] = dict(self.incident)
        return meta


SCENARIOS: dict[str, ScenarioDef] = {s.id: s for s in [
    ScenarioDef(
        "mixed", "Mixed attack",
        "The compromised supplier sends a fake shipping notice, a fake "
        "certificate and an invoice with a modified RIB.",
        _attack_mixed),
    ScenarioDef(
        "rib", "RIB fraud",
        "A RIB change email modifies the supplier record; the next invoice "
        "would be paid into the fraudster's account.",
        _attack_rib),
    ScenarioDef(
        "cert", "Fake quality certificate",
        "A real coil arrives with a fake certificate: the lot made with it, "
        "the sub-assembly that includes it and their shipments are blocked.",
        _attack_cert),
    ScenarioDef(
        "asn", "Fake shipping notice",
        "A non-existent delivery is announced: phantom goods receipt, production "
        "started on stock that does not exist, delivery promised to the customer.",
        _attack_asn),
    ScenarioDef(
        "lot", "Defective lot",
        "The receiving inspection detects a casting defect on coil COIL-104: "
        "isolate that lot and what derives from it, without blacklisting the supplier.",
        _attack_none,
        {"type": "lot", "company": "fabricant", "lot": "COIL-104",
         "reason": "Casting defect reported by the receiving inspection"}),
    ScenarioDef(
        "recall", "Recall from a finished product",
        "Breakage on site on LOT-503: the analysis traces back to coil COIL-103 "
        "and measures what a recall would affect.",
        _attack_none,
        {"type": "recall", "company": "fabricant", "target": "LOT-503",
         "suspect_lot": "COIL-103",
         "reason": "Breakage on site, quality analysis: coil at fault"}),
]}


def scenarios_meta() -> list[dict]:
    return [s.meta() for s in SCENARIOS.values()]


def build_simulation(scenario: str = DEFAULT_SCENARIO) -> Simulation:
    definition = SCENARIOS.get(scenario)
    if definition is None:
        raise ValueError(f"unknown scenario: {scenario}")
    b = _Builder()
    _clean_morning(b)
    definition.attack(b)
    _internal_ops(b)
    _add_fabricant_afternoon(b)
    sim = Simulation(COMPANIES, b.ledgers, b.fed, scenario=definition.meta())
    sim.run()
    return sim
