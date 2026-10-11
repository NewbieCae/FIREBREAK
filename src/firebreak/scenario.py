"""Scénarios déterministes Firebreak — journée du 2026-10-10.

Chaîne : Aciers Durand (fournisseur) -> Mécano Précision Loire (fabricant)
-> Logidis Rhône (distributeur) -> Bâtiments Azur (client).

Tous les scénarios partagent la même matinée propre (7 livraisons avant
14:00 et des opérations internes) ; le fournisseur est compromis depuis
14:00 et seule l'attaque change :

- "mixed" (défaut) : faux ASN, faux certificat et facture au RIB modifié ;
- "rib" : changement de RIB par mail + facture → paiement frauduleux ;
- "cert" : faux certificat qualité sur une bobine réelle → lot de
  production non conforme, sous-ensemble fabriqué avec, expéditions ;
- "asn" : faux avis d'expédition → réception fantôme, production lancée
  sur un stock inexistant, livraison promise au client ;
- "lot" et "recall" : aucun compromis ; incident qualité sur un lot
  (`meta()["incident"]`), traité lot par lot sur décision humaine.
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
    Company("fournisseur", "Aciers Durand", "Fournisseur d'acier", "3012345"),
    Company("fabricant", "Mécano Précision Loire", "Fabricant de pièces", "3023456"),
    Company("distributeur", "Logidis Rhône", "Distributeur régional", "3034567"),
    Company("client", "Bâtiments Azur", "Client final", "3045678"),
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
        """Lancement de production : lots consommés -> lot produit (gate)."""
        payload = transformation_payload(
            [ledger.records[i] for i in consumed], lot, extra)
        return self.rec(ledger, rid, "production_lot", ts, label, inputs=consumed,
                        gate=True, payload=payload)


def _clean_morning(b: _Builder) -> None:
    """7 livraisons propres, de la bobine reçue au paiement du client."""
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
        b.rec(f, f"f-asn-{i:02d}", "asn", t0, f"ASN commande {bc}", payload=ship)
        b.rec(f, f"f-cert-{i:02d}", "quality_cert", t0 + timedelta(minutes=2),
              f"Certificat qualité CQ-{2000 + i}", payload=cert)
        b.rec(f, f"f-inv-{i:02d}", "invoice", t0 + timedelta(minutes=4),
              f"Facture F-{3000 + i}", payload=inv)
        b.send(f, f"f-asn-{i:02d}", m, f"m-asn-{i:02d}", "asn",
               t0 + timedelta(minutes=10), f"ASN reçu — {bc}", payload=ship)
        b.send(f, f"f-cert-{i:02d}", m, f"m-cert-{i:02d}", "quality_cert",
               t0 + timedelta(minutes=10), f"Certificat reçu CQ-{2000 + i}",
               payload=cert)
        b.send(f, f"f-inv-{i:02d}", m, f"m-inv-{i:02d}", "invoice",
               t0 + timedelta(minutes=10), f"Facture reçue F-{3000 + i}",
               payload=inv)
        b.rec(m, f"m-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=40),
              f"Réception marchandise {bc}", inputs=[f"m-asn-{i:02d}", f"m-cert-{i:02d}"],
              payload={"lot": coil, "part": PART, "qty": 12, "bc": f"BC-100{i}"})
        b.transform(m, f"m-lot-{i:02d}", t0 + timedelta(minutes=90),
                    f"Lancement lot LOT-{500 + i}", [f"m-gr-{i:02d}"], f"LOT-{500 + i}")
        b.rec(m, f"m-pay-{i:02d}", "payment", t0 + timedelta(minutes=120),
              f"Paiement facture F-{3000 + i}", inputs=[f"m-inv-{i:02d}"],
              gate=True, payload={"amount": amount, "rib": RIB_OK})
        b.rec(m, f"m-ship-{i:02d}", "shipment", t0 + timedelta(minutes=150),
              f"Expédition lot LOT-{500 + i}", inputs=[f"m-lot-{i:02d}"], gate=True)
        b.send(m, f"m-ship-{i:02d}", d, f"d-ship-{i:02d}", "shipment",
               t0 + timedelta(minutes=155), f"Expédition reçue LOT-{500 + i}")
        b.rec(d, f"d-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=175),
              f"Réception entrepôt LOT-{500 + i}", inputs=[f"d-ship-{i:02d}"])
        b.rec(d, f"d-out-{i:02d}", "shipment", t0 + timedelta(minutes=210),
              f"Réexpédition LOT-{500 + i} vers client", inputs=[f"d-gr-{i:02d}"],
              gate=True)
        b.send(d, f"d-out-{i:02d}", c, f"c-ship-{i:02d}", "shipment",
               t0 + timedelta(minutes=215), f"Livraison attendue LOT-{500 + i}")
        b.rec(c, f"c-gr-{i:02d}", "goods_receipt", t0 + timedelta(minutes=240),
              f"Réception chantier LOT-{500 + i}", inputs=[f"c-ship-{i:02d}"])
        b.rec(c, f"c-pay-{i:02d}", "payment", t0 + timedelta(minutes=280),
              f"Paiement LOT-{500 + i}", inputs=[f"c-gr-{i:02d}"],
              gate=True, payload={"amount": amount + 950})


def _add_fabricant_afternoon(b: _Builder) -> None:
    """Après-midi d'activité légitime au fabricant (14:05 → 17:25).

    ~40 records indépendants : ils ne dépendent QUE de données matinales
    propres (m-gr-01..07, m-lot-01..07) ou entre eux — jamais d'une donnée
    fournisseur reçue après 14:00, jamais d'un record contaminé. Les
    paiements vont à d'autres fournisseurs (RIB habituel). Les expéditions
    partent vers le distributeur (copies reçues + réceptions en entrepôt).
    """
    m, d = b.m, b.d
    ts = _t(14, 5)

    def nxt(minutes: int = 5) -> datetime:
        nonlocal ts
        t = ts
        ts += timedelta(minutes=minutes)
        return t

    # 6 lots produits sur stock matinal contrôlé
    for i in range(1, 7):
        b.transform(m, f"m-lot-a{i}", nxt(), f"Lancement lot LOT-A{i}0 (stock matinal)",
                    [f"m-gr-0{i}"], f"LOT-A{i}0")
    # 6 contrôles qualité des lots
    for i in range(1, 7):
        b.rec(m, f"m-qc-a{i}", "quality_check", nxt(),
              f"Contrôle qualité LOT-A{i}0", inputs=[f"m-lot-a{i}"])
    # 6 emballages
    for i in range(1, 7):
        b.rec(m, f"m-pack-a{i}", "packaging", nxt(),
              f"Emballage LOT-A{i}0", inputs=[f"m-qc-a{i}"])
    # 4 transferts internes vers le quai
    for i in range(1, 5):
        b.rec(m, f"m-tr-a{i}", "internal_transfer", nxt(),
              f"Transfert quai LOT-A{i}0", inputs=[f"m-pack-a{i}"])
    # 4 expéditions vers le distributeur (+ réceptions entrepôt côté d)
    for i in range(1, 5):
        b.rec(m, f"m-ship-a{i}", "shipment", nxt(),
              f"Expédition LOT-A{i}0", inputs=[f"m-tr-a{i}"], gate=True)
        b.send(m, f"m-ship-a{i}", d, f"d-ship-a{i}", "shipment",
               nxt(2), f"Expédition reçue LOT-A{i}0")
        b.rec(d, f"d-gr-a{i}", "goods_receipt", nxt(5),
              f"Réception entrepôt LOT-A{i}0", inputs=[f"d-ship-a{i}"])
    # 4 commandes + paiements à d'autres fournisseurs
    for i, amount in enumerate((2250, 2700, 3150, 3600), start=1):
        b.rec(m, f"m-po-a{i}", "purchase_order", nxt(),
              f"Commande BC-A{i}0 fournisseur alternatif")
        b.rec(m, f"m-pay-a{i}", "payment", nxt(),
              f"Paiement commande BC-A{i}0", inputs=[f"m-po-a{i}"],
              gate=True, payload={"amount": amount, "rib": RIB_OK})
    # 6 opérations internes diverses
    b.rec(m, "m-so-a1", "sales_order", nxt(), "Commande chantier direct SO-A1")
    b.rec(m, "m-so-a2", "sales_order", nxt(), "Commande distributeur SO-A2")
    b.rec(m, "m-ic-a1", "inventory_count", nxt(), "Inventaire bobines aprèm")
    b.rec(m, "m-mnt-a1", "maintenance", nxt(), "Maintenance découpeuse D1")
    b.rec(m, "m-qc-a7", "quality_check", nxt(), "Contrôle LOT-502",
          inputs=["m-lot-02"])
    b.rec(m, "m-adj-a1", "stock_adjustment", nxt(), "Ajustement stock aprèm")


def _internal_ops(b: _Builder) -> None:
    """Opérations internes sans lien avec l'attaque."""
    f, m, d, c = b.f, b.m, b.d, b.c
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
        b.rec(ledger, rid, kind, ts, label)


