from datetime import datetime

from firebreak.engine import Ledger
from firebreak.genealogy import lot_genealogy, transformation_payload
from firebreak.model import Record
from firebreak.scenario import COMPROMISED_SINCE, build_simulation

T = datetime(2026, 10, 10, 15, 0)


def _ledger():
    led = Ledger("fab")

    def add(rid, inputs=(), lot=None, origin="fab", payload=None):
        led.add(Record(id=rid, company="fab", origin=origin, kind="x", ts=T, label=rid,
                       inputs=list(inputs), payload=payload or ({"lot": lot} if lot else {})))

    add("coil-a", lot="COIL-A", origin="evil")
    add("coil-b", lot="COIL-B")
    add("coil-c", lot="COIL-C")
    consumed = [led.records["coil-a"], led.records["coil-b"]]
    add("lot-1", ["coil-a", "coil-b"], payload=transformation_payload(consumed, "LOT-1"))
    add("lot-2", ["coil-b", "coil-c"], payload=transformation_payload(
        [led.records["coil-b"], led.records["coil-c"]], "LOT-2"))
    add("asm-1", ["lot-1", "lot-2"], payload=transformation_payload(
        [led.records["lot-1"], led.records["lot-2"]], "ASM-1"))
    add("asm-2", ["lot-2"], payload=transformation_payload([led.records["lot-2"]], "ASM-2"))
    return led


def test_contaminated_lot_contaminates_lots_made_with_it():
    led = _ledger()
    led.declare_compromised("evil", T.replace(hour=0))
    led.recompute()
    status = {rid: r.status for rid, r in led.records.items()}
    assert status == {
        "coil-a": "quarantined", "coil-b": "ok", "coil-c": "ok",
        "lot-1": "quarantined", "lot-2": "ok",
        "asm-1": "quarantined", "asm-2": "ok",
    }
    assert led.records["asm-1"].taint_path == ["coil-a", "lot-1", "asm-1"]


def test_transformation_payload_lists_consumed_lots():
    led = _ledger()
    assert led.records["lot-1"].payload == {"lot": "LOT-1", "input_lots": ["COIL-A", "COIL-B"]}


def test_lot_genealogy_up_and_down():
    g = lot_genealogy(_ledger(), "COIL-B")
    assert g["ancestors"] == []
    assert g["descendants"] == ["ASM-1", "ASM-2", "LOT-1", "LOT-2"]
    g = lot_genealogy(_ledger(), "ASM-1")
    assert g["ancestors"] == ["COIL-A", "COIL-B", "COIL-C", "LOT-1", "LOT-2"]


def test_scenario_cert_genealogy():
    sim = build_simulation("cert")
    fab = sim.ledgers["fabricant"]
    assert lot_genealogy(fab, "COIL-210")["descendants"] == ["ASM-950", "LOT-901"]
    assert fab.records["m-asm-950"].payload["input_lots"] == ["LOT-901", "LOT-902"]
    sim.declare_compromise("fournisseur", COMPROMISED_SINCE)
    assert fab.records["m-lot-901"].status == "quarantined"
    assert fab.records["m-lot-902"].status == "ok"
