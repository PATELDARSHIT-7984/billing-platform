from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster  # registers relationship targets
from api.model.bill_item import BillItem
from api.model.party import Party
from api.model.customer import Customer
from api.model.purchase import Purchase
from api.model.purchase_return import PurchaseReturn
from api.model.bill import Bill
from api.model.sales_return import SalesReturn
from api.model.rojmel import Rojmel, TransactionType
from api.router.dashboard import router
from api.services import dashboard as service

START, END = date(2026, 9, 1), date(2026, 9, 30)


@pytest.fixture
def accounts(db_session):
    suppliers = [Party(name=f'Supplier {i}', mobile=f'987650000{i}', address=f'Patel Road {i}',
                       gstin=f'24ABCDE{i:08}', current_balance=100 * (i + 1),
                       current_balance_type='Debit' if i == 6 else 'Credit') for i in range(7)]
    customers = [Customer(customer_name=f'Customer {i}', mobile=f'876540000{i}',
                          address=f'Gandhi Road {i}', city='Surat', state='Gujarat', gstin=f'24CUSTM{i:08}') for i in range(7)]
    db_session.add_all(suppliers + customers + [Party(name='Customer Party', party_type='Customer', current_balance=99999)])
    db_session.flush()
    return suppliers, customers


def document(db, model, partner, amount, day=START, active=True):
    common = dict(grand_total=amount, is_active=active)
    number = f'{model.__name__}-{db.query(model).count() + 1}'
    if model is Bill:
        common.update(invoice_no=number, customer_id=partner.id, bill_date=day, customer_name=partner.customer_name,
                      mobile=partner.mobile, address=partner.address, city=partner.city, state=partner.state,
                      total_boxes=0, subtotal=amount, taxable_amount=amount, amount_in_words='Test')
    elif model is Purchase:
        common.update(bill_no=number, party_id=partner.id, bill_date=day)
    else:
        common.update(return_no=number, return_date=day, return_reason='Test')
        common['party_id' if model is PurchaseReturn else 'customer_id'] = partner.id
    row = model(**common)
    db.add(row)
    db.flush()
    return row


def test_summary_totals_and_current_balances(db_session, accounts):
    suppliers, customers = accounts
    for model, partner, amount in [(Purchase, suppliers[0], 1000), (PurchaseReturn, suppliers[0], 120),
                                   (Bill, customers[0], 2000), (SalesReturn, customers[0], 200)]:
        document(db_session, model, partner, amount)
        document(db_session, model, partner, 999, date(2026, 8, 31))
        document(db_session, model, partner, 999, active=False)
    suppliers[0].is_active = False
    db_session.flush()
    result = service.summary(db_session, START, END)
    for key, expected in dict(total_purchase=1000, total_purchase_return=120, net_purchase=880,
                              total_sales=2000, total_sales_return=200, net_sales=1800,
                              supplier_payable=2100, supplier_advance=700,
                              sales_return_rate=10, purchase_return_rate=12).items():
        assert result[key] == Decimal(expected)
    assert result['customer_receivable'] is None
    assert service.summary(db_session, date(2000, 1, 1), date(2000, 1, 2))['supplier_payable'] == 2100


def test_empty_and_zero_rates(db_session):
    result = service.summary(db_session, START, END)
    for key in ('total_purchase', 'total_sales', 'net_purchase', 'net_sales', 'supplier_payable',
                'supplier_advance', 'total_received', 'total_paid', 'net_cash_flow', 'sales_return_rate', 'purchase_return_rate'):
        assert result[key] == 0
    assert service.recent_transactions(db_session, START, END) == []


