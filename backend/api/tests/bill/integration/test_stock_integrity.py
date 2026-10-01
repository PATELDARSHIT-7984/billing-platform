"""Sequential Sale stock rules using real repositories and persisted snapshots."""
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.customer import Customer
from api.model.item_master import ItemMaster
from api.router.bill import router
from api.schema.bill import BillCreate, BillUpdate
from api.services import bill as service


@pytest.fixture
def inventory(db_session, test_app):
    test_app.include_router(router)
    buyer = Customer(customer_name='Buyer', mobile='9876543210', address='Road',
                     city='Ahmedabad', state='Gujarat')
    items = [ItemMaster(name=name, hsn_code='1234', unit='Box', current_stock=30,
                        sale_price=100, cgst=9, sgst=9) for name in ['LED Bulb', 'Item B', 'Item C']]
    db_session.add_all([buyer, *items]); db_session.commit()
    return buyer, items


def line(item, quantity, **changes):
    return dict(item_id=item.id, quantity=quantity, rate=100, disc_percent=0,
                cgst=0, sgst=0, igst=0) | changes


def payload(inventory, rows, **changes):
    return dict(customer_id=inventory[0].id, bill_date=date(2026, 9, 17), items=rows) | changes


def create(db, inventory, quantities=(10,)):
    return service.create_bill(db, BillCreate(**payload(inventory,
        [line(inventory[1][index], qty) for index, qty in enumerate(quantities)])))


def snapshot(db):
    db.flush()
    return {model.__tablename__: [tuple(getattr(row, col.name) for col in model.__table__.columns)
            for row in db.query(model).order_by(list(model.__table__.primary_key.columns)[0]).all()]
            for model in (Bill, BillItem, ItemMaster, Customer)}


@pytest.mark.parametrize('quantities,current,expected', [([5], 12, 7), ([7, 5], 12, 0), ([7, 6], 12, None), ([15], 12, None)])
def test_create_aggregate_stock(db_session, inventory, quantities, current, expected):
    item = inventory[1][0]; item.current_stock = current; db_session.commit()
    before = snapshot(db_session)
    data = BillCreate(**payload(inventory, [line(item, qty) for qty in quantities]))
    if expected is None:
        with pytest.raises(HTTPException) as error:
            service.create_bill(db_session, data)
        assert error.value.status_code == 400
        assert 'Requested quantity' in error.value.detail and 'LED Bulb' in error.value.detail
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.create_bill(db_session, data)
        assert item.current_stock == expected
        assert db_session.query(BillItem).count() == len(quantities)


def test_create_multiple_items_is_atomic(db_session, inventory):
    items = inventory[1]; items[0].current_stock = 10; items[1].current_stock = 3
    db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.create_bill(db_session, BillCreate(**payload(inventory, [line(items[0], 5), line(items[1], 4)])))
    db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('new,expected', [(15, 7), (6, 16), (10, 12), (25, None)])
def test_update_uses_only_difference(db_session, inventory, new, expected):
    bill = create(db_session, inventory)
    item = inventory[1][0]; item.current_stock = 12; db_session.commit()
    before = snapshot(db_session)
    data = BillUpdate(**payload(inventory, [line(item, new)], remarks='Edited'))
    if expected is None:
        with pytest.raises(HTTPException) as error:
            service.update_bill(db_session, bill.bill_id, data)
        assert 'Additional quantity required is 15' in error.value.detail
        assert '12' in error.value.detail
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_bill(db_session, bill.bill_id, data)
        assert item.current_stock == expected


@pytest.mark.parametrize('operation,shortage', [('replace', False), ('replace', True), ('add', False), ('add', True), ('remove', False), ('mixed', True)])
def test_update_line_changes_are_atomic(db_session, inventory, operation, shortage):
    items = inventory[1]
    bill = create(db_session, inventory, (10, 5))
    items[2].current_stock = 5 if shortage else 20
    db_session.commit(); before = snapshot(db_session)
    rows = {
        'replace': [line(items[2], 10), line(items[1], 5)],
        'add': [line(items[0], 10), line(items[1], 5), line(items[2], 7)],
        'remove': [line(items[1], 5)],
        'mixed': [line(items[0], 12), line(items[1], 5), line(items[2], 7)],
    }[operation]
    data = BillUpdate(**payload(inventory, rows, remarks='Must not partially persist', shipping_state='Maharashtra'))
    if shortage:
        with pytest.raises(HTTPException):
            service.update_bill(db_session, bill.bill_id, data)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_bill(db_session, bill.bill_id, data)
        expected = {'replace': [30, 25, 10], 'add': [20, 25, 13], 'remove': [30, 25, 20]}[operation]
        assert [item.current_stock for item in items] == expected


