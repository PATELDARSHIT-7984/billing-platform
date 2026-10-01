from datetime import date
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.dependencies import dependencies
from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.customer import Customer
from api.model.item_master import ItemMaster
from api.router.bill import router
from api.schema.bill import BillCreate, BillUpdate
from api.schema.bill_item import BillItemResponse
from api.services import bill as service


@pytest.fixture
def sale_data(db_session):
    customer = Customer(customer_name="Buyer", mobile="9876543210", address="Address",
                        city="Ahmedabad", state="Gujarat")
    item = ItemMaster(name="Tile", hsn_code="6907", unit="Box", sale_price=100,
                      cgst=9, sgst=9, current_stock=100)
    db_session.add_all([customer, item])
    db_session.commit()
    return customer, item


def payload(sale_data, **changes):
    customer, item = sale_data
    result = dict(customer_id=customer.id, bill_date=date(2026, 9, 15),
                  items=[dict(item_id=item.id, quantity=2, rate=80,
                              disc_percent=10, cgst=9, sgst=9, igst=0)])
    result.update(changes)
    return result


@pytest.mark.parametrize("gst,taxes,expected", [
    (True, (9, 9, 0), (12.96, 12.96, 0, 169.92)),
    (True, (0, 0, 18), (0, 0, 25.92, 169.92)),
    (False, (9, 9, 0), (0, 0, 0, 144)),
])
def test_persisted_transaction_inputs(db_session, sale_data, gst, taxes, expected):
    data = payload(sale_data, is_gst=gst, shipping_state="Maharashtra")
    data['items'][0].update(cgst=taxes[0], sgst=taxes[1], igst=taxes[2])
    bill = service.create_bill(db_session, BillCreate(**data))
    db_session.expire_all()
    bill = db_session.get(Bill, bill.bill_id)
    line = bill.bill_items[0]
    assert line.rate == 80
    assert line.discount_amount == 16
    assert line.taxable_amount == 144
    assert (line.cgst_amount, line.sgst_amount, line.igst_amount, line.line_total) == expected
    assert (bill.cgst_amount, bill.sgst_amount, bill.igst_amount, bill.grand_total) == expected
    assert (bill.subtotal, bill.discount_amount, bill.taxable_amount) == (160, 16, 144)
    assert bill.shipping_state == "Maharashtra"
    assert bill.is_interstate is (gst and taxes[2] > 0)
    assert sale_data[1].sale_price == 100
    assert sale_data[1].current_stock == 98
    assert BillItemResponse.model_validate(line).discount_amount == 16


def test_multiple_lines_sum_persisted_components(db_session, sale_data):
    data = payload(sale_data)
    data['items'].append(dict(item_id=sale_data[1].id, quantity=1, rate=10.05,
                              disc_percent=0, cgst=9, sgst=9, igst=0))
    bill = service.create_bill(db_session, BillCreate(**data))
    db_session.expire_all()
    lines = bill.bill_items
    assert lines[1].line_total == 11.85
    assert bill.grand_total == 181.77
    assert bill.grand_total == pytest.approx(sum(line.line_total for line in lines))
    assert bill.taxable_amount == pytest.approx(sum(line.taxable_amount for line in lines))
    assert bill.discount_amount == sum(line.discount_amount for line in lines)
    assert bill.cgst_amount == pytest.approx(sum(line.cgst_amount for line in lines))
    assert sale_data[1].current_stock == 97


@pytest.mark.parametrize("interstate", [False, True])
def test_legacy_create_uses_master_defaults(db_session, sale_data, interstate):
    data = payload(sale_data, is_interstate=interstate,
                   items=[dict(item_id=sale_data[1].id, quantity=1)])
    bill = service.create_bill(db_session, BillCreate(**data))
    assert bill.grand_total == 118
    assert bill.bill_items[0].rate == 100
    assert bill.is_interstate is interstate


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("gst", [False, True])
def test_edit_preserves_saved_inputs_after_master_change(db_session, sale_data, explicit, gst):
    data = payload(sale_data, is_gst=gst)
    bill = service.create_bill(db_session, BillCreate(**data))
    expected = bill.grand_total
    old = bill.bill_items[0]
    item = sale_data[1]
    item.sale_price, item.cgst, item.sgst = 999, 14, 14
    db_session.commit()
    if not explicit:
        data.pop('is_gst')
        data['items'] = [dict(item_id=item.id, quantity=2)]
    else:
        data['items'][0]['bill_item_id'] = old.bill_item_id
    updated = service.update_bill(db_session, bill.bill_id, BillUpdate(**data, remarks="Edited"))['bill']
    db_session.expire_all()
    assert updated.grand_total == expected
    assert updated.bill_items[0].rate == 80
    assert updated.bill_items[0].discount_amount == 16
    assert item.current_stock == 98
    assert updated.remarks == "Edited"


