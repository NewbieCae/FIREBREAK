"""FirebreakRegistry sur une EVM en mémoire (eth-tester) : aucun réseau."""

import pytest

pytest.importorskip("eth_tester")

from web3 import EthereumTesterProvider, Web3  # noqa: E402

from firebreak.chain import ids  # noqa: E402
from firebreak.chain.accounts import TEST_MNEMONIC, derive_accounts  # noqa: E402
from firebreak.chain.artifact import load_artifact  # noqa: E402
from firebreak.chain.config import COMPANIES  # noqa: E402
from firebreak.chain.deployer import (  # noqa: E402
    TransactionFailed,
    ensure_tester_registry,
    register_members,
    send_value,
    transact,
)
from firebreak.federation import Federation  # noqa: E402

RUN = ids.new_run_id()


@pytest.fixture
def chain():
    w3 = Web3(EthereumTesterProvider())
    accounts = derive_accounts(TEST_MNEMONIC)
    pubkeys = Federation(list(COMPANIES)).public_keys
    contract = ensure_tester_registry(w3, accounts, pubkeys)
    # Un compte extérieur financé mais jamais enregistré.
    outsider = w3.eth.account.create()
    send_value(w3, accounts["admin"], outsider.address, w3.to_wei(1, "ether"))
    return w3, contract, accounts, pubkeys, outsider


def _events(contract, receipt, name):
    return getattr(contract.events, name)().process_receipt(receipt)


def test_build_matches_source():
    from firebreak.chain.artifact import source_sha256

    assert load_artifact()["sourceSha256"] == source_sha256(), \
        "contracts/build périmé : relancer scripts/chain_compile.py"
    assert load_artifact()["evmVersion"] == "paris"


def test_members_registered_with_pubkeys(chain):
    w3, contract, accounts, pubkeys, _ = chain
    assert contract.functions.admin().call() == accounts["admin"].address
    for cid in COMPANIES:
        company, pubkey, active = contract.functions.members(accounts[cid].address).call()
        assert company == ids.company_id(cid) and pubkey == pubkeys[cid] and active
        assert contract.functions.accountOf(ids.company_id(cid)).call() == accounts[cid].address
        assert contract.functions.pubKeyOf(ids.company_id(cid)).call() == pubkeys[cid]
    # Relancer l'enregistrement n'envoie aucune transaction.
    assert register_members(w3, contract, accounts["admin"], accounts, pubkeys) == []


def test_only_admin_registers(chain):
    w3, contract, accounts, _, outsider = chain
    with pytest.raises(Exception):
        transact(w3, accounts["fabricant"],
                 contract.functions.registerMember(outsider.address, ids.company_id("intrus"), b"\x01" * 32))


def test_company_cannot_be_hijacked(chain):
    w3, contract, accounts, _, outsider = chain
    with pytest.raises(Exception):
        transact(w3, accounts["admin"],
                 contract.functions.registerMember(outsider.address, ids.company_id("fournisseur"), b"\x01" * 32))


def test_outsider_cannot_declare_or_anchor(chain):
    w3, contract, _, _, outsider = chain
    calls = [
        contract.functions.declareIncident(RUN, ids.company_id("fournisseur"), 1, b"\x02" * 32),
        contract.functions.anchorAlert(RUN, b"\x03" * 32, ids.company_id("fabricant"), 0),
        contract.functions.anchorAudit(RUN, b"\x04" * 32, 3),
    ]
    for call in calls:
        with pytest.raises(Exception):
            transact(w3, outsider, call)