def _legit_ship_08() -> dict:
    return {"bc": "BC-1008", "part": PART, "qty": 12, "lot_no": "COIL-108",
            "ship_date": _t(14, 45).isoformat()}


def _legit_gr_08() -> dict:
    return {"lot": "COIL-108", "part": PART, "qty": 12, "bc": "BC-1008"}


def _attack_mixed(b: _Builder) -> None:
    """Les trois attaques mélangées, puis une livraison légitime vérifiée."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-9999", "part": PART, "qty": 30, "lot_no": "COIL-999",
            "ship_date": _t(14, 10).isoformat()}
    cert = {"cert_no": "CQ-9999", "lot_no": "COIL-999", "part": PART, "grade": "S235"}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "ASN urgente BC-9999", payload=ship)
    b.rec(f, "f-cert-X", "quality_cert", _t(14, 12), "Certificat qualité CQ-9999",
          payload=cert)
    b.rec(f, "f-inv-X", "invoice", _t(14, 14), "Facture F-9999 — nouveau RIB",
          payload={"amount": 5210, "rib": RIB_FRAUD, "bank_details_change": True,
                   "bc": "BC-9999"})
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN reçu — BC-9999",
           payload=ship)
    b.send(f, "f-cert-X", m, "m-cert-X", "quality_cert", _t(14, 17),
           "Certificat reçu CQ-9999", payload=cert)
    b.send(f, "f-inv-X", m, "m-inv-X", "invoice", _t(14, 19),
           "Facture reçue F-9999",
           payload={"amount": 5210, "rib": RIB_FRAUD, "bc": "BC-9999"})
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 40), "Réception marchandise BC-9999",
          inputs=["m-asn-X", "m-cert-X"],
          payload={"lot": "COIL-999", "part": PART, "qty": 30, "bc": "BC-9999"})
    b.transform(m, "m-lot-X", _t(15, 0), "Lancement lot LOT-999", ["m-gr-X"], "LOT-999")
    b.rec(m, "m-pay-X", "payment", _t(15, 10), "Paiement facture F-9999 (RIB modifié)",
          inputs=["m-inv-X"], gate=True, payload={"amount": 5210, "rib": RIB_FRAUD})
    b.rec(m, "m-ship-X", "shipment", _t(15, 30), "Expédition lot LOT-999",
          inputs=["m-lot-X"], gate=True)
    b.send(m, "m-ship-X", d, "d-ship-X", "shipment", _t(15, 35),
           "Expédition reçue LOT-999")
    b.rec(d, "d-gr-X", "goods_receipt", _t(15, 50), "Réception entrepôt LOT-999",
          inputs=["d-ship-X"])
    b.rec(d, "d-out-X", "shipment", _t(16, 10), "Réexpédition LOT-999 vers client",
          inputs=["d-gr-X"], gate=True)
    b.send(d, "d-out-X", c, "c-ship-X", "shipment", _t(16, 15),
           "Livraison attendue LOT-999")
    b.rec(c, "c-gr-X", "goods_receipt", _t(16, 35), "Réception chantier LOT-999",
          inputs=["c-ship-X"])

    # livraison légitime post-14:00, réception vérifiée (stop rule)
    ship = _legit_ship_08()
    b.rec(f, "f-asn-08", "asn", _t(14, 45), "ASN commande BC-1008", payload=ship)
    b.send(f, "f-asn-08", m, "m-asn-08", "asn", _t(14, 50), "ASN reçu — BC-1008",
           payload=ship)
    b.rec(m, "m-gr-08", "goods_receipt", _t(15, 10),
          "Réception BC-1008 (contrôle physique)", inputs=["m-asn-08"],
          verified=True, payload=_legit_gr_08())


def _attack_rib(b: _Builder) -> None:
    """Fraude au RIB : le mail de changement de coordonnées bancaires modifie
    la fiche fournisseur, puis une facture est payée sur le nouveau RIB.
    Une facture légitime de la fenêtre est confirmée par contre-appel."""
    f, m = b.f, b.m
    b.rec(f, "f-bank-X", "bank_details_change", _t(14, 5),
          "Mail : changement de coordonnées bancaires",
          payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK, "bank_details_change": True})
    b.rec(f, "f-inv-X", "invoice", _t(14, 14), "Facture F-9999 — nouveau RIB",
          payload={"amount": 5210, "rib": RIB_FRAUD, "bank_details_change": True,
                   "bc": "BC-1010"})
    b.send(f, "f-bank-X", m, "m-bank-X", "bank_details_change", _t(14, 8),
           "Changement de RIB reçu (mail)",
           payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK, "bank_details_change": True})
    b.send(f, "f-inv-X", m, "m-inv-X", "invoice", _t(14, 19),
           "Facture reçue F-9999",
           payload={"amount": 5210, "rib": RIB_FRAUD, "bc": "BC-1010"})
    b.rec(m, "m-vendor-X", "vendor_master_update", _t(14, 30),
          "Fiche fournisseur : RIB remplacé", inputs=["m-bank-X"],
          payload={"rib": RIB_FRAUD, "previous_rib": RIB_OK})
    b.rec(m, "m-pay-X", "payment", _t(15, 10), "Paiement facture F-9999 (RIB modifié)",
          inputs=["m-inv-X", "m-vendor-X"], gate=True,
          payload={"amount": 5210, "rib": RIB_FRAUD})

    b.rec(f, "f-inv-08", "invoice", _t(14, 40), "Facture F-3008",
          payload={"amount": 4950, "rib": RIB_OK, "bc": "BC-1008"})
    b.send(f, "f-inv-08", m, "m-inv-08", "invoice", _t(14, 45), "Facture reçue F-3008",
           payload={"amount": 4950, "rib": RIB_OK, "bc": "BC-1008"})
    b.rec(m, "m-call-08", "callback_verification", _t(15, 0),
          "Contre-appel au numéro connu : F-3008 confirmée", inputs=["m-inv-08"],
          verified=True)
    b.rec(m, "m-pay-08", "payment", _t(15, 20), "Paiement facture F-3008",
          inputs=["m-call-08"], gate=True, payload={"amount": 4950, "rib": RIB_OK})


def _attack_cert(b: _Builder) -> None:
    """Faux certificat : la bobine COIL-210 existe (pesée à réception), mais
    son certificat qualité est faux. Le lot LOT-901 fabriqué avec elle, le
    sous-ensemble ASM-950 fabriqué avec LOT-901 et leurs expéditions sont
    bloqués ; le lot LOT-902 (autres bobines) continue."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-1010", "part": PART, "qty": 12, "lot_no": "COIL-210",
            "ship_date": _t(14, 10).isoformat()}
    cert = {"cert_no": "CQ-9999", "lot": "COIL-210", "lot_no": "COIL-210", "part": PART, "grade": "S355"}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "ASN commande BC-1010 (bobine COIL-210)",
          payload=ship)
    b.rec(f, "f-cert-X", "quality_cert", _t(14, 12), "Certificat qualité CQ-9999",
          payload=cert)
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN reçu — BC-1010",
           payload=ship)
    b.send(f, "f-cert-X", m, "m-cert-X", "quality_cert", _t(14, 17),
           "Certificat reçu CQ-9999 (COIL-210)", payload=cert)
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 40),
          "Réception bobine COIL-210 (pesée et comptage)", inputs=["m-asn-X"],
          verified=True,
          payload={"lot": "COIL-210", "part": PART, "qty": 12, "bc": "BC-1010"})
    b.rec(m, "m-qc-X", "quality_release", _t(14, 50),
          "Libération qualité COIL-210 sur certificat CQ-9999",
          inputs=["m-gr-X", "m-cert-X"], payload={"lot": "COIL-210"})
    b.transform(m, "m-lot-901", _t(15, 0), "Lot LOT-901 (bobines COIL-210 + COIL-107)",
                ["m-qc-X", "m-gr-07"], "LOT-901")
    b.transform(m, "m-lot-902", _t(15, 5), "Lot LOT-902 (bobines COIL-106 + COIL-107)",
                ["m-gr-06", "m-gr-07"], "LOT-902")
    b.transform(m, "m-asm-950", _t(15, 30), "Sous-ensemble ASM-950 (LOT-901 + LOT-902)",
                ["m-lot-901", "m-lot-902"], "ASM-950")
    b.rec(m, "m-ship-902", "shipment", _t(15, 40), "Expédition lot LOT-902",
          inputs=["m-lot-902"], gate=True)
    b.rec(m, "m-ship-950", "shipment", _t(15, 45), "Expédition sous-ensemble ASM-950",
          inputs=["m-asm-950"], gate=True)
    b.send(m, "m-ship-902", d, "d-ship-902", "shipment", _t(15, 45),
           "Expédition reçue LOT-902")
    b.rec(d, "d-gr-902", "goods_receipt", _t(16, 0), "Réception entrepôt LOT-902",
          inputs=["d-ship-902"])
    b.send(m, "m-ship-950", d, "d-ship-950", "shipment", _t(15, 50),
           "Expédition reçue ASM-950")
    b.rec(d, "d-gr-950", "goods_receipt", _t(16, 5), "Réception entrepôt ASM-950",
          inputs=["d-ship-950"])
    b.rec(d, "d-out-950", "shipment", _t(16, 30), "Réexpédition ASM-950 vers client",
          inputs=["d-gr-950"], gate=True)
    b.send(d, "d-out-950", c, "c-ship-950", "shipment", _t(16, 35),
           "Livraison attendue ASM-950")
    b.rec(c, "c-gr-950", "goods_receipt", _t(16, 55), "Réception chantier ASM-950",
          inputs=["c-ship-950"])


