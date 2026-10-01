"""Sales Return stock reversals, invoice caps and atomic transactions."""
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.customer import Customer
from api.model.item_master import ItemMaster
from api.model.sales_return import SalesReturn, SalesReturnItem
from api.router.sales_return import router
from api.schema.bill import BillCreate
from api.schema.sales_return import SalesReturnCreate, SalesReturnUpdate, SalesReturnItemCreate
from api.services.bill import create_bill
from api.services import sales_return as service


@pytest.fixture
def data(db_session, test_app):
    test_app.include_router(router)
    customers = [Customer(customer_name=name, mobile=mobile, address='Road', city='Surat', state='Gujarat')
                 for name, mobile in [('Buyer', '9876543210'), ('Other', '9876543211')]]
    items = [ItemMaster(name=name, hsn_code='1234', unit='units', current_stock=50, sale_price=100)
             for name in ['LED Bulb', 'Item B', 'Item C']]
    db_session.add_all([*customers, *items]); db_session.commit()
    bill = create_bill(db_session, BillCreate(customer_id=customers[0].id, bill_date=date(2026, 9, 17),
        items=[dict(item_id=items[0].id, quantity=5), dict(item_id=items[0].id, quantity=5),
               dict(item_id=items[1].id, quantity=8)]))
    bill.invoice_no = 'INV-001'; db_session.commit()
    return customers, items, bill


def line(item, quantity, **changes):
    return dict(item_id=item.id, item_name=item.name, hsn_code='1234', unit='units', quantity=quantity, price=100) | changes


def create(db, data, quantity=4, **changes):
    payload = dict(customer_id=data[0][0].id, original_invoice_no='INV-001', return_reason='Damaged',
                   items=[line(data[1][0], quantity)]) | changes
    return service.create_sales_return(db, SalesReturnCreate(**payload))


def snapshot(db):
    db.flush()
    return {model.__tablename__: [tuple(getattr(row, col.name) for col in model.__table__.columns)
            for row in db.query(model).order_by(list(model.__table__.primary_key.columns)[0]).all()]
            for model in (SalesReturn, SalesReturnItem, ItemMaster, Customer, Bill, BillItem)}


@pytest.mark.parametrize('quantity,reference,allowed', [(3, None, True), (3, 'INV-001', True),
    (10, 'INV-001', True), (11, 'INV-001', False), (1, 'MISSING', False)])
def test_create_stock_and_invoice_limits(db_session, data, quantity, reference, allowed):
    item = data[1][0]; item.current_stock = 5; db_session.commit(); before = snapshot(db_session)
    if allowed:
        create(db_session, data, quantity, original_invoice_no=reference)
        assert item.current_stock == 5 + quantity
    else:
        with pytest.raises(HTTPException): create(db_session, data, quantity, original_invoice_no=reference)
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('failure', ['customer', 'absent_item', 'inactive_bill', 'inactive_line', 'multi_line'])
def test_invalid_invoice_context_changes_nothing(db_session, data, failure):
    customers, items, bill = data
    changes = {}
    if failure == 'customer': changes['customer_id'] = customers[1].id
    if failure == 'absent_item': changes['items'] = [line(items[2], 1)]
    if failure == 'inactive_bill': bill.is_active = False
    if failure == 'inactive_line':
        for row in bill.bill_items:
            if row.item_id == items[0].id: row.is_active = False
    if failure == 'multi_line': changes['items'] = [line(items[0], 3), line(items[1], 9)]
    db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException): create(db_session, data, **changes)
    db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('second,allowed', [(6, True), (7, False)])
def test_previous_active_returns_reduce_capacity(db_session, data, second, allowed):
    record = create(db_session, data, 4)
    record.original_invoice_no = ' inv-001 '; db_session.commit(); before = snapshot(db_session)
    if allowed: create(db_session, data, second)
    else:
        with pytest.raises(HTTPException) as error: create(db_session, data, second)
        assert 'Previously returned: 4' in error.value.detail
        assert 'Remaining returnable quantity: 6' in error.value.detail
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('quantities,allowed', [([4, 6], True), ([4, 7], False)])
def test_duplicate_invoice_and_return_quantities(db_session, data, quantities, allowed):
    before = snapshot(db_session)
    rows = [line(data[1][0], qty) for qty in quantities]
    if allowed:
        create(db_session, data, items=rows)
        assert data[1][0].current_stock == 50
    else:
        with pytest.raises(HTTPException): create(db_session, data, items=rows)
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('other,old,new,stock,expected', [(0, 4, 7, 0, 3), (4, 2, 6, 0, 4),
    (4, 2, 7, 50, None), (0, 7, 4, 3, 0), (0, 7, 4, 2, None), (0, 4, 4, 0, 0)])