@pytest.mark.parametrize('new,expected', [([8, 7], 7), ([13, 12], None), ([3, 3], 16)])
def test_duplicate_old_and_new_lines_use_aggregate_delta(db_session, inventory, new, expected):
    item = inventory[1][0]
    bill = service.create_bill(db_session, BillCreate(**payload(inventory, [line(item, 4), line(item, 6)])))
    item.current_stock = 12; db_session.commit(); before = snapshot(db_session)
    data = BillUpdate(**payload(inventory, [line(item, qty) for qty in new]))
    if expected is None:
        with pytest.raises(HTTPException):
            service.update_bill(db_session, bill.bill_id, data)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_bill(db_session, bill.bill_id, data)
        assert item.current_stock == expected


@pytest.mark.parametrize('kind', ['rate', 'discount', 'gst_toggle', 'cgst_sgst', 'igst', 'shipping', 'date', 'customer'])
def test_financial_and_metadata_edits_do_not_change_stock(db_session, inventory, kind):
    item = inventory[1][0]
    bill = (service.create_bill(db_session, BillCreate(**payload(inventory, [line(item, 10, cgst=9, sgst=9)])))
            if kind == 'gst_toggle' else create(db_session, inventory))
    item.current_stock = 0; item.sale_price = 999; db_session.commit()
    row = line(item, 10); changes = {}
    if kind == 'rate': row['rate'] = 110
    if kind == 'discount': row['disc_percent'] = 10
    if kind == 'gst_toggle':
        assert bill.grand_total == 1180
        row.update(cgst=9, sgst=9)
        changes['is_gst'] = False
    if kind == 'cgst_sgst': row.update(cgst=9, sgst=9)
    if kind == 'igst': row.update(igst=18)
    if kind == 'shipping': changes['shipping_state'] = 'Maharashtra'
    if kind == 'date': changes['bill_date'] = date(2026, 9, 18)
    if kind == 'customer':
        buyer = Customer(customer_name='Second Buyer', mobile='9876543211', address='Other road', city='Surat', state='Gujarat')
        db_session.add(buyer); db_session.commit(); changes['customer_id'] = buyer.id
    result = service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory, [row], **changes)))
    assert item.current_stock == 0
    assert result['bill'].grand_total == {'rate': 1100, 'discount': 900, 'cgst_sgst': 1180, 'igst': 1180}.get(kind, 1000)
    if kind == 'customer': assert result['bill'].customer_name == 'Second Buyer'


@pytest.mark.parametrize('operation', ['reduce', 'same', 'remove', 'delete'])
def test_historical_inactive_item_reversal(db_session, inventory, operation):
    items = inventory[1]; bill = create(db_session, inventory, (10, 5))
    items[0].is_active = False; items[0].sale_price = 999; db_session.commit()
    if operation == 'delete':
        service.delete_bill(db_session, bill.bill_id)
        assert [item.current_stock for item in items] == [30, 30, 30]
    else:
        rows = [dict(item_id=items[1].id, quantity=5)]
        if operation != 'remove': rows.append(dict(item_id=items[0].id, quantity=6 if operation == 'reduce' else 10))
        service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory, rows)))
        assert items[0].current_stock == {'reduce': 24, 'same': 20, 'remove': 30}[operation]
        assert all(row.rate == 100 for row in bill.bill_items)


def test_new_inactive_item_still_rejected(db_session, inventory):
    bill = create(db_session, inventory)
    inventory[1][1].is_active = False; db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory, [line(inventory[1][1], 1)])))
    db_session.commit(); assert snapshot(db_session) == before