def _attack_asn(b: _Builder) -> None:
    """Faux avis d'expédition : la bobine COIL-299 n'existe pas. La réception
    est saisie depuis l'ASN sans contrôle, la production est lancée sur ce
    stock fantôme et la livraison est promise jusqu'au client. Une vraie
    livraison de la fenêtre, contrôlée physiquement, continue."""
    f, m, d, c = b.f, b.m, b.d, b.c
    ship = {"bc": "BC-9999", "part": PART, "qty": 12, "lot_no": "COIL-299",
            "ship_date": _t(14, 10).isoformat()}
    b.rec(f, "f-asn-X", "asn", _t(14, 10), "ASN urgente BC-9999 (bobine COIL-299)",
          payload=ship)
    b.send(f, "f-asn-X", m, "m-asn-X", "asn", _t(14, 15), "ASN reçu — BC-9999",
           payload=ship)
    b.rec(m, "m-gr-X", "goods_receipt", _t(14, 30),
          "Réception COIL-299 saisie depuis l'ASN (sans contrôle)", inputs=["m-asn-X"],
          payload={"lot": "COIL-299", "part": PART, "qty": 12, "bc": "BC-9999"})
    b.rec(m, "m-stock-X", "stock_entry", _t(14, 35), "Entrée en stock COIL-299",
          inputs=["m-gr-X"], payload={"lot": "COIL-299"})
    b.transform(m, "m-lot-X", _t(15, 0), "Lancement lot LOT-999 (COIL-299 + COIL-107)",
                ["m-stock-X", "m-gr-07"], "LOT-999")
    b.rec(m, "m-ship-X", "shipment", _t(15, 30), "Expédition lot LOT-999",
          inputs=["m-lot-X"], gate=True)
    b.send(m, "m-ship-X", d, "d-ship-X", "shipment", _t(15, 35),
           "Expédition annoncée LOT-999")
    b.rec(d, "d-res-X", "reservation", _t(15, 50), "Réservation client sur LOT-999",
          inputs=["d-ship-X"])
    b.rec(d, "d-out-X", "shipment", _t(16, 10), "Réexpédition LOT-999 vers client",
          inputs=["d-res-X"], gate=True)
    b.send(d, "d-out-X", c, "c-ship-X", "shipment", _t(16, 15),
           "Livraison promise LOT-999")
    b.rec(c, "c-plan-X", "work_plan", _t(16, 30), "Planning chantier calé sur LOT-999",
          inputs=["c-ship-X"])

    ship = _legit_ship_08()
    b.rec(f, "f-asn-08", "asn", _t(14, 45), "ASN commande BC-1008 (bobine COIL-108)",
          payload=ship)
    b.send(f, "f-asn-08", m, "m-asn-08", "asn", _t(14, 50), "ASN reçu — BC-1008",
           payload=ship)
    b.rec(m, "m-gr-08", "goods_receipt", _t(15, 10),
          "Réception COIL-108 (contrôle physique)", inputs=["m-asn-08"],
          verified=True, payload=_legit_gr_08())
    b.transform(m, "m-lot-908", _t(15, 40), "Lancement lot LOT-908 (COIL-108)",
                ["m-gr-08"], "LOT-908")


