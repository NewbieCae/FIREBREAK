"""Scénario déterministe Firebreak — journée du 2026-10-10.

Chaîne : Aciers Durand (fournisseur) -> Mécano Précision Loire (fabricant)
-> Logidis Rhône (distributeur) -> Bâtiments Azur (client).

Le fournisseur est compromis depuis 14:00 : il émet ensuite 3 records
malveillants (faux ASN, faux certificat, facture avec RIB modifié) et 1
record légitime dont la réception est vérifiée physiquement (stop rule).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .engine import Ledger
from .federation import Federation
from .model import Company, Record
from .simulation import Simulation

DAY = datetime(2026, 10, 10)
COMPROMISED_SINCE = datetime(2026, 10, 10, 14, 0, 0)

COMPANIES = [
    Company("fournisseur", "Aciers Durand", "Fournisseur d'acier"),
    Company("fabricant", "Mécano Précision Loire", "Fabricant de pièces"),
    Company("distributeur", "Logidis Rhône", "Distributeur régional"),
    Company("client", "Bâtiments Azur", "Client final"),
]

RIB_OK = "FR76 3000 4028 3798 7654 3210 085"
RIB_FRAUD = "FR76 1234 5678 9000 0000 0000 666"


def _t(h: int, m: int = 0) -> datetime:
    return DAY.replace(hour=h, minute=m)


def build_simulation() -> Simulation:
    ledgers = {c.id: Ledger(c.id) for c in COMPANIES}
    fed = Federation([c.id for c in COMPANIES])
    f, m, d, c = (ledgers[k] for k in ("fournisseur", "fabricant", "distributeur", "client"))

    def rec(ledger: Ledger, rid: str, kind: str, ts: datetime, label: str,
            inputs: list[str] | None = None, gate: bool = False,
            verified: bool = False, payload: dict | None = None,
            origin: str | None = None, token: str | None = None) -> Record:
        return ledger.add(Record(
            id=rid, company=ledger.company_id, origin=origin or ledger.company_id,
            kind=kind, ts=ts, label=label, inputs=inputs or [], gate=gate,
            verified=verified, payload=payload or {}, token=token,
        ))

    def send(src: Ledger, src_rid: str, dst: Ledger, dst_rid: str,
             kind: str, ts: datetime, label: str, payload: dict | None = None) -> Record:
        token = fed.register_send(src.company_id, src_rid, dst.company_id, dst_rid)
        return rec(dst, dst_rid, kind, ts, label, origin=src.company_id,
                   token=token, payload=payload)

    # --- 7 livraisons propres, avant 14:00 --------------------------------
    for i in range(1, 8):
        t0 = _t(8, 30) + timedelta(minutes=30 * (i - 1))  # 08:30 -> 11:30
        amount = 4000 + 317 * i
        bc = f"BC-{1000 + i}"
        rec(f, f"f-asn-{i:02d}", "asn", t0, f"ASN commande {bc}")
        rec(f, f"f-cert-{i:02d}", "quality_cert", t0 + timedelta(minutes=2),
            f"Certificat qualité CQ-{2000 + i}")
        rec(f, f"f-inv-{i:02d}", "invoice", t0 + timedelta(minutes=4),
            f"Facture F-{3000 + i}", payload={"amount": amount, "rib": RIB_OK})
        send(f, f"f-asn-{i:02d}", m, f"m-asn-{i:02d}", "asn",
             t0 + timedelta(minutes=10), f"ASN reçu — {bc}")
        send(f, f"f-cert-{i:02d}", m, f"m-cert-{i:02d}", "quality_cert",
             t0 + timedelta(minutes=10), f"Certificat reçu CQ-{2000 + i}")
        send(f, f"f-inv-{i:02d}", m, f"m-inv-{i:02d}", "invoice",
             t0 + timedelta(minutes=10), f"Facture reçue F-{3000 + i}",
             payload={"amount": amount, "rib": RIB_OK})
        rec(m, f"m-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=40),
            f"Réception marchandise {bc}", inputs=[f"m-asn-{i:02d}", f"m-cert-{i:02d}"])
        rec(m, f"m-lot-{i:02d}", "production_lot", t0 + timedelta(minutes=90),
            f"Lancement lot LOT-{500 + i}", inputs=[f"m-gr-{i:02d}"],
            gate=True, payload={"lot": f"LOT-{500 + i}"})
        rec(m, f"m-pay-{i:02d}", "payment", t0 + timedelta(minutes=120),
            f"Paiement facture F-{3000 + i}", inputs=[f"m-inv-{i:02d}"],
            gate=True, payload={"amount": amount, "rib": RIB_OK})
        rec(m, f"m-ship-{i:02d}", "shipment", t0 + timedelta(minutes=150),
            f"Expédition lot LOT-{500 + i}", inputs=[f"m-lot-{i:02d}"], gate=True)
        send(m, f"m-ship-{i:02d}", d, f"d-ship-{i:02d}", "shipment",
             t0 + timedelta(minutes=155), f"Expédition reçue LOT-{500 + i}")
        rec(d, f"d-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=175),
            f"Réception entrepôt LOT-{500 + i}", inputs=[f"d-ship-{i:02d}"])
        rec(d, f"d-out-{i:02d}", "shipment", t0 + timedelta(minutes=210),
            f"Réexpédition LOT-{500 + i} vers client", inputs=[f"d-gr-{i:02d}"],
            gate=True)
        send(d, f"d-out-{i:02d}", c, f"c-ship-{i:02d}", "shipment",
             t0 + timedelta(minutes=215), f"Livraison attendue LOT-{500 + i}")
        rec(c, f"c-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=240),
            f"Réception chantier LOT-{500 + i}", inputs=[f"c-ship-{i:02d}"])
        rec(c, f"c-pay-{i:02d}", "payment", t0 + timedelta(minutes=280),
            f"Paiement LOT-{500 + i}", inputs=[f"c-gr-{i:02d}"],
            gate=True, payload={"amount": amount + 950})

    # --- attaque : 3 records malveillants après 14:00 ----------------------
    rec(f, "f-asn-X", "asn", _t(14, 10), "ASN urgente BC-9999")
    rec(f, "f-cert-X", "quality_cert", _t(14, 12), "Certificat qualité CQ-9999")
    rec(f, "f-inv-X", "invoice", _t(14, 14), "Facture F-9999 — nouveau RIB",
        payload={"amount": 5210, "rib": RIB_FRAUD, "bank_details_change": True})
    send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN reçu — BC-9999")
    send(f, "f-cert-X", m, "m-cert-X", "quality_cert", _t(14, 17),
         "Certificat reçu CQ-9999")
    send(f, "f-inv-X", m, "m-inv-X", "invoice", _t(14, 19),
         "Facture reçue F-9999", payload={"amount": 5210, "rib": RIB_FRAUD})
    rec(m, "m-gr-X", "goods_receipt", _t(14, 40), "Réception marchandise BC-9999",
        inputs=["m-asn-X", "m-cert-X"])
    rec(m, "m-lot-X", "production_lot", _t(15, 0), "Lancement lot LOT-999",
        inputs=["m-gr-X"], gate=True, payload={"lot": "LOT-999"})
    rec(m, "m-pay-X", "payment", _t(15, 10), "Paiement facture F-9999 (RIB modifié)",
        inputs=["m-inv-X"], gate=True, payload={"amount": 5210, "rib": RIB_FRAUD})
    rec(m, "m-ship-X", "shipment", _t(15, 30), "Expédition lot LOT-999",
        inputs=["m-lot-X"], gate=True)
    send(m, "m-ship-X", d, "d-ship-X", "shipment", _t(15, 35),
         "Expédition reçue LOT-999")
    rec(d, "d-gr-X", "goods_receipt", _t(15, 50), "Réception entrepôt LOT-999",
        inputs=["d-ship-X"])
    rec(d, "d-out-X", "shipment", _t(16, 10), "Réexpédition LOT-999 vers client",
        inputs=["d-gr-X"], gate=True)
    send(d, "d-out-X", c, "c-ship-X", "shipment", _t(16, 15),
         "Livraison attendue LOT-999")
    rec(c, "c-gr-X", "goods_receipt", _t(16, 35), "Réception chantier LOT-999",
        inputs=["c-ship-X"])

    # --- livraison légitime post-14:00, réception vérifiée (stop rule) -----
    rec(f, "f-asn-08", "asn", _t(14, 45), "ASN commande BC-1008")
    send(f, "f-asn-08", m, "m-asn-08", "asn", _t(14, 50), "ASN reçu — BC-1008")
    rec(m, "m-gr-08", "goods_receipt", _t(15, 10),
        "Réception BC-1008 (contrôle physique)", inputs=["m-asn-08"],
        verified=True)

    # --- opérations internes sans lien avec l'attaque ----------------------
    padding = [
        (f, "f-int-01", "inventory_count", _t(9, 45), "Inventaire tôles"),
        (f, "f-int-02", "stock_adjustment", _t(11, 15), "Ajustement stock acier"),
        (f, "f-int-03", "catalog_update", _t(13, 0), "Mise à jour catalogue"),
        (m, "m-int-01", "quality_check", _t(10, 0), "Contrôle qualité atelier"),
        (m, "m-int-02", "maintenance", _t(12, 30), "Maintenance presse P2"),
        (m, "m-int-03", "sales_order", _t(9, 30), "Commande interne outillage"),
        (m, "m-int-04", "inventory_count", _t(13, 45), "Inventaire atelier"),
        (m, "m-int-05", "catalog_update", _t(8, 45), "Mise à jour gammes"),
        (d, "d-int-01", "inventory_count", _t(10, 30), "Inventaire entrepôt"),
        (d, "d-int-02", "stock_adjustment", _t(12, 0), "Ajustement stock hub"),
        (d, "d-int-03", "sales_order", _t(11, 0), "Commande client hors chaîne"),
        (d, "d-int-04", "quality_check", _t(13, 15), "Contrôle qualité quai"),
        (c, "c-int-01", "sales_order", _t(9, 15), "Commande chantier B"),
        (c, "c-int-02", "inventory_count", _t(12, 45), "Inventaire dépôt"),
        (c, "c-int-03", "catalog_update", _t(13, 30), "Mise à jour référentiel"),
    ]
    for ledger, rid, kind, ts, label in padding:
        rec(ledger, rid, kind, ts, label)

    sim = Simulation(COMPANIES, ledgers, fed)
    sim.run()
    return sim