@pytest.mark.parametrize('type,search', [
    ('supplier', 'sUPPLIER 6'), ('supplier', '9876500006'), ('supplier', 'pATEL Road 6'), ('supplier', '24abcde00000006'),
    ('customer', 'cUSTOMER 6'), ('customer', '8765400006'), ('customer', 'gANDHI Road 6'), ('customer', '24custm00000006'),
])
def test_global_search_beyond_first_five(db_session, accounts, type, search):
    first = service.accounts(db_session, type=type)
    assert len(first['items']) == 5
    found = service.accounts(db_session, type=type, search=search)
    assert found['total'] == 1
    assert found['items'][0]['id'] not in [row['id'] for row in first['items']]
    if type == 'customer':
        assert found['items'][0]['current_balance'] is None


@pytest.mark.parametrize('balance,expected', [('all', 7), ('payable', 6), ('advance', 1)])
def test_balance_filter(db_session, accounts, balance, expected):
    assert service.accounts(db_session, balance_type=balance)['total'] == expected


@pytest.mark.parametrize('sort,first', [('balance_desc', 'Supplier 6'), ('balance_asc', 'Supplier 0'),
                                      ('name_asc', 'Supplier 0'), ('name_desc', 'Supplier 6')])
def test_sort_and_pagination(db_session, accounts, sort, first):
    result = service.accounts(db_session, sort=sort)
    assert result['items'][0]['name'] == first
    assert len(service.accounts(db_session, skip=5)['items']) == 2


@pytest.mark.parametrize('type', ['supplier', 'customer'])
def test_partner_net_ranking(db_session, accounts, type):
    suppliers, customers = accounts
    partners, sale, ret = (suppliers, Purchase, PurchaseReturn) if type == 'supplier' else (customers, Bill, SalesReturn)
    for i, partner in enumerate(partners):
        document(db_session, sale, partner, (i + 1) * 100)
    document(db_session, sale, partners[0], 50)
    document(db_session, ret, partners[6], 690)
    document(db_session, ret, partners[5], 900)
    document(db_session, sale, partners[0], 9000, date(2026, 8, 1))
    result = service.top_partners(db_session, START, END, type)
    assert len(result['items']) == 5
    assert result['total'] == 7
    assert result['items'][0]['id'] == partners[4].id
    assert result['items'][0]['net_amount'] == 500
    assert result['items'][-1]['net_amount'] == 150
    assert service.top_partners(db_session, START, END, type, search=partners[5].mobile)['items'][0]['net_amount'] == -300


def test_cash_flow_uses_net_and_effective_date(db_session, accounts):
    bank, person = BankModel(name='Cash'), DoneByModel(name='Admin')
    db_session.add_all([bank, person])
    db_session.flush()
    for i, (kind, amount, day) in enumerate([(TransactionType.CR_PAY, 120, START), (TransactionType.DR_PAY, 45, START),
                                           (TransactionType.CASH_BANK, 1000, START), (TransactionType.JV, 2000, START),
                                           (TransactionType.CR_PAY, 999, date(2026, 8, 1))]):
        db_session.add(Rojmel(receipt_no=f'R{i}', transaction_type=kind, effective_date=day, given_taken_date=date(2020, 1, 1),
                             cash_bank_id=bank.id, done_by_id=person.id, pay_mode='Cash', amount=1, net_amount=amount))
    db_session.flush()
    result = service.summary(db_session, START, END)
    assert (result['total_received'], result['total_paid'], result['net_cash_flow']) == (120, 45, 75)
    assert any(row['type'] == 'Cr Pay' for row in service.recent_transactions(db_session, START, END))


def test_recent_all_sources_and_limit(db_session, accounts):
    suppliers, customers = accounts
    for day, model, partner in [(1, Purchase, suppliers[0]), (2, Bill, customers[0]),
                                (3, PurchaseReturn, suppliers[0]), (4, SalesReturn, customers[0]),
                                (5, Purchase, suppliers[0]), (6, Bill, customers[0])]:
        document(db_session, model, partner, 10, date(2026, 9, day))
    rows = service.recent_transactions(db_session, START, END)
    assert len(rows) == 5
    assert [row['date'].day for row in rows] == [6, 5, 4, 3, 2]