def test_edit_changes_explicit_rate_and_quantity(db_session, sale_data):
    data = payload(sale_data)
    bill = service.create_bill(db_session, BillCreate(**data))
    data['items'][0].update(rate=90, quantity=3)
    updated = service.update_bill(db_session, bill.bill_id, BillUpdate(**data))['bill']
    db_session.expire_all()
    assert updated.grand_total == 286.74
    assert updated.bill_items[0].rate == 90
    assert updated.discount_amount == 27
    assert sale_data[1].current_stock == 97


def test_duplicate_historical_lines_need_unambiguous_identity(db_session, sale_data):
    data = payload(sale_data)
    data['items'].append(dict(item_id=sale_data[1].id, quantity=1, rate=50))
    bill = service.create_bill(db_session, BillCreate(**data))
    data['items'] = [dict(item_id=sale_data[1].id, quantity=1)]
    with pytest.raises(HTTPException, match="bill_item_id"):
        service.update_bill(db_session, bill.bill_id, BillUpdate(**data))
    data['items'] = [dict(item_id=line.item_id, bill_item_id=line.bill_item_id,
                          quantity=line.quantity) for line in bill.bill_items]
    service.update_bill(db_session, bill.bill_id, BillUpdate(**data))
    db_session.expire_all()
    assert sorted(line.rate for line in bill.bill_items) == [50, 80]


def test_api_ignores_forged_totals(client, test_app, db_session, sale_data):
    test_app.include_router(router)
    data = payload(sale_data, subtotal=1, grand_total=1)
    data['bill_date'] = data['bill_date'].isoformat()
    data['items'][0].update(line_total=1, taxable_amount=1)
    response = client.post('/bills/', json=data)
    assert response.status_code == 201, response.text
    assert response.json()['grand_total'] == 169.92
    assert db_session.query(BillItem).one().line_total == 169.92


@pytest.mark.parametrize("changes", [dict(rate=-1), dict(disc_percent=101), dict(igst=18)])
def test_api_rejects_invalid_inputs_before_writing(client, test_app, db_session, sale_data, changes):
    test_app.include_router(router)
    data = payload(sale_data)
    data['bill_date'] = data['bill_date'].isoformat()
    data['items'][0].update(changes)
    response = client.post('/bills/', json=data)
    assert response.status_code == 422
    assert db_session.query(Bill).count() == 0
    assert sale_data[1].current_stock == 100


def test_metadata_edit_preserves_legacy_invoice_rounding(db_session, sale_data):
    data = payload(sale_data)
    bill = service.create_bill(db_session, BillCreate(**data))
    # Old service summed rounded taxes independently of rounded line totals.
    bill.grand_total = 169.91
    bill.amount_in_words = "Historical amount"
    db_session.commit()
    updated = service.update_bill(db_session, bill.bill_id, BillUpdate(**data, remarks="Note"))['bill']
    db_session.expire_all()
    assert updated.grand_total == 169.91
    assert updated.amount_in_words == "Historical amount"


@pytest.mark.parametrize("rate,discount,cgst,expected", [
    (1.005, 0, 0, 1.01), (100.5, 0, 0, 100.5), (0.05, 0, 10, 0.06),
    (80, 100, 9, 0), (0, 10, 9, 0),
])
def test_sales_paise_rounding(db_session, sale_data, rate, discount, cgst, expected):
    data = payload(sale_data, items=[dict(item_id=sale_data[1].id, quantity=1,
                   rate=rate, disc_percent=discount, cgst=cgst, sgst=0, igst=0)])
    bill = service.create_bill(db_session, BillCreate(**data))
    assert bill.grand_total == expected


def test_get_bill_detail_contract(client, test_app, db_session, sale_data):
    test_app.include_router(router)
    bill = service.create_bill(db_session, BillCreate(**payload(sale_data)))
    response = client.get(f'/bills/{bill.bill_id}')
    assert response.status_code == 200, response.text
    detail = response.json()
    assert set(detail) == {'bill', 'items'}
    assert detail['bill']['bill_id'] == bill.bill_id
    assert detail['bill']['bill_date'] == '2026-09-15'
    assert detail['bill']['grand_total'] == 169.92
    assert len(detail['items']) == 1
    assert detail['items'][0]['rate'] == 80
    assert detail['items'][0]['discount_amount'] == 16
    assert detail['items'][0]['line_total'] == 169.92