def test_delete_restores_duplicates_once_and_preserves_history(db_session, inventory, client):
    items = inventory[1]
    bill = service.create_bill(db_session, BillCreate(**payload(inventory, [line(items[0], 2), line(items[0], 3), line(items[1], 3)])))
    bill_id = bill.bill_id
    assert client.delete(f'/bills/{bill_id}').status_code == 200
    db_session.expire_all()
    assert [item.current_stock for item in items] == [30, 30, 30]
    assert not bill.is_active and len(bill.bill_items) == 3
    assert client.delete(f'/bills/{bill_id}').status_code == 404
    assert client.get(f'/bills/{bill_id}').status_code == 404
    assert client.get('/bills/').json() == []
    db_session.expire_all(); assert [item.current_stock for item in items] == [30, 30, 30]
    assert service.bill_repo.get_bill_by_id(db_session, bill_id, include_inactive=True) is not None


@pytest.mark.parametrize('operation', ['create', 'update', 'delete'])
@pytest.mark.parametrize('failure', ['flush', 'commit'])
def test_failure_after_writes_rolls_back_service_session(db_session, inventory, operation, failure):
    bill = create(db_session, inventory, (10, 5)) if operation != 'create' else None
    before = snapshot(db_session)
    repo_name = {'create': 'create_bill_item', 'update': 'update_bill', 'delete': 'deactivate_bill'}[operation]
    original = getattr(service.bill_repo, repo_name)
    def fail_after_flush(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('Injected failure after flush')
    target = (patch.object(db_session, 'commit', side_effect=RuntimeError('Injected commit failure'))
              if failure == 'commit' else patch.object(service.bill_repo, repo_name, side_effect=fail_after_flush))
    with target:
        with pytest.raises(RuntimeError):
            if operation == 'create': create(db_session, inventory, (10, 5))
            elif operation == 'delete': service.delete_bill(db_session, bill.bill_id)
            else: service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory,
                [line(inventory[1][0], 12)], remarks='Changed', shipping_state='Maharashtra')))
    db_session.commit(); db_session.expire_all()
    assert snapshot(db_session) == before


@pytest.mark.parametrize('schema', [BillCreate, BillUpdate])
@pytest.mark.parametrize('quantity', [float('inf'), float('-inf'), float('nan'), -1, 0])
def test_invalid_quantity_rejected(inventory, schema, quantity):
    with pytest.raises(ValidationError):
        schema(**payload(inventory, [line(inventory[1][0], quantity)]))


def test_tiny_shortage_is_rejected(db_session, inventory):
    bill = create(db_session, inventory)
    item = inventory[1][0]; item.current_stock = 0.9999995; db_session.commit()
    before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory, [line(item, 11)])))
    db_session.commit(); assert snapshot(db_session) == before


def test_two_existing_line_increases_reject_changed_customer_snapshot(db_session, inventory):
    bill = create(db_session, inventory, (10, 5))
    items = inventory[1]
    items[0].current_stock = 5; items[1].current_stock = 3
    buyer = Customer(customer_name='Different Buyer', mobile='9876543211', address='Other', city='Surat', state='Gujarat')
    db_session.add(buyer); db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory,
            [line(items[0], 12), line(items[1], 11)], customer_id=buyer.id, remarks='Rejected')))
    db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_shortage_detail_reaches_http_client(db_session, inventory, client, operation):
    bill = create(db_session, inventory) if operation == 'update' else None
    item = inventory[1][0]; item.current_stock = 12; db_session.commit()
    data = payload(inventory, [line(item, 25 if bill else 15)], bill_date='2026-09-17')
    response = client.put(f'/bills/{bill.bill_id}', json=data) if bill else client.post('/bills/', json=data)
    assert response.status_code == 400
    label = 'Additional quantity required' if bill else 'Requested quantity'
    assert response.json()['detail'] == f'Cannot sell LED Bulb. {label} is 15 units, but only 12 units are available.'


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_invalid_nonfinite_stored_stock_is_not_used(db_session, inventory, operation):
    bill = create(db_session, inventory) if operation == 'update' else None
    item = inventory[1][0]; item.current_stock = float('inf'); db_session.commit()
    before = snapshot(db_session)
    with pytest.raises(HTTPException, match='Current stock is invalid'):
        if bill:
            service.update_bill(db_session, bill.bill_id, BillUpdate(**payload(inventory, [line(item, 11)])))
        else:
            create(db_session, inventory)
    db_session.commit(); assert snapshot(db_session) == before