def test_monthly_trend_fills_gaps_and_filters(db_session, accounts):
    suppliers, customers = accounts
    document(db_session, Bill, customers[0], 0.1)
    document(db_session, Bill, customers[0], 0.2)
    document(db_session, Purchase, suppliers[0], 55)
    result = service.trend(db_session, date(2026, 8, 1), END)
    assert result['labels'] == ['Aug 2026', 'Sep 2026']
    assert result['sales'] == [0, Decimal('0.30')]
    assert result['purchase'] == [0, 55]


@pytest.mark.parametrize('period,today,expected', [('today', date(2026, 9, 13), date(2026, 9, 13)),
    ('week', date(2026, 9, 13), date(2026, 9, 7)), ('month', date(2026, 9, 13), START),
    ('financial_year', date(2026, 3, 31), date(2025, 4, 1)), ('financial_year', date(2026, 4, 1), date(2026, 4, 1))])
def test_presets(period, today, expected):
    assert service.date_range(period, today=today) == (expected, today)


def test_endpoints_validation_and_decimal_contract(test_app, client):
    test_app.include_router(router)
    for endpoint in ('summary', 'accounts', 'top-partners', 'trend', 'recent-transactions'):
        response = client.get('/dashboard/' + endpoint)
        assert response.status_code == 200, response.text
    assert client.get('/dashboard/summary').json()['total_sales'] == '0.00'
    for suffix in ('accounts?limit=0', 'accounts?skip=-1', 'accounts?sort=unsafe',
                   'summary?period=custom', 'summary?period=custom&start_date=2026-09-30&end_date=2026-09-01'):
        assert client.get('/dashboard/' + suffix).status_code == 422

def test_return_only_partner_and_literal_search(db_session, accounts):
    suppliers, _ = accounts
    document(db_session, PurchaseReturn, suppliers[0], 75)
    result = service.top_partners(db_session, START, END)
    assert result['items'][0]['net_amount'] == -75
    assert service.accounts(db_session, search='%')['total'] == 0
    assert service.accounts(db_session, search='Customer Party')['total'] == 0
    assert service.accounts(db_session, type='customer', search='Supplier')['total'] == 0


def test_dashboard_reads_do_not_write(db_session, accounts):
    from sqlalchemy import event
    statements = []
    engine = db_session.get_bind()
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        service.summary(db_session, START, END)
        service.accounts(db_session)
        service.top_partners(db_session, START, END)
        service.trend(db_session, START, END)
        service.recent_transactions(db_session, START, END)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert statements and set(statements) == {'SELECT'}

@pytest.mark.parametrize('period', ['today', 'week', 'month', 'financial_year', 'custom'])
def test_trend_respects_explicit_period(test_app, client, period):
    test_app.include_router(router)
    params = {'period': period}
    if period == 'custom':
        params.update(start_date='2026-01-12', end_date='2026-02-03')
    selected = client.get('/dashboard/summary', params=params).json()
    response = client.get('/dashboard/trend', params=params)
    assert response.status_code == 200
    assert response.json()['start_date'] == selected['start_date']
    assert response.json()['end_date'] == selected['end_date']


@pytest.mark.parametrize('params,six_months', [({}, True), ({'last_six_months': 'false'}, False),
    ({'period': 'custom', 'start_date': '2026-01-12', 'end_date': '2026-02-03', 'last_six_months': 'true'}, True),
    ({'period': 'custom', 'start_date': '2026-01-12', 'end_date': '2026-02-03', 'last_six_months': 'false'}, False)])
def test_trend_default_and_explicit_chart_mode(test_app, client, params, six_months):
    test_app.include_router(router)
    result = client.get('/dashboard/trend', params=params).json()
    end = date.fromisoformat(result['end_date'])
    if six_months:
        month_index = end.year * 12 + end.month - 1 - 5
        expected = date(month_index // 12, month_index % 12 + 1, 1)
        assert len(result['labels']) == 6
    else:
        expected = date.fromisoformat(params['start_date']) if 'start_date' in params else end.replace(day=1)
    assert result['start_date'] == expected.isoformat()
