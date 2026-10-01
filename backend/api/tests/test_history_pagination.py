"""Real HTTP, repository and SQL pagination checks across all six histories."""
from datetime import date
from importlib import import_module

import pytest
from sqlalchemy import event

from api.model.bank import BankModel
from api.model.bill import Bill
from api.model.bill_item import BillItem  # registers relationship
from api.model.customer import Customer
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster  # registers relationship
from api.model.party import Party
from api.model.purchase import Purchase
from api.model.purchase_return import PurchaseReturn
from api.model.quotation import Quotation
from api.model.rojmel import Rojmel
from api.model.sales_return import SalesReturn


MODULES = [
    ('bill', '/bills/', Bill, 'invoice_no', 'bill_id'),
    ('purchase', '/purchases/', Purchase, 'bill_no', 'id'),
    ('sales_return', '/sales-returns/', SalesReturn, 'return_no', 'id'),
    ('purchase_return', '/purchase-returns/', PurchaseReturn, 'return_no', 'id'),
    ('quotation', '/quotations/', Quotation, 'quotation_no', 'id'),
    ('rojmel', '/rojmel/', Rojmel, 'receipt_no', 'id'),
]


@pytest.fixture(params=MODULES, ids=[row[0] for row in MODULES])
def history(request, db_session, test_app, customer_api):
    name, url, model, number, pk = request.param
    test_app.include_router(import_module(f'api.router.{name}').router)
    customer = Customer(**customer_api.create_payload(customer_name='Buyer Needle'))
    party = Party(name='Supplier Needle', party_type='Supplier')
    bank, person = BankModel(name='Cash'), DoneByModel(name='Operator')
    db_session.add_all([customer, party, bank, person])
    db_session.flush()
    for index in range(1, 206):
        values = {number: f"{'MATCH' if index % 2 else 'OTHER'}-{index:04}"}
        if model is Bill:
            values.update(customer_id=customer.id, customer_name=customer.customer_name,
                          bill_date=date(2026, 1, 1), mobile='9876543210', address='Street',
                          city='Ahmedabad', state='Gujarat', total_boxes=0, subtotal=0,
                          taxable_amount=0, grand_total=0, amount_in_words='Zero')
        elif model is Rojmel:
            values.update(party_id=party.id if index % 2 else None, cash_bank_id=bank.id,
                          done_by_id=person.id, transaction_type='Dr Pay', pay_mode='Cash',
                          given_taken_date=date(2026, 1, 1),
                          effective_date=date(2026, 1, 1 if index <= 100 else 2))
        elif model in (Purchase, PurchaseReturn):
            values['party_id'] = party.id
        else:
            values['customer_id'] = customer.id
        if model in (SalesReturn, PurchaseReturn):
            values['return_reason'] = 'Test return'
        # The inactive newest record must never enter either count or page rows.
        if model is not Rojmel:
            values['is_active'] = index != 205
        db_session.add(model(**values))
    db_session.commit()
    return dict(name=name, url=url, model=model, pk=pk, party=party.id,
                total=205 if model is Rojmel else 204)


def get_page(client, history, **params):
    response = client.get(history['url'], params={'page': 1, **params})
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload['data'] if history['name'] == 'rojmel' else payload


def test_pages_are_bounded_stable_and_complete(client, history, test_engine):
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))
    event.listen(test_engine, 'before_cursor_execute', capture)
    try:
        first = get_page(client, history)
    finally:
        event.remove(test_engine, 'before_cursor_execute', capture)
    assert first['total'] == history['total']
    assert first['page_size'] == 20
    assert first['total_pages'] == 11
    assert len(first['items']) == 20
    assert first == get_page(client, history)
    second = get_page(client, history, page=2)
    ids = [row[history['pk']] for row in first['items'] + second['items']]
    assert ids == list(range(history['total'], history['total'] - 40, -1))
    # Capture the actual parent SELECT: count is unbounded, rows are SQL-bounded.
    table = history['model'].__tablename__
    queries = [(sql.upper(), args) for sql, args in statements if f'FROM {table}' in sql]
    assert any('COUNT(' in sql and 'LIMIT' not in sql for sql, _ in queries)
    row_queries = [(sql, args) for sql, args in queries if 'COUNT(' not in sql]
    assert len(row_queries) == 1
    sql, args = row_queries[0]
    assert 'ORDER BY' in sql and 'LIMIT' in sql and 'OFFSET' in sql
    assert args[-2:] == (20, 0)


def test_search_totals_empty_and_out_of_range(client, history):
    expected = 103 if history['name'] == 'rojmel' else 102
    first = get_page(client, history, search='MATCH', page_size=20)
    second = get_page(client, history, search='MATCH', page=2, page_size=20)
    assert first['total'] == second['total'] == expected
    ids = [row[history['pk']] for row in first['items'] + second['items']]
    assert ids == list(range(expected * 2 - 1, expected * 2 - 81, -2))
    empty = get_page(client, history, search='NO-SUCH-RECORD')
    assert empty['items'] == [] and empty['total'] == empty['total_pages'] == 0
    beyond = get_page(client, history, page=999)
    assert beyond['items'] == [] and beyond['total'] == history['total']
    if history['name'] != 'rojmel':
        by_party = get_page(client, history, search='Needle', page=2)
        assert by_party['total'] == history['total']
        assert len(by_party['items']) == 20


def test_maximum_size_and_legacy_list(client, history):
    maximum = get_page(client, history, page_size=200)
    assert len(maximum['items']) == 200
    assert maximum['total_pages'] == 2
    if history['name'] != 'rojmel':
        legacy = client.get(history['url'], params={'search': 'MATCH', 'skip': 2, 'limit': 3})
        assert legacy.status_code == 200
        assert isinstance(legacy.json(), list) and len(legacy.json()) == 3
        assert [row[history['pk']] for row in legacy.json()] == [199, 197, 195]


@pytest.mark.parametrize('params', [{'page': 0}, {'page_size': 0}, {'page_size': 201}])
def test_query_bounds(client, history, params):
    assert client.get(history['url'], params={'page': 1, **params}).status_code == 422


@pytest.mark.parametrize('history', [MODULES[-1]], indirect=True, ids=['rojmel'])
def test_rojmel_business_filters(client, history):
    filters = dict(start_date='2026-01-02', end_date='2026-01-02', party_id=history['party'])
    first = get_page(client, history, **filters)
    second = get_page(client, history, page=2, **filters)
    assert first['total'] == second['total'] == 53
    ids = [row['id'] for row in first['items'] + second['items']]
    assert ids == list(range(205, 125, -2))