def test_declare_and_withdraw_incident_events(chain):
    w3, contract, accounts, _, _ = chain
    dh = ids.declaration_hash("fournisseur", "2026-10-11T14:00:00", "fabricant")
    r = transact(w3, accounts["fabricant"],
                 contract.functions.declareIncident(RUN, ids.company_id("fournisseur"), 1_791_640_800, dh))
    (ev,) = _events(contract, r, "IncidentDeclared")
    assert ev.args.declarer == ids.company_id("fabricant")
    assert ev.args.sourceCompany == ids.company_id("fournisseur")
    assert ev.args.declarationHash == dh and ev.args.since == 1_791_640_800
    r = transact(w3, accounts["fabricant"],
                 contract.functions.withdrawIncident(RUN, ids.company_id("fournisseur"), dh))
    assert len(_events(contract, r, "IncidentWithdrawn")) == 1


def test_alert_anchor_and_acknowledge(chain):
    w3, contract, accounts, _, _ = chain
    h = b"\x05" * 32
    to = ids.company_id("fabricant")
    r = transact(w3, accounts["fournisseur"], contract.functions.anchorAlert(RUN, h, to, 0))
    (ev,) = _events(contract, r, "AlertAnchored")
    assert ev.args.fromCompany == ids.company_id("fournisseur") and ev.args.toCompany == to
    frm, to_, kind, anchored_at, ack_at = contract.functions.alerts(h).call()
    assert kind == 0 and anchored_at > 0 and ack_at == 0
    with pytest.raises(Exception):  # même empreinte deux fois
        transact(w3, accounts["fournisseur"], contract.functions.anchorAlert(RUN, h, to, 0))
    with pytest.raises(Exception):  # seul le destinataire acquitte
        transact(w3, accounts["distributeur"], contract.functions.acknowledgeAlert(h))
    r = transact(w3, accounts["fabricant"], contract.functions.acknowledgeAlert(h))
    assert len(_events(contract, r, "AlertAcknowledged")) == 1
    assert contract.functions.alerts(h).call()[4] > 0
    with pytest.raises(Exception):  # double acquittement
        transact(w3, accounts["fabricant"], contract.functions.acknowledgeAlert(h))


def test_alert_type_and_unknown_ack_rejected(chain):
    w3, contract, accounts, _, _ = chain
    with pytest.raises(Exception):
        transact(w3, accounts["fournisseur"],
                 contract.functions.anchorAlert(RUN, b"\x06" * 32, ids.company_id("fabricant"), 2))
    with pytest.raises(Exception):
        transact(w3, accounts["fabricant"], contract.functions.acknowledgeAlert(b"\x07" * 32))


def test_audit_anchor_never_shrinks_within_a_run(chain):
    w3, contract, accounts, _, _ = chain
    me = ids.company_id("fabricant")
    transact(w3, accounts["fabricant"], contract.functions.anchorAudit(RUN, b"\x08" * 32, 5))
    head, entries, at = contract.functions.latestAudit(RUN, me).call()
    assert head == b"\x08" * 32 and entries == 5 and at > 0
    transact(w3, accounts["fabricant"], contract.functions.anchorAudit(RUN, b"\x09" * 32, 7))
    assert contract.functions.latestAudit(RUN, me).call()[1] == 7
    with pytest.raises(Exception):
        transact(w3, accounts["fabricant"], contract.functions.anchorAudit(RUN, b"\x0a" * 32, 6))
    other_run = ids.new_run_id()  # nouvelle partie de démo : repart de zéro
    transact(w3, accounts["fabricant"], contract.functions.anchorAudit(other_run, b"\x0b" * 32, 1))
    assert contract.functions.latestAudit(other_run, me).call()[1] == 1


def test_deactivated_member_cannot_write(chain):
    w3, contract, accounts, _, _ = chain
    transact(w3, accounts["admin"], contract.functions.deactivateMember(accounts["client"].address))
    with pytest.raises(Exception):
        transact(w3, accounts["client"], contract.functions.anchorAudit(RUN, b"\x0c" * 32, 1))


def test_revert_raises_transaction_failed_or_contract_error(chain):
    w3, contract, accounts, _, outsider = chain
    with pytest.raises((TransactionFailed, Exception)):
        transact(w3, outsider, contract.functions.anchorAudit(RUN, b"\x0d" * 32, 1))
