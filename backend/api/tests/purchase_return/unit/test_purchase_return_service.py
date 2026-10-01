"""Purchase Return accounting and transaction tests using isolated SQLite."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.model.item_master import ItemMaster
from api.model.party import Party
from api.model.purchase_return import PurchaseReturn, PurchaseReturnItem
from api.schema.purchase_return import PurchaseReturnCreate, PurchaseReturnUpdate
from api.services import purchase_return as service


@pytest.fixture
def account(db_session):
    supplier = Party(name="ABC", current_balance=Decimal("200000"),
                     current_balance_type="Credit", opening_balance=Decimal("100"))
    other = Party(name="XYZ", current_balance=Decimal("100000"),
                  current_balance_type="Credit")
    item = ItemMaster(name="Test item", hsn_code="1234", unit="Box", current_stock=100)
    db_session.add_all([supplier, other, item])
    db_session.commit()
    return supplier, other, item


def line(item, price=30000, **changes):
    return dict(item_id=item.id, item_name=item.name, hsn_code=item.hsn_code,
                unit=item.unit, quantity=1, price=price, **changes)


def create(db, supplier, item, price=30000):
    return service.create_purchase_return(db, PurchaseReturnCreate(
        party_id=supplier.id, return_reason="Damaged goods", items=[line(item, price)]
    ))


def balance(db, supplier, amount, kind="Credit"):
    db.refresh(supplier)
    assert supplier.current_balance == Decimal(str(amount))
    assert supplier.current_balance_type == kind


@pytest.mark.parametrize("opening,total,expected,kind", [
    (200000, 30000, 170000, "Credit"),
    (20000, 50000, 30000, "Debit"),
])
def test_create(db_session, account, opening, total, expected, kind):
    supplier, _, item = account
    supplier.current_balance = Decimal(opening)
    db_session.commit()
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        record = create(db_session, supplier, item, total)
        assert commit.call_count == 1
    balance(db_session, supplier, expected, kind)
    db_session.refresh(item)
    assert item.current_stock == 99
    assert record.grand_total == total
    assert supplier.opening_balance == Decimal("100")


@pytest.mark.parametrize("old,new", [(30000, 40000), (40000, 25000), (30000, 30000)])
def test_same_supplier_update(db_session, account, old, new):
    supplier, _, item = account
    record = create(db_session, supplier, item, old)
    with patch.object(service, "apply_party_balance_delta", wraps=service.apply_party_balance_delta) as post:
        with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
            service.update_purchase_return_by_id(db_session, record.id,
                PurchaseReturnUpdate(items=[line(item, new)]))
            assert commit.call_count == 1
        assert post.call_count == (0 if old == new else 1)
        if old != new:
            assert post.call_args.args[2] == Decimal(old - new)
    balance(db_session, supplier, 200000 - new)
    db_session.refresh(item)
    assert item.current_stock == 99


@pytest.mark.parametrize("old,new,inactive", [
    (30000, 40000, False), (80000, 30000, False), (30000, 40000, True),
])
def test_supplier_change(db_session, account, old, new, inactive):
    supplier, other, item = account
    record = create(db_session, supplier, item, old)
    supplier.is_active = not inactive
    db_session.commit()
    service.update_purchase_return_by_id(db_session, record.id,
        PurchaseReturnUpdate(party_id=other.id, items=[line(item, new)]))
    balance(db_session, supplier, 200000)
    balance(db_session, other, 100000 - new)
    assert supplier.is_active is not inactive
    assert record.party_id == other.id


@pytest.mark.parametrize("inactive", [False, True])
def test_delete_restores_balance_and_stock_once(db_session, account, inactive):
    supplier, _, item = account
    record = create(db_session, supplier, item)
    supplier.is_active = not inactive
    db_session.commit()
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        result = service.delete_purchase_return_by_id(db_session, record.id)
        assert commit.call_count == 1
    assert result == {"message": f"Purchase Return '{record.return_no}' deleted successfully."}
    balance(db_session, supplier, 200000)
    db_session.refresh(item)
    assert item.current_stock == 100
    assert record.is_active is False
    assert supplier.is_active is not inactive
    with pytest.raises(HTTPException):
        service.delete_purchase_return_by_id(db_session, record.id)
    balance(db_session, supplier, 200000)
    db_session.refresh(item)
    assert item.current_stock == 100


def test_nonfinancial_update(db_session, account):
    supplier, _, item = account
    record = create(db_session, supplier, item)
    with patch.object(service, "apply_party_balance_delta") as post:
        service.update_purchase_return_by_id(db_session, record.id,
            PurchaseReturnUpdate(remarks="Updated remark", reference="Reference"))
        post.assert_not_called()
    balance(db_session, supplier, 170000)
    assert record.remarks == "Updated remark"


def test_financial_items_use_final_total(db_session, account):
    supplier, _, item = account
    record = create(db_session, supplier, item)
    updated_line = line(item, 10000, disc_percent=10, sgst=9, cgst=9)
    updated_line["quantity"] = 2
    service.update_purchase_return_by_id(db_session, record.id,
        PurchaseReturnUpdate(items=[updated_line]))
    assert record.grand_total == 21240
    balance(db_session, supplier, 178760)
    db_session.refresh(item)
    assert item.current_stock == 98


@pytest.mark.parametrize("operation", ["create", "update"])
def test_stock_failure_does_not_post(db_session, account, operation):
    supplier, _, item = account
    record = create(db_session, supplier, item) if operation == "update" else None
    bad_line = line(item)
    bad_line["quantity"] = 101
    with patch.object(service, "apply_party_balance_delta") as post:
        with pytest.raises(HTTPException):
            if record:
                service.update_purchase_return_by_id(db_session, record.id,
                    PurchaseReturnUpdate(items=[bad_line]))
            else:
                service.create_purchase_return(db_session, PurchaseReturnCreate(
                    party_id=supplier.id, return_reason="Damaged", items=[bad_line]))
        post.assert_not_called()
    balance(db_session, supplier, 170000 if record else 200000)
    db_session.refresh(item)
    assert item.current_stock == (99 if record else 100)
    assert db_session.query(PurchaseReturn).count() == (1 if record else 0)


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("failure", ["posting", "commit"])
def test_failure_rolls_back_everything(db_session, account, operation, failure):
    supplier, other, item = account
    record = create(db_session, supplier, item) if operation != "create" else None
    record_id = record.id if record else None
    old_items = [(r.id, r.quantity, r.price) for r in db_session.query(PurchaseReturnItem).all()]
    original_post = service.apply_party_balance_delta

    def fail_after_flush(*args):
        original_post(*args)
        raise RuntimeError("Injected failure after balance flush")

    target = patch.object(service, "apply_party_balance_delta", side_effect=fail_after_flush) if failure == "posting" else patch.object(db_session, "commit", side_effect=RuntimeError("Commit failed"))
    with target, patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
        with pytest.raises(RuntimeError):
            if operation == "create":
                create(db_session, supplier, item)
            elif operation == "update":
                changed_line = line(item, 20000)
                changed_line["quantity"] = 2
                service.update_purchase_return_by_id(db_session, record_id,
                    PurchaseReturnUpdate(party_id=other.id, items=[changed_line], remarks="Changed"))
            else:
                service.delete_purchase_return_by_id(db_session, record_id)
        rollback.assert_called_once()
    balance(db_session, supplier, 170000 if record else 200000)
    balance(db_session, other, 100000)
    db_session.refresh(item)
    assert item.current_stock == (99 if record else 100)
    assert [(r.id, r.quantity, r.price) for r in db_session.query(PurchaseReturnItem).all()] == old_items
    assert db_session.query(PurchaseReturn).count() == (1 if record else 0)
    if record:
        db_session.refresh(record)
        assert record.party_id == supplier.id
        assert record.grand_total == 30000
        assert record.remarks is None
        assert record.is_active is True
