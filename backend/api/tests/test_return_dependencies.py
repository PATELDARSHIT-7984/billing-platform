"""Original documents must preserve the relationships of active linked returns."""
import pytest
from fastapi import HTTPException

from api.tests.purchase_return.integration.test_integrity import data as purchase_data
from api.tests.purchase_return.integration import test_integrity as pr
from api.tests.sales_return.integration.test_integrity import data as sale_data
from api.tests.sales_return.integration import test_integrity as sr
from api.schema.purchase import PurchaseUpdate
from api.schema.bill import BillUpdate
from api.services import purchase, bill


@pytest.fixture(params=['purchase', 'sale'])
def context(request, db_session):
    kind = request.param
    data = request.getfixturevalue(kind + '_data')
    return kind, data, pr if kind == 'purchase' else sr


def update(db, context, rows=None, **changes):
    kind, data, helpers = context
    original = data[2]
    if kind == 'purchase':
        payload = changes | (dict(items=rows) if rows is not None else {})
        return purchase.update_purchase_by_id(db, original.id, PurchaseUpdate(**payload))
    payload = dict(customer_id=data[0][0].id, bill_date=original.bill_date,
                   items=rows if rows is not None else [helpers.line(data[1][0], 10), helpers.line(data[1][1], 8)]) | changes
    payload['items'] = [row | dict(rate=row.get('price', 100), disc_percent=0, cgst=0, sgst=0, igst=0)
                        for row in payload['items']]
    return bill.update_bill(db, original.bill_id, BillUpdate(**payload))


@pytest.mark.parametrize('quantity,allowed', [(8, True), (4, True), (3, False), (15, True)])
def test_quantity_floor(db_session, context, quantity, allowed):
    _, data, helpers = context
    helpers.create(db_session, data, 4)
    before = helpers.snapshot(db_session)
    rows = [helpers.line(data[1][0], quantity), helpers.line(data[1][1], 8)]
    if allowed:
        old_stock = data[1][0].current_stock
        update(db_session, context, rows)
        assert data[1][0].current_stock == old_stock + (quantity - 10) * (1 if context[0] == 'purchase' else -1)
    else:
        with pytest.raises(HTTPException, match='already been returned'):
            update(db_session, context, rows, remarks='Must not persist')
        db_session.commit(); assert helpers.snapshot(db_session) == before


@pytest.mark.parametrize('mode', ['remove', 'replace', 'duplicates', 'multiple', 'multi_item', 'owner'])
def test_invalid_dependency_is_atomic(db_session, context, mode):
    kind, data, helpers = context
    items = data[1]
    helpers.create(db_session, data, 4)
    if mode == 'multiple': helpers.create(db_session, data, 3)
    if mode == 'multi_item': helpers.create(db_session, data, items=[helpers.line(items[1], 7)])
    rows = [helpers.line(items[0], 10), helpers.line(items[1], 8)]
    if mode == 'remove': rows = [helpers.line(items[1], 8)]
    if mode == 'replace': rows = [helpers.line(items[2], 10), helpers.line(items[1], 8)]
    if mode == 'duplicates': rows = [helpers.line(items[0], 1), helpers.line(items[0], 2)]
    if mode == 'multiple': rows = [helpers.line(items[0], 6)]
    if mode == 'multi_item': rows = [helpers.line(items[0], 8), helpers.line(items[1], 5)]
    changes = {('party_id' if kind == 'purchase' else 'customer_id'): data[0][1].id} if mode == 'owner' else {}
    before = helpers.snapshot(db_session)
    with pytest.raises(HTTPException): update(db_session, context, rows, **changes)
    db_session.commit(); assert helpers.snapshot(db_session) == before


@pytest.mark.parametrize('mode', ['deleted', 'standalone', 'financial', 'text', 'duplicates_valid'])
def test_harmless_updates_remain_allowed(db_session, context, mode):
    kind, data, helpers = context
    reference = 'original_bill_no' if kind == 'purchase' else 'original_invoice_no'
    record = helpers.create(db_session, data, 4, **({reference: None} if mode == 'standalone' else {}))
    if mode == 'deleted':
        if kind == 'purchase': helpers.service.delete_purchase_return_by_id(db_session, record.id)
        else: helpers.service.delete_sales_return_by_id(db_session, record.id)
    rows = None
    if mode in ['deleted', 'standalone']: rows = [helpers.line(data[1][0], 3)]
    if mode == 'financial': rows = [helpers.line(data[1][0], 10, price=110), helpers.line(data[1][1], 8)]
    if mode == 'duplicates_valid': rows = [helpers.line(data[1][0], 2), helpers.line(data[1][0], 2), helpers.line(data[1][1], 8)]
    stocks = [item.current_stock for item in data[1]]
    update(db_session, context, rows, remarks='Allowed')
    if mode in ['financial', 'text']: assert [item.current_stock for item in data[1]] == stocks


