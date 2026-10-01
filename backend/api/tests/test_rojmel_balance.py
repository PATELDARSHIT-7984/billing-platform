"""Supplier-payment accounting using isolated SQLite and real repositories."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.party import Party
from api.model.rojmel import Rojmel
from api.schema.rojmel import RojmelCreate, RojmelUpdate
from api.services import rojmel as service


@pytest.fixture
def accounts(db_session):
    rows = [Party(name=name, party_type=kind, current_balance=Decimal("100000"),
                  current_balance_type="Credit", opening_balance=Decimal("123"))
            for name, kind in [("ABC", "Supplier"), ("XYZ", "Supplier"), ("Buyer", "Customer")]]
    bank, person = BankModel(name="Cash"), DoneByModel(name="Operator")
    db_session.add_all([*rows, bank, person])
    db_session.commit()
    return rows, bank, person


def create(db, accounts, **changes):
    rows, bank, person = accounts
    payload = dict(transaction_type="Dr Pay", party_id=rows[0].id, amount="25000",
                   receipt_no="ignored", given_taken_date=date.today(), effective_date=date.today(),
                   cash_bank_id=bank.id, done_by_id=person.id, pay_mode="Cash")
    payload.update(changes)
    return service.create_rojmel(db, RojmelCreate(**payload))


def assert_balance(db, party, amount, kind="Credit"):
    db.refresh(party)
    assert party.current_balance == Decimal(str(amount))
    assert party.current_balance_type == kind
    assert party.opening_balance == Decimal("123")
    assert party.balance_type == "Credit"


@pytest.mark.parametrize("opening,amount,expected,kind", [
    (100000, 25000, 75000, "Credit"), (20000, 50000, 30000, "Debit"),
])
def test_create_payment(db_session, accounts, opening, amount, expected, kind):
    supplier = accounts[0][0]
    supplier.current_balance = Decimal(opening)
    db_session.commit()
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        create(db_session, accounts, amount=amount)
        commit.assert_called_once()
    assert_balance(db_session, supplier, expected, kind)


@pytest.mark.parametrize("old,new", [(10000, 15000), (15000, 8000), (10000, 10000)])
def test_same_supplier_delta(db_session, accounts, old, new):
    record = create(db_session, accounts, amount=old)
    with patch.object(service, "apply_party_balance_delta", wraps=service.apply_party_balance_delta) as post:
        with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
            service.update_rojmel(db_session, record.id, RojmelUpdate(amount=new))
            commit.assert_called_once()
        assert post.call_count == (old != new)
        if old != new:
            assert post.call_args.args[2] == Decimal(old - new)
    assert_balance(db_session, accounts[0][0], 100000 - new)


@pytest.mark.parametrize("inactive", [False, True])
def test_supplier_change(db_session, accounts, inactive):
    old, new, _ = accounts[0]
    record = create(db_session, accounts, amount=10000)
    old.is_active = not inactive
    db_session.commit()
    service.update_rojmel(db_session, record.id, RojmelUpdate(party_id=new.id, amount=15000))
    assert_balance(db_session, old, 100000)
    assert_balance(db_session, new, 85000)
    assert old.is_active == (not inactive)


@pytest.mark.parametrize("inactive", [False, True])
def test_delete_payment(db_session, accounts, inactive):
    record = create(db_session, accounts)
    record_id = record.id
    supplier = accounts[0][0]
    supplier.is_active = not inactive
    db_session.commit()
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        service.delete_rojmel(db_session, record_id)
        commit.assert_called_once()
    assert_balance(db_session, supplier, 100000)
    assert db_session.get(Rojmel, record_id) is None
    with pytest.raises(HTTPException):
        service.delete_rojmel(db_session, record_id)
    assert_balance(db_session, supplier, 100000)


@pytest.mark.parametrize("kind,party", [
    ("Cr Pay", 0), ("Cash/Bank", 0), ("JV", 0), ("Dr Pay", None), ("Dr Pay", 2),
])
def test_non_supplier_create_update_delete(db_session, accounts, kind, party):
    party_id = accounts[0][party].id if party is not None else None
    with patch.object(service, "apply_party_balance_delta") as post:
        record = create(db_session, accounts, transaction_type=kind, party_id=party_id,
                        payment_for="Supplier payment")
        service.update_rojmel(db_session, record.id, RojmelUpdate(amount=12000))
        service.delete_rojmel(db_session, record.id)
        post.assert_not_called()
    for supplier in accounts[0]:
        assert_balance(db_session, supplier, 100000)


@pytest.mark.parametrize("transition", ["clear", "receipt", "customer"])
def test_payment_to_non_supplier(db_session, accounts, transition):
    record = create(db_session, accounts, amount=10000)
    changes = {"clear": {"party_id": None}, "receipt": {"transaction_type": "Cr Pay"},
               "customer": {"party_id": accounts[0][2].id}}[transition]
    service.update_rojmel(db_session, record.id, RojmelUpdate(**changes))
    assert_balance(db_session, accounts[0][0], 100000)
    assert_balance(db_session, accounts[0][2], 100000)


@pytest.mark.parametrize("kind,party", [("Dr Pay", None), ("Cr Pay", 0), ("Dr Pay", 2)])
def test_non_supplier_to_payment(db_session, accounts, kind, party):
    record = create(db_session, accounts, transaction_type=kind,
                    party_id=accounts[0][party].id if party is not None else None)
    service.update_rojmel(db_session, record.id, RojmelUpdate(
        transaction_type="Dr Pay", party_id=accounts[0][0].id, amount=12000))
    assert_balance(db_session, accounts[0][0], 88000)


def test_net_override_and_metadata(db_session, accounts):
    record = create(db_session, accounts, amount=100, sgst_percent=9, cgst_percent=9, net_amount=99999)
    assert record.net_amount == Decimal("118")
    assert_balance(db_session, accounts[0][0], 99882)
    with patch.object(service, "apply_party_balance_delta") as post:
        service.update_rojmel(db_session, record.id, RojmelUpdate(
            net_amount=99999, remarks="Changed", payment_for="Free text", effective_date=date(2026, 9, 12)))
        post.assert_not_called()
    assert record.net_amount == Decimal("118")
    service.update_rojmel(db_session, record.id, RojmelUpdate(amount=200, net_amount=1))
    assert record.net_amount == Decimal("236")
    assert_balance(db_session, accounts[0][0], 99764)


@pytest.mark.parametrize("mode", ["create", "reassign", "transition"])
def test_new_inactive_assignment_rejected(db_session, accounts, mode):
    supplier, other, _ = accounts[0]
    record = None if mode == "create" else create(db_session, accounts,
        transaction_type="Cr Pay" if mode == "transition" else "Dr Pay")
    target = other if mode == "reassign" else supplier
    target.is_active = False
    db_session.commit()
    with patch.object(service, "apply_party_balance_delta") as post:
        with pytest.raises(HTTPException) as error:
            if mode == "create":
                create(db_session, accounts)
            else:
                service.update_rojmel(db_session, record.id, RojmelUpdate(
                    transaction_type="Dr Pay", party_id=target.id))
        assert error.value.status_code == 400
        post.assert_not_called()
    assert_balance(db_session, supplier, 75000 if mode == "reassign" else 100000)
    assert_balance(db_session, other, 100000)


def test_existing_inactive_assignment_metadata_allowed(db_session, accounts):
    record = create(db_session, accounts)
    supplier = accounts[0][0]
    supplier.is_active = False
    db_session.commit()
    with patch.object(service, "apply_party_balance_delta") as post:
        service.update_rojmel(db_session, record.id, RojmelUpdate(remarks="Historical"))
        post.assert_not_called()
    assert_balance(db_session, supplier, 75000)


@pytest.mark.parametrize("changes", [{"party_id": 999999}, {"cash_bank_id": 999999},
                                     {"sgst_percent": 9, "igst_percent": 18}])
def test_validation_failure(db_session, accounts, changes):
    with patch.object(service, "apply_party_balance_delta") as post:
        with pytest.raises(HTTPException):
            create(db_session, accounts, **changes)
        post.assert_not_called()
    assert db_session.query(Rojmel).count() == 0
    assert_balance(db_session, accounts[0][0], 100000)


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("failure", ["post", "commit"])
def test_atomic_rollback(db_session, accounts, operation, failure):
    record = None if operation == "create" else create(db_session, accounts, amount=10000)
    record_id = record.id if record else None
    original = service.apply_party_balance_delta

    def fail_after_flush(*args):
        original(*args)
        raise RuntimeError("After flush")

    failure_patch = patch.object(service, "apply_party_balance_delta", side_effect=fail_after_flush) if failure == "post" else patch.object(db_session, "commit", side_effect=RuntimeError("Before commit"))
    with failure_patch, patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
        with pytest.raises(RuntimeError):
            if operation == "create":
                create(db_session, accounts)
            elif operation == "update":
                service.update_rojmel(db_session, record_id, RojmelUpdate(
                    party_id=accounts[0][1].id, amount=15000, remarks="Changed"))
            else:
                service.delete_rojmel(db_session, record_id)
        rollback.assert_called_once()
    assert_balance(db_session, accounts[0][0], 90000 if record else 100000)
    assert_balance(db_session, accounts[0][1], 100000)
    assert db_session.query(Rojmel).count() == (1 if record else 0)
    if record:
        stored = db_session.get(Rojmel, record_id)
        assert stored.party_id == accounts[0][0].id
        assert stored.amount == stored.net_amount == Decimal("10000")
        assert stored.remarks is None


def test_http_contract_and_net_override(test_app, client, db_session, accounts):
    from api.router.rojmel import router

    test_app.include_router(router)
    suppliers, bank, person = accounts
    payload = dict(transaction_type="Dr Pay", party_id=suppliers[0].id,
                   amount="100.00", sgst_percent="9.00", cgst_percent="9.00",
                   net_amount="99999.00", receipt_no="placeholder",
                   given_taken_date="2026-09-12", effective_date="2026-09-12",
                   cash_bank_id=bank.id, done_by_id=person.id, pay_mode="Cash")
    response = client.post("/rojmel/", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Rojmel receipt created successfully"
    assert Decimal(str(body["data"]["net_amount"])) == Decimal("118")
    record_id = body["data"]["id"]
    response = client.patch(f"/rojmel/{record_id}", json={"net_amount": "1.00"})
    assert response.status_code == 200
    assert Decimal(str(response.json()["data"]["net_amount"])) == Decimal("118")
    assert_balance(db_session, suppliers[0], 99882)
    response = client.delete(f"/rojmel/{record_id}")
    assert response.status_code == 200
    assert response.json()["data"] is None
    assert_balance(db_session, suppliers[0], 100000)