def test_update_self_exclusion_and_stock_difference(db_session, data, other, old, new, stock, expected):
    if other: create(db_session, data, other)
    record = create(db_session, data, old)
    item = data[1][0]; item.current_stock = stock; db_session.commit(); before = snapshot(db_session)
    update = SalesReturnUpdate(items=[line(item, new)], remarks='Edited')
    if expected is None:
        with pytest.raises(HTTPException): service.update_sales_return_by_id(db_session, record.id, update)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_sales_return_by_id(db_session, record.id, update)
        assert item.current_stock == expected


@pytest.mark.parametrize('mode', ['replace', 'replace_stock', 'replace_absent', 'replace_cap', 'add', 'add_absent', 'remove', 'remove_stock', 'mixed'])
def test_line_changes_validate_before_mutating(db_session, data, mode):
    items = data[1]
    record = create(db_session, data, items=[line(items[0], 5), line(items[1], 3)])
    if mode in ['replace_stock', 'remove_stock', 'mixed']: items[0].current_stock = 1
    db_session.commit(); before = snapshot(db_session)
    rows = {
        'replace': [line(items[1], 5)], 'replace_stock': [line(items[1], 5)],
        'replace_absent': [line(items[2], 5)], 'replace_cap': [line(items[1], 9)],
        'add': [line(items[0], 5), line(items[1], 3), line(items[1], 2)],
        'add_absent': [line(items[0], 5), line(items[1], 3), line(items[2], 2)],
        'remove': [line(items[1], 3)], 'remove_stock': [line(items[1], 3)],
        'mixed': [line(items[1], 4)],
    }[mode]
    if mode not in ['replace', 'add', 'remove']:
        with pytest.raises(HTTPException):
            service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=rows, remarks='Rejected', reference='Changed'))
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=rows))
        assert [item.current_stock for item in items] == {'replace': [40, 47, 50], 'add': [45, 47, 50], 'remove': [40, 45, 50]}[mode]


@pytest.mark.parametrize('mode', ['wrong_customer', 'missing', 'too_small', 'valid', 'clear'])
def test_header_only_reference_changes_revalidate_items(db_session, data, mode):
    record = create(db_session, data)
    customers, items, _ = data
    bill = create_bill(db_session, BillCreate(customer_id=customers[1].id, bill_date=date(2026, 9, 17),
        items=[dict(item_id=items[0].id, quantity=3 if mode == 'too_small' else 8)]))
    bill.invoice_no = 'INV-002'; db_session.commit(); before = snapshot(db_session)
    changes = dict(original_invoice_no='INV-002', customer_id=customers[1].id)
    if mode == 'wrong_customer': changes = dict(customer_id=customers[1].id)
    if mode == 'missing': changes = dict(original_invoice_no='MISSING')
    if mode == 'clear': changes = dict(original_invoice_no=None)
    if mode in ['valid', 'clear']:
        stock = items[0].current_stock
        service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(**changes))
        assert items[0].current_stock == stock
        create(db_session, data, 10)  # Capacity freed on original invoice.
    else:
        with pytest.raises(HTTPException): service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(**changes))
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('changes', [dict(price=110), dict(disc_percent=10), dict(sgst=9, cgst=9)])
def test_financial_only_stock_unchanged(db_session, data, changes):
    record = create(db_session, data)
    item = data[1][0]; item.current_stock = 0; db_session.commit()
    service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=[line(item, 4, **changes)]))
    assert item.current_stock == 0
    assert record.grand_total == (440 if 'price' in changes else 360 if 'disc_percent' in changes else 472)