def test_get_missing_bill_keeps_404(client, test_app):
    test_app.include_router(router)
    response = client.get('/bills/999')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Bill with ID 999 not found'}


def test_put_returns_committed_detail(client, test_app, db_session, sale_data):
    test_app.include_router(router)
    data = payload(sale_data)
    bill = service.create_bill(db_session, BillCreate(**data))
    data['bill_date'] = data['bill_date'].isoformat()
    data['remarks'] = 'Updated'
    data['items'][0].update(rate=90, quantity=3)
    response = client.put(f'/bills/{bill.bill_id}', json=data)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert set(detail) == {'bill', 'items'}
    assert detail['bill']['bill_id'] == bill.bill_id
    assert detail['bill']['remarks'] == 'Updated'
    assert detail['bill']['grand_total'] == 286.74
    assert len(detail['items']) == 1
    assert detail['items'][0]['quantity'] == 3
    assert detail['items'][0]['rate'] == 90
    assert detail['items'][0]['line_total'] == 286.74
    db_session.expire_all()
    assert bill.remarks == 'Updated'
    assert bill.grand_total == 286.74
    assert [BillItemResponse.model_validate(line).model_dump() for line in bill.bill_items] == detail['items']
    assert sale_data[1].current_stock == 97
    assert client.get(f'/bills/{bill.bill_id}').json() == detail


@pytest.mark.parametrize('failure', ['invalid_rate', 'insufficient_stock', 'before_commit'])
def test_put_failure_does_not_persist(client, test_app, db_session, sale_data,
                                    test_session_factory, monkeypatch, failure):
    test_app.include_router(router)
    # Exercise production session cleanup against the existing test database.
    test_app.dependency_overrides.pop(dependencies.get_db)
    monkeypatch.setattr(dependencies, 'SessionLocal', test_session_factory)
    data = payload(sale_data)
    bill = service.create_bill(db_session, BillCreate(**data))
    original_items = [BillItemResponse.model_validate(line).model_dump() for line in bill.bill_items]
    data['bill_date'] = data['bill_date'].isoformat()
    data['remarks'] = 'Must not persist'
    data['items'][0].update(rate=90, quantity=3)
    if failure == 'before_commit':
        # Stock and replacement items have already been flushed at this point.
        with patch.object(service.bill_repo, 'update_bill', side_effect=RuntimeError('precommit failure')):
            with pytest.raises(RuntimeError, match='precommit failure'):
                client.put(f'/bills/{bill.bill_id}', json=data)
    else:
        data['items'][0].update({'rate': -1} if failure == 'invalid_rate' else {'quantity': 101})
        response = client.put(f'/bills/{bill.bill_id}', json=data)
        assert response.status_code == (422 if failure == 'invalid_rate' else 400)
    db_session.expire_all()
    assert bill.remarks is None
    assert bill.grand_total == 169.92
    assert [BillItemResponse.model_validate(line).model_dump() for line in bill.bill_items] == original_items
    assert sale_data[1].current_stock == 98


@pytest.mark.parametrize("params,expected,status", [
    ({}, ["INV-C", "INV-B", "INV-A"], 200),
    ({"search": "inv-b"}, ["INV-B"], 200),
    ({"search": "Alice"}, ["INV-C", "INV-A"], 200),
    ({"search": "missing"}, [], 200),
    ({"limit": 1}, ["INV-C"], 200),
    ({"skip": 1, "limit": 1}, ["INV-B"], 200),
    ({"search": "Alice", "skip": 1, "limit": 1}, ["INV-A"], 200),
    ({"skip": 3}, [], 200),
    ({"limit": 500}, ["INV-C", "INV-B", "INV-A"], 200),
    ({"skip": -1}, None, 422),
    ({"limit": 0}, None, 422),
    ({"limit": 501}, None, 422),
])
def test_bill_list_search_and_pagination(client, test_app, db_session, sale_data, params, expected, status):
    test_app.include_router(router)
    for invoice, name, active in [('INV-A', 'Alice', True), ('INV-B', 'Bob', True),
                                  ('INV-C', 'Alice', True), ('INV-D', 'Alice', False)]:
        bill = service.create_bill(db_session, BillCreate(**payload(sale_data)))
        bill.invoice_no, bill.customer_name, bill.is_active = invoice, name, active
        db_session.commit()
    response = client.get('/bills/', params=params)
    assert response.status_code == status, response.text
    if status == 200:
        assert [row['invoice_no'] for row in response.json()] == expected