def test_stock_validation_still_applies(db_session, context):
    kind, data, helpers = context
    helpers.create(db_session, data, 4)
    data[1][0].current_stock = 2; db_session.commit()
    before = helpers.snapshot(db_session)
    quantity = 5 if kind == 'purchase' else 15
    with pytest.raises(HTTPException): update(db_session, context, [helpers.line(data[1][0], quantity)])
    db_session.commit(); assert helpers.snapshot(db_session) == before


def test_purchase_number_change_rejected(db_session, purchase_data):
    pr.create(db_session, purchase_data, 4)
    before = pr.snapshot(db_session)
    with pytest.raises(HTTPException):
        purchase.update_purchase_by_id(db_session, purchase_data[2].id, PurchaseUpdate(bill_no='PUR-NEW'))
    db_session.commit(); assert pr.snapshot(db_session) == before


def test_fractional_returns_are_not_truncated(db_session, context):
    kind, data, helpers = context
    record = helpers.create(db_session, data, 3.5)
    reference = 'original_bill_no' if kind == 'purchase' else 'original_invoice_no'
    setattr(record, reference, ' pur-001 ' if kind == 'purchase' else ' inv-001 ')
    db_session.commit(); before = helpers.snapshot(db_session)
    with pytest.raises(HTTPException, match='3.5 units'):
        update(db_session, context, [helpers.line(data[1][0], 3)])
    db_session.commit(); assert helpers.snapshot(db_session) == before


@pytest.mark.parametrize('standalone', [True, False])
def test_unlinked_or_deleted_returns_allow_owner_change(db_session, context, standalone):
    kind, data, helpers = context
    reference = 'original_bill_no' if kind == 'purchase' else 'original_invoice_no'
    record = helpers.create(db_session, data, **({reference: None} if standalone else {}))
    if not standalone:
        if kind == 'purchase': helpers.service.delete_purchase_return_by_id(db_session, record.id)
        else: helpers.service.delete_sales_return_by_id(db_session, record.id)
    field = 'party_id' if kind == 'purchase' else 'customer_id'
    changes = {field: data[0][1].id}
    if kind == 'purchase': changes['bill_no'] = 'PUR-NEW'
    update(db_session, context, **changes)
    assert getattr(data[2], field) == data[0][1].id
    if kind == 'purchase': assert data[2].bill_no == 'PUR-NEW'


def test_new_item_creation_rolls_back_on_dependency_failure(db_session, purchase_data):
    pr.create(db_session, purchase_data, 4)
    before = pr.snapshot(db_session)
    rows = [pr.line(purchase_data[1][0], 3),
            dict(item_name='New item', hsn_code='1234', unit='units', quantity=2, price=100)]
    with pytest.raises(HTTPException):
        purchase.update_purchase_by_id(db_session, purchase_data[2].id, PurchaseUpdate(items=rows))
    db_session.commit(); assert pr.snapshot(db_session) == before


@pytest.mark.parametrize('mode', ['active', 'deleted', 'standalone'])
def test_sale_delete_dependency(db_session, sale_data, mode):
    record = sr.create(db_session, sale_data, 4, original_invoice_no=None if mode == 'standalone' else 'INV-001')
    if mode == 'deleted': sr.service.delete_sales_return_by_id(db_session, record.id)
    before = sr.snapshot(db_session)
    original = sale_data[2]
    stocks = [item.current_stock for item in sale_data[1]]
    if mode == 'active':
        with pytest.raises(HTTPException, match='active Sales Returns'): bill.delete_bill(db_session, original.bill_id)
        db_session.commit(); assert sr.snapshot(db_session) == before
    else:
        bill.delete_bill(db_session, original.bill_id)
        assert not original.is_active
        assert [item.current_stock for item in sale_data[1]] == [stocks[0] + 10, stocks[1] + 8, stocks[2]]
        after = sr.snapshot(db_session)
        with pytest.raises(HTTPException): bill.delete_bill(db_session, original.bill_id)
        db_session.commit(); assert sr.snapshot(db_session) == after