@pytest.mark.parametrize('stock,allowed', [(4, True), (3, False)])
def test_delete_checks_reversal_and_frees_capacity(db_session, data, stock, allowed):
    record = create(db_session, data)
    item = data[1][0]; item.current_stock = stock; item.is_active = False
    db_session.commit(); before = snapshot(db_session)
    if allowed:
        service.delete_sales_return_by_id(db_session, record.id)
        assert item.current_stock == 0 and not record.is_active
        with pytest.raises(HTTPException): service.delete_sales_return_by_id(db_session, record.id)
        assert item.current_stock == 0
        create(db_session, data, 10)
        assert item.current_stock == 10
    else:
        with pytest.raises(HTTPException): service.delete_sales_return_by_id(db_session, record.id)
        db_session.commit(); assert snapshot(db_session) == before


def test_inactive_item_update_supported(db_session, data):
    record = create(db_session, data, 7)
    item = data[1][0]; item.current_stock = 3; item.is_active = False; db_session.commit()
    service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=[line(item, 4)]))
    assert item.current_stock == 0


@pytest.mark.parametrize('operation', ['create', 'update', 'delete'])
@pytest.mark.parametrize('failure', ['flush', 'commit'])
def test_write_failure_explicitly_rolls_back(db_session, data, operation, failure):
    record = create(db_session, data) if operation != 'create' else None
    before = snapshot(db_session)
    name = {'create': 'create_sales_return_item', 'update': 'update_sales_return', 'delete': 'deactivate_sales_return'}[operation]
    original = getattr(service.sales_return_repo, name)
    def fail(*args):
        original(*args)
        raise RuntimeError('After flush')
    target = patch.object(db_session, 'commit', side_effect=RuntimeError('Commit failed')) if failure == 'commit' else patch.object(service.sales_return_repo, name, side_effect=fail)
    with target:
        with pytest.raises(RuntimeError):
            if operation == 'create': create(db_session, data)
            elif operation == 'delete': service.delete_sales_return_by_id(db_session, record.id)
            else: service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=[line(data[1][0], 7)], remarks='Changed'))
    db_session.commit(); db_session.expire_all(); assert snapshot(db_session) == before


@pytest.mark.parametrize('quantity', [0, -1, float('nan'), float('inf')])
def test_invalid_quantity(data, quantity):
    with pytest.raises(ValidationError): SalesReturnItemCreate(**line(data[1][0], quantity))


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_tiny_shortage_rejected(db_session, data, operation):
    record = create(db_session, data, 1)
    item = data[1][0]; item.current_stock = 0 if operation == 'update' else 0.9999995
    db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        if operation == 'update': service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=[line(item, 0.9999995)]))
        else: service.delete_sales_return_by_id(db_session, record.id)
    db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('quantities,expected', [([3, 4], 3), ([5, 6], None), ([1, 2], None)])
def test_duplicate_update_uses_aggregate_delta(db_session, data, quantities, expected):
    item = data[1][0]
    record = create(db_session, data, items=[line(item, 2), line(item, 2)])
    item.current_stock = 0; db_session.commit(); before = snapshot(db_session)
    update = SalesReturnUpdate(items=[line(item, quantity) for quantity in quantities])
    if expected is None:
        with pytest.raises(HTTPException): service.update_sales_return_by_id(db_session, record.id, update)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_sales_return_by_id(db_session, record.id, update)
        assert item.current_stock == expected


def test_fractional_duplicates_reverse_exactly(db_session, data):
    item = data[1][0]; item.current_stock = 0; db_session.commit()
    record = create(db_session, data, items=[line(item, 0.1), line(item, 0.2)])
    assert item.current_stock == 0.3
    service.update_sales_return_by_id(db_session, record.id, SalesReturnUpdate(items=[line(item, 0.1)]))
    assert item.current_stock == 0.1
    service.delete_sales_return_by_id(db_session, record.id)
    assert item.current_stock == 0


def test_duplicate_delete_checks_total_stock(db_session, data):
    item = data[1][0]
    record = create(db_session, data, items=[line(item, 4), line(item, 4)])
    item.current_stock = 7; db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException): service.delete_sales_return_by_id(db_session, record.id)
    db_session.commit(); assert snapshot(db_session) == before
