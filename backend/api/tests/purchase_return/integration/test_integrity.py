"""Physical stock and original-document limits using real repositories."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.model.item_master import ItemMaster
from api.model.party import Party
from api.model.purchase import Purchase, PurchaseItem
from api.model.purchase_return import PurchaseReturn, PurchaseReturnItem
from api.router.purchase_return import router
from api.schema.purchase import PurchaseCreate
from api.schema.purchase_return import PurchaseReturnCreate, PurchaseReturnUpdate, PurchaseReturnItemCreate
from api.services.purchase import create_purchase
from api.services import purchase_return as service


@pytest.fixture
def data(db_session, test_app):
    test_app.include_router(router)
    parties = [Party(name=name, party_type='Supplier', current_balance=10000) for name in ['ABC', 'XYZ']]
    items = [ItemMaster(name=name, hsn_code='1234', unit='units', current_stock=50)
             for name in ['LED Bulb', 'Item B', 'Item C']]
    db_session.add_all([*parties, *items]); db_session.commit()
    purchase = create_purchase(db_session, PurchaseCreate(bill_no='PUR-001', party_id=parties[0].id,
        items=[line(items[0], 5), line(items[0], 5), line(items[1], 8)]))
    return parties, items, purchase


def line(item, quantity, **changes):
    return dict(item_id=item.id, item_name=item.name, hsn_code='1234', unit='units',
                quantity=quantity, price=100) | changes


def create(db, data, quantity=4, **changes):
    parties, items, _ = data
    payload = dict(party_id=parties[0].id, original_bill_no='PUR-001',
                   return_reason='Damaged', items=[line(items[0], quantity)]) | changes
    return service.create_purchase_return(db, PurchaseReturnCreate(**payload))


def snapshot(db):
    db.flush()
    return {model.__tablename__: [tuple(getattr(row, col.name) for col in model.__table__.columns)
            for row in db.query(model).order_by(list(model.__table__.primary_key.columns)[0]).all()]
            for model in (Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem, ItemMaster, Party)}


@pytest.mark.parametrize('quantity,stock,reference,allowed', [(5, 8, None, True), (10, 8, None, False),
    (10, 50, 'PUR-001', True), (15, 50, 'PUR-001', False), (1, 50, 'MISSING', False)])
def test_create_physical_and_document_limits(db_session, data, quantity, stock, reference, allowed):
    item = data[1][0]; item.current_stock = stock; db_session.commit()
    before = snapshot(db_session); balance = data[0][0].current_balance
    if allowed:
        result = create(db_session, data, quantity, original_bill_no=reference)
        assert item.current_stock == stock - quantity
        assert data[0][0].current_balance == balance - Decimal(str(result.grand_total))
    else:
        with pytest.raises(HTTPException): create(db_session, data, quantity, original_bill_no=reference)
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('failure', ['supplier', 'item', 'inactive_purchase', 'multi_line'])
def test_invalid_original_document_changes_nothing(db_session, data, failure):
    parties, items, purchase = data
    changes = {}
    if failure == 'supplier': changes['party_id'] = parties[1].id
    if failure == 'item': changes['items'] = [line(items[2], 1)]
    if failure == 'multi_line': changes['items'] = [line(items[0], 2), line(items[1], 9)]
    if failure == 'inactive_purchase': purchase.is_active = False
    db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException): create(db_session, data, **changes)
    db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('second,allowed', [(6, True), (7, False)])
def test_other_active_returns_reduce_remaining(db_session, data, second, allowed):
    create(db_session, data, 4, original_bill_no=' pur-001 ')
    before = snapshot(db_session)
    if allowed:
        create(db_session, data, second)
        assert data[1][0].current_stock == 50
    else:
        with pytest.raises(HTTPException) as error: create(db_session, data, second)
        assert 'already returned: 4' in error.value.detail
        assert 'remaining returnable quantity: 6' in error.value.detail
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('other,old,new,current,expected', [(0, 4, 7, 3, 0), (0, 7, 4, 0, 3),
    (4, 2, 6, 4, 0), (4, 2, 7, 50, None), (0, 4, 7, 2, None)])
def test_update_excludes_itself_and_uses_stock_difference(db_session, data, other, old, new, current, expected):
    if other: create(db_session, data, other)
    record = create(db_session, data, old)
    item = data[1][0]; item.current_stock = current; db_session.commit()
    before = snapshot(db_session)
    update = PurchaseReturnUpdate(items=[line(item, new)], remarks='Changed')
    if expected is None:
        with pytest.raises(HTTPException): service.update_purchase_return_by_id(db_session, record.id, update)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_purchase_return_by_id(db_session, record.id, update)
        assert item.current_stock == expected


@pytest.mark.parametrize('mode', ['valid', 'stock', 'absent', 'cap'])
def test_item_replacement_validates_both_rules(db_session, data, mode):
    items = data[1]; record = create(db_session, data, 5)
    replacement = items[2] if mode == 'absent' else items[1]
    if mode == 'stock': replacement.current_stock = 4
    qty = 9 if mode == 'cap' else 5
    db_session.commit(); before = snapshot(db_session)
    update = PurchaseReturnUpdate(items=[line(replacement, qty)])
    if mode != 'valid':
        with pytest.raises(HTTPException): service.update_purchase_return_by_id(db_session, record.id, update)
        db_session.commit(); assert snapshot(db_session) == before
    else:
        service.update_purchase_return_by_id(db_session, record.id, update)
        assert items[0].current_stock == 60 and items[1].current_stock == 53


@pytest.mark.parametrize('quantities,allowed', [([4, 6], True), ([4, 7], False)])
def test_duplicate_purchase_and_return_lines(db_session, data, quantities, allowed):
    before = snapshot(db_session)
    rows = [line(data[1][0], qty) for qty in quantities]
    if allowed:
        create(db_session, data, items=rows)
        assert data[1][0].current_stock == 50
    else:
        with pytest.raises(HTTPException): create(db_session, data, items=rows)
        db_session.commit(); assert snapshot(db_session) == before


@pytest.mark.parametrize('mode', ['new_purchase', 'wrong_supplier', 'valid_purchase', 'clear'])
def test_header_only_changes_validate_effective_lines(db_session, data, mode):
    record = create(db_session, data, 4)
    parties, items, _ = data
    create_purchase(db_session, PurchaseCreate(bill_no='PUR-002', party_id=parties[0].id,
        items=[line(items[0], 3 if mode == 'new_purchase' else 8)]))
    before = snapshot(db_session)
    changes = {'original_bill_no': 'PUR-002'}
    if mode == 'wrong_supplier': changes = {'party_id': parties[1].id}
    if mode == 'clear': changes = {'original_bill_no': None}
    if mode in ['new_purchase', 'wrong_supplier']:
        with pytest.raises(HTTPException): service.update_purchase_return_by_id(db_session, record.id, PurchaseReturnUpdate(**changes))
        db_session.commit(); assert snapshot(db_session) == before
    else:
        stock = items[0].current_stock
        service.update_purchase_return_by_id(db_session, record.id, PurchaseReturnUpdate(**changes))
        assert items[0].current_stock == stock
        assert record.original_bill_no == (None if mode == 'clear' else 'PUR-002')


@pytest.mark.parametrize('changes', [dict(price=110), dict(disc_percent=10), dict(sgst=9, cgst=9)])
def test_financial_only_edits_preserve_stock(db_session, data, changes):
    record = create(db_session, data)
    item = data[1][0]; stock = item.current_stock; balance = data[0][0].current_balance
    old_total = record.grand_total
    service.update_purchase_return_by_id(db_session, record.id, PurchaseReturnUpdate(items=[line(item, 4, **changes)]))
    assert item.current_stock == stock
    assert data[0][0].current_balance == balance + Decimal(str(old_total)) - Decimal(str(record.grand_total))


def test_delete_restores_stock_balance_and_document_capacity(db_session, data):
    balance = data[0][0].current_balance
    record = create(db_session, data)
    data[1][0].is_active = False; db_session.commit()
    service.delete_purchase_return_by_id(db_session, record.id)
    assert data[1][0].current_stock == 60
    assert data[0][0].current_balance == balance
    assert not record.is_active
    before = snapshot(db_session)
    with pytest.raises(HTTPException): service.delete_purchase_return_by_id(db_session, record.id)
    db_session.commit(); assert snapshot(db_session) == before
    data[1][0].is_active = True; db_session.commit()
    create(db_session, data, 10)
    assert data[1][0].current_stock == 50


def test_inactive_historical_item_can_be_reduced(db_session, data):
    record = create(db_session, data, 7)
    item = data[1][0]; item.is_active = False; db_session.commit()
    service.update_purchase_return_by_id(db_session, record.id, PurchaseReturnUpdate(items=[line(item, 4)]))
    assert item.current_stock == 56


@pytest.mark.parametrize('quantity', [0, -1, float('inf'), float('nan')])
def test_quantity_validation(data, quantity):
    with pytest.raises(ValidationError): PurchaseReturnItemCreate(**line(data[1][0], quantity))


@pytest.mark.parametrize('operation', ['create', 'update', 'delete'])
def test_linked_return_late_failure_rolls_back(db_session, data, operation):
    record = create(db_session, data) if operation != 'create' else None
    before = snapshot(db_session)
    original = service.apply_party_balance_delta
    def fail(*args):
        original(*args)
        raise RuntimeError('After flush')
    with patch.object(service, 'apply_party_balance_delta', side_effect=fail):
        with pytest.raises(RuntimeError):
            if operation == 'create': create(db_session, data)
            elif operation == 'delete': service.delete_purchase_return_by_id(db_session, record.id)
            else: service.update_purchase_return_by_id(db_session, record.id, PurchaseReturnUpdate(items=[line(data[1][0], 7)]))
    db_session.commit(); db_session.expire_all(); assert snapshot(db_session) == before


def test_document_limit_message_is_http_detail(client, db_session, data):
    response = client.post('/purchase-returns/', json=dict(party_id=data[0][0].id,
        original_bill_no='PUR-001', return_reason='Damaged', items=[line(data[1][0], 15)]))
    assert response.status_code == 400
    message = response.json()['detail']
    assert 'LED Bulb' in message and 'PUR-001' in message and '15' in message and '10' in message


@pytest.mark.parametrize('other,allowed', [(0, True), (4, False)])
def test_duplicate_update_uses_aggregate_delta_and_document_cap(db_session, data, other, allowed):
    if other: create(db_session, data, other)
    record = create(db_session, data, items=[line(data[1][0], 1), line(data[1][0], 3)])
    item = data[1][0]; item.current_stock = 3; db_session.commit(); before = snapshot(db_session)
    update = PurchaseReturnUpdate(items=[line(item, 2), line(item, 5)])
    if allowed:
        service.update_purchase_return_by_id(db_session, record.id, update)
        assert item.current_stock == 0
    else:
        with pytest.raises(HTTPException): service.update_purchase_return_by_id(db_session, record.id, update)
        db_session.commit(); assert snapshot(db_session) == before


def test_duplicate_standalone_lines_cannot_bypass_physical_stock(db_session, data):
    item = data[1][0]; item.current_stock = 8; db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        create(db_session, data, original_bill_no=None, items=[line(item, 4), line(item, 5)])
    db_session.commit(); assert snapshot(db_session) == before


def test_legacy_reference_casing_and_spaces_still_count(db_session, data):
    record = create(db_session, data, 4)
    record.original_bill_no = ' pur-001 '; db_session.commit()
    with pytest.raises(HTTPException): create(db_session, data, 7)


def test_fractional_document_quantities_have_no_sum_drift(db_session, data):
    parties, items, _ = data
    create_purchase(db_session, PurchaseCreate(bill_no='FRACTION', party_id=parties[0].id,
        items=[line(items[0], 0.1), line(items[0], 0.2)]))
    items[0].current_stock = 0.3; db_session.commit()
    create(db_session, data, 0.1, original_bill_no='FRACTION')
    create(db_session, data, 0.2, original_bill_no='FRACTION')
    assert items[0].current_stock == 0


def test_tiny_physical_shortage_rejected(db_session, data):
    record = create(db_session, data, 1)
    item = data[1][0]; item.current_stock = 0; db_session.commit(); before = snapshot(db_session)
    with pytest.raises(HTTPException):
        service.update_purchase_return_by_id(db_session, record.id,
            PurchaseReturnUpdate(items=[line(item, 1.0000005)]))
    db_session.commit(); assert snapshot(db_session) == before


def test_valid_supplier_and_original_bill_change(db_session, data):
    parties, items, _ = data
    record = create(db_session, data, 4)
    create_purchase(db_session, PurchaseCreate(bill_no='OTHER', party_id=parties[1].id, items=[line(items[0], 8)]))
    balances = [party.current_balance for party in parties]; stock = items[0].current_stock
    service.update_purchase_return_by_id(db_session, record.id,
        PurchaseReturnUpdate(party_id=parties[1].id, original_bill_no='OTHER'))
    assert items[0].current_stock == stock
    assert parties[0].current_balance == balances[0] + Decimal(400)
    assert parties[1].current_balance == balances[1] - Decimal(400)
    # Moving the return frees the old Purchase's capacity.
    create(db_session, data, 10)
