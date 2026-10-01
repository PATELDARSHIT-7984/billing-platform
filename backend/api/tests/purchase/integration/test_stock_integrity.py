"""Purchase stock and accounting against real repositories, without lot assumptions."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.customer import Customer
from api.model.item_master import ItemMaster
from api.model.party import Party
from api.model.purchase import Purchase, PurchaseItem
from api.repository import bill as bill_repo
from api.router.purchase import router
from api.schema.purchase import PurchaseCreate, PurchaseUpdate, PurchaseItemCreate
from api.services import purchase as service


@pytest.fixture
def stock_data(db_session, test_app):
    test_app.include_router(router)
    parties = [Party(name=name, party_type='Supplier', current_balance=100,
                     opening_balance=100) for name in ['Supplier A', 'Supplier B']]
    items = [ItemMaster(name=name, code=name, hsn_code='1234', unit='units', current_stock=10)
             for name in ['LED Bulb', 'Item B', 'Item C']]
    db_session.add_all(parties + items)
    db_session.commit()
    return parties, items


def line(item, quantity, **changes):
    return dict(item_id=item.id, item_name=item.name, hsn_code='1234', unit='units',
                quantity=quantity, price=100, **changes)


def create(db, data, quantities=(20,)):
    parties, items = data
    return service.create_purchase(db, PurchaseCreate(
        bill_no='PUR-001', party_id=parties[0].id,
        items=[line(items[index], qty) for index, qty in enumerate(quantities)],
    ))


def snapshot(db):
    # Include every persisted column, including prices/dates and balance types.
    db.flush()
    return {model.__tablename__: [tuple(getattr(row, column.name) for column in model.__table__.columns)
                                 for row in db.query(model).order_by(model.__table__.primary_key.columns.values()[0]).all()]
            for model in (Purchase, PurchaseItem, ItemMaster, Party)}


def sale_context(db, item, number='INV-0012', active=True, line_active=True, duplicate=False):
    customer = db.query(Customer).first()
    if customer is None:
        customer = Customer(customer_name='Buyer', mobile='9876543210', address='Road',
                            city='Ahmedabad', state='Gujarat')
        db.add(customer)
        db.flush()
    bill = Bill(invoice_no=number, customer_id=customer.id, customer_name='Buyer',
                mobile='9876543210', address='Road', city='Ahmedabad', state='Gujarat',
                bill_date=date(2026, 1, 1), total_boxes=1, subtotal=100, taxable_amount=100,
                grand_total=100, amount_in_words='One hundred', is_active=active)
    db.add(bill)
    db.flush()
    for _ in range(2 if duplicate else 1):
        db.add(BillItem(bill_id=bill.bill_id, item_id=item.id, item_name=item.name,
                        hsn_code='1234', unit='units', quantity=1, rate=100,
                        taxable_amount=100, gst_percent=0, line_total=100, is_active=line_active))
    db.commit()


@pytest.mark.parametrize('quantities,expected', [((5,), [15, 10, 10]), ((5, 10), [15, 20, 10])])
def test_create_adds_stock(db_session, stock_data, quantities, expected):
    purchase = create(db_session, stock_data, quantities)
    assert [row.current_stock for row in stock_data[1]] == expected
    assert stock_data[0][0].current_balance == Decimal(100 + purchase.grand_total)


def test_duplicate_lines_aggregate_on_create_and_update(db_session, stock_data):
    parties, items = stock_data
    purchase = service.create_purchase(db_session, PurchaseCreate(
        bill_no='DUP', party_id=parties[0].id, items=[line(items[0], 5), line(items[0], 3)]))
    assert items[0].current_stock == 18
    service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(
        items=[line(items[0], 2), line(items[0], 4)]))
    assert items[0].current_stock == 16


@pytest.mark.parametrize('old,new,current,expected', [(10, 15, 3, 8), (10, 6, 10, 6), (20, 15, 12, 7), (100, 90, 95, 85)])
def test_quantity_delta_with_active_sales(db_session, stock_data, old, new, current, expected):
    purchase = create(db_session, stock_data, (old,))
    item = stock_data[1][0]
    item.current_stock = current
    sale_context(db_session, item)
    with patch.object(bill_repo, 'get_active_invoice_references_for_item') as references:
        service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(item, new)]))
        references.assert_not_called()
    assert item.current_stock == expected
    assert stock_data[0][0].current_balance == Decimal(100 + new * 100)


@pytest.mark.parametrize('operation,expected', [('replace', [10, 20, 10]), ('add', [20, 15, 17]), ('remove', [10, 15, 10])])
def test_line_changes(db_session, stock_data, operation, expected):
    _, items = stock_data
    purchase = create(db_session, stock_data, (10, 5) if operation != 'replace' else (10,))
    rows = {'replace': [line(items[1], 10)], 'add': [line(items[0], 10), line(items[1], 5), line(items[2], 7)],
            'remove': [line(items[1], 5)]}[operation]
    service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=rows))
    assert [row.current_stock for row in items] == expected


@pytest.mark.parametrize('operation', ['reduce', 'replace', 'remove', 'mixed'])
def test_shortage_rejects_entire_edit(db_session, stock_data, operation):
    parties, items = stock_data
    purchase = create(db_session, stock_data, (20, 10))
    items[0].current_stock = 12
    db_session.commit()
    before = snapshot(db_session)
    rows = {
        'reduce': [line(items[0], 5), line(items[1], 10)],
        'replace': [line(items[2], 20), line(items[1], 10)],
        'remove': [line(items[1], 10)],
        'mixed': [line(items[1], 6), line(items[0], 5), line(items[2], 7)],
    }[operation]
    with pytest.raises(HTTPException) as error:
        service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(
            bill_no='CHANGED', remarks='Changed', party_id=parties[1].id, items=rows))
    assert error.value.status_code == 400
    # Service must leave no pending changes that a later commit could persist.
    db_session.commit()
    assert snapshot(db_session) == before


@pytest.mark.parametrize('kind', ['price', 'gst', 'discount', 'gst_header', 'text', 'party'])
def test_non_quantity_edits_preserve_stock_and_accounting(db_session, stock_data, kind):
    parties, items = stock_data
    purchase = create(db_session, stock_data, (10,))
    items[0].current_stock = 0  # All units can be consumed; unchanged quantities remain valid.
    db_session.commit()
    original_total = Decimal(str(purchase.grand_total))
    row = line(items[0], 10)
    changes = {'price': {'price': 110}, 'gst': {'sgst': 9, 'cgst': 9}, 'discount': {'disc_percent': 10}}
    if kind in changes:
        row.update(changes[kind])
        payload = PurchaseUpdate(items=[row])
    else:
        payload = PurchaseUpdate(**{'gst_header': {'is_gst': False},
                                    'text': {'bill_no': 'NEW', 'bill_date': date(2026, 2, 1), 'remarks': 'Edited'},
                                    'party': {'party_id': parties[1].id}}[kind])
    service.update_purchase_by_id(db_session, purchase.id, payload)
    assert items[0].current_stock == 0
    db_session.refresh(parties[0]); db_session.refresh(parties[1])
    if kind == 'party':
        assert parties[0].current_balance == 100
        assert parties[1].current_balance == 100 + original_total
    else:
        assert parties[0].current_balance == 100 + Decimal(str(purchase.grand_total))
        assert parties[1].current_balance == 100


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_validation_failure_rolls_back_created_items(db_session, stock_data, operation):
    parties, items = stock_data
    purchase = create(db_session, stock_data) if operation == 'update' else None
    before = snapshot(db_session)
    new_item = dict(item_name='New temporary item', hsn_code='1234', unit='units', quantity=7, price=100)
    invalid = line(items[0], 1); invalid['item_id'] = 999999
    with pytest.raises(HTTPException):
        if purchase:
            service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[new_item, invalid]))
        else:
            service.create_purchase(db_session, PurchaseCreate(bill_no='FAIL', party_id=parties[0].id,
                                                             items=[line(items[0], 5), new_item, invalid]))
    db_session.commit()
    assert snapshot(db_session) == before


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_late_failure_rolls_back_stock_items_and_balance(db_session, stock_data, operation):
    purchase = create(db_session, stock_data) if operation == 'update' else None
    before = snapshot(db_session)
    with patch.object(db_session, 'commit', side_effect=RuntimeError('forced commit failure')):
        with pytest.raises(RuntimeError):
            if purchase:
                service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(stock_data[1][0], 25)]))
            else:
                create(db_session, stock_data)
    db_session.commit()
    assert snapshot(db_session) == before


def test_sales_context_is_active_distinct_bounded_and_http_visible(db_session, stock_data, client):
    purchase = create(db_session, stock_data)
    item = stock_data[1][0]; item.current_stock = 12
    for index in range(1, 8):
        sale_context(db_session, item, f'INV-{index:04}', duplicate=True)
    sale_context(db_session, item, 'DELETED-INVOICE', active=False)
    sale_context(db_session, item, 'INACTIVE-LINE', line_active=False)
    sale_context(db_session, stock_data[1][1], 'OTHER-ITEM')
    response = client.put(f'/purchases/{purchase.id}', json={'items': [line(item, 5)]})
    assert response.status_code == 400
    message = response.json()['detail']
    for text in ['LED Bulb', '20', '5', '15', '12', 'INV-0007', 'INV-0003', 'and 2 more']:
        assert text in message
    for text in ['DELETED-INVOICE', 'INACTIVE-LINE', 'OTHER-ITEM', 'INV-0001', 'INV-0002']:
        assert text not in message


def test_shortage_without_sales_has_clear_quantity_message(db_session, stock_data):
    purchase = create(db_session, stock_data)
    item = stock_data[1][0]; item.current_stock = 12; db_session.commit()
    with pytest.raises(HTTPException) as error:
        service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(item, 5)]))
    message = error.value.detail
    assert 'from 20 to 5' in message and 'removing 15' in message and '12' in message
    assert 'Sales invoices' not in message


@pytest.mark.parametrize('old,new,current,expected', [(0.3, 0.1, 0.2, 0), (1, 0.9999995, 0, None)])
def test_fractional_stock_never_becomes_negative(db_session, stock_data, old, new, current, expected):
    purchase = create(db_session, stock_data, (old,))
    item = stock_data[1][0]; item.current_stock = current; db_session.commit()
    if expected is None:
        with pytest.raises(HTTPException):
            service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(item, new)]))
    else:
        service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(item, new)]))
        assert item.current_stock == expected


@pytest.mark.parametrize('quantity', [float('inf'), float('-inf'), float('nan'), 0, -1])
def test_quantity_must_be_positive_and_finite(stock_data, quantity):
    with pytest.raises(ValidationError):
        PurchaseItemCreate(**line(stock_data[1][0], quantity))


def test_purchase_deletion_remains_prohibited(client, db_session, stock_data):
    purchase = create(db_session, stock_data)
    assert client.delete(f'/purchases/{purchase.id}').status_code == 405
    assert client.put(f'/purchases/{purchase.id}', json={'is_active': False}).status_code == 400


def test_shortage_rolls_back_new_item_resolution(db_session, stock_data):
    purchase = create(db_session, stock_data)
    item = stock_data[1][0]
    item.current_stock = 12
    db_session.commit()
    before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[
            dict(item_name='Temporary replacement', hsn_code='1234', unit='units', quantity=7, price=100),
            line(item, 5),
        ]))
    db_session.commit()
    assert snapshot(db_session) == before


def test_fractional_duplicate_lines_and_repeated_updates(db_session, stock_data):
    parties, items = stock_data
    items[0].current_stock = 0
    db_session.commit()
    purchase = service.create_purchase(db_session, PurchaseCreate(
        bill_no='FRACTION', party_id=parties[0].id, items=[line(items[0], 0.1), line(items[0], 0.2)]))
    assert items[0].current_stock == 0.3
    service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(items[0], 0.3)]))
    assert items[0].current_stock == 0.3
    service.update_purchase_by_id(db_session, purchase.id, PurchaseUpdate(items=[line(items[0], 0.1)]))
    assert items[0].current_stock == 0.1