def _attack_none(b: _Builder) -> None:
    """Scénarios qualité : personne n'est compromis, la matinée et l'après-midi
    de base suffisent (COIL-104 -> LOT-504 + LOT-A40, COIL-103 -> LOT-503 + LOT-A30).
    Le paiement m-pay-04 dépend de la facture, pas de la bobine : il reste ok."""


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
        "mixed", "Attaque mixte",
        "Le fournisseur compromis envoie un faux avis d'expédition, un faux "
        "certificat et une facture au RIB modifié.",
        _attack_mixed),
    ScenarioDef(
        "rib", "Fraude au RIB",
        "Un mail de changement de RIB modifie la fiche fournisseur ; la facture "
        "suivante serait payée sur le compte du fraudeur.",
        _attack_rib),
    ScenarioDef(
        "cert", "Faux certificat qualité",
        "Une bobine réelle arrive avec un faux certificat : le lot fabriqué avec "
        "elle, le sous-ensemble qui l'intègre et leurs expéditions sont bloqués.",
        _attack_cert),
    ScenarioDef(
        "asn", "Faux avis d'expédition",
        "Une livraison inexistante est annoncée : réception fantôme, production "
        "lancée sur un stock qui n'existe pas, livraison promise au client.",
        _attack_asn),
    ScenarioDef(
        "lot", "Lot défectueux",
        "Le contrôle réception détecte un défaut de coulée sur la bobine COIL-104 : "
        "on isole ce lot et ce qui en dérive, sans blacklister le fournisseur.",
        _attack_none,
        {"type": "lot", "company": "fabricant", "lot": "COIL-104",
         "reason": "Défaut de coulée signalé par le contrôle réception"}),
    ScenarioDef(
        "recall", "Rappel depuis un produit fini",
        "Casse sur chantier sur LOT-503 : l'analyse remonte à la bobine COIL-103 "
        "et mesure ce qu'un rappel toucherait.",
        _attack_none,
        {"type": "recall", "company": "fabricant", "target": "LOT-503",
         "suspect_lot": "COIL-103",
         "reason": "Casse sur chantier, analyse qualité : bobine en cause"}),
]}


def scenarios_meta() -> list[dict]:
    return [s.meta() for s in SCENARIOS.values()]


def build_simulation(scenario: str = DEFAULT_SCENARIO) -> Simulation:
    definition = SCENARIOS.get(scenario)
    if definition is None:
        raise ValueError(f"scénario inconnu: {scenario}")
    b = _Builder()
    _clean_morning(b)
    definition.attack(b)
    _internal_ops(b)
    _add_fabricant_afternoon(b)
    sim = Simulation(COMPANIES, b.ledgers, b.fed, scenario=definition.meta())
    sim.run()
    return sim
