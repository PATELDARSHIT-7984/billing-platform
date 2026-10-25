"""Real service/repository accounting, including flush-then-fail rollback."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from api.model.customer import Customer
from api.model.party import Party
from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster
from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.sales_return import SalesReturn, SalesReturnItem
from api.model.rojmel import Rojmel
from api.schema.bill import BillCreate, BillUpdate
from api.schema.sales_return import SalesReturnCreate, SalesReturnUpdate
from api.schema.rojmel import RojmelCreate, RojmelUpdate
from api.schema.customer import CustomerUpdate
from api.services import bill, sales_return, rojmel, customer, dashboard, quotation


@pytest.fixture
def data(db_session):
    buyers = [Customer(customer_name=name, mobile='9876543210', address='Road', city='Surat', state='Gujarat',
                       opening_balance=1000, balance_type='Debit', current_balance=1000, current_balance_type='Debit')
              for name in ['First', 'Second']]
    item = ItemMaster(name='Tile', hsn_code='1234', unit='Box', current_stock=100, sale_price=100)
    party = Party(name='Supplier', current_balance=1000)
    bank, person = BankModel(name='Cash'), DoneByModel(name='Operator')
    db_session.add_all([*buyers, item, party, bank, person]); db_session.commit()
    return buyers, item, party, bank, person


def bill_payload(data, total=5000, buyer=0, **changes):
    return dict(customer_id=data[0][buyer].id, bill_date=date.today(), is_gst=False,
                items=[dict(item_id=data[1].id, quantity=1, rate=total)]) | changes


def return_payload(data, total=1500, buyer=0, **changes):
    return dict(customer_id=data[0][buyer].id, is_gst=False, return_reason='Returned',
                items=[dict(item_id=data[1].id, item_name='Tile', hsn_code='1234', unit='Box', quantity=1, price=total)]) | changes


def receipt_payload(data, amount=2000, buyer=0, **changes):
    return dict(customer_id=data[0][buyer].id, amount=amount, transaction_type='Cr Pay', receipt_no='ignored',
                given_taken_date=date.today(), effective_date=date.today(), cash_bank_id=data[3].id,
                done_by_id=data[4].id, pay_mode='Cash') | changes


def balance(db, account):
    db.refresh(account)
    return account.current_balance * (-1 if account.current_balance_type == 'Debit' else 1)


def snapshot(db):
    db.flush()
    return {model.__tablename__: [tuple(getattr(row, col.name) for col in model.__table__.columns)
            for row in db.query(model).order_by(list(model.__table__.primary_key.columns)[0]).all()]
            for model in (Customer, Party, ItemMaster, Bill, BillItem, SalesReturn, SalesReturnItem, Rojmel)}


@pytest.mark.parametrize('total', [6000, 4000, 5000])
def test_sale_updates_only_difference(db_session, data, total):
    saved = bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    assert balance(db_session, data[0][0]) == -6000
    bill.update_bill(db_session, saved.bill_id, BillUpdate(**bill_payload(data, total, remarks='Text change')))
    assert balance(db_session, data[0][0]) == -1000-total


def test_sale_customer_switch_and_delete_once(db_session, data):
    saved = bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    bill.update_bill(db_session, saved.bill_id, BillUpdate(**bill_payload(data, buyer=1)))
    assert [balance(db_session, c) for c in data[0]] == [-1000, -6000]
    data[0][1].is_active = False; db_session.commit()
    bill.delete_bill(db_session, saved.bill_id)
    with pytest.raises(HTTPException): bill.delete_bill(db_session, saved.bill_id)
    assert [balance(db_session, c) for c in data[0]] == [-1000, -1000]


@pytest.mark.parametrize('total', [2000, 1000, 1500])
def test_return_delta_switch_and_delete(db_session, data, total):
    bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    saved = sales_return.create_sales_return(db_session, SalesReturnCreate(**return_payload(data)))
    assert balance(db_session, data[0][0]) == -4500
    sales_return.update_sales_return_by_id(db_session, saved.id, SalesReturnUpdate(**return_payload(data, total)))
    assert balance(db_session, data[0][0]) == -6000+total
    sales_return.update_sales_return_by_id(db_session, saved.id, SalesReturnUpdate(customer_id=data[0][1].id))
    assert [balance(db_session, c) for c in data[0]] == [-6000, -1000+total]
    sales_return.delete_sales_return_by_id(db_session, saved.id)
    with pytest.raises(HTTPException): sales_return.delete_sales_return_by_id(db_session, saved.id)
    assert balance(db_session, data[0][1]) == -1000


@pytest.mark.parametrize('opening,direction,expected', [('1500','Debit',-6500),('1500','Credit',-3500)])
def test_opening_edits_preserve_sale_effect(db_session, data, customer_api, opening, direction, expected):
    bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    customer.update_customer(db_session, data[0][0].id, CustomerUpdate(**customer_api.update_payload(
        opening_balance=opening, balance_type=direction)))
    assert balance(db_session, data[0][0]) == expected
    customer.update_customer(db_session, data[0][0].id, CustomerUpdate(**customer_api.update_payload(
        opening_balance='1000', balance_type='Credit')))
    customer.update_customer(db_session, data[0][0].id, CustomerUpdate(**customer_api.update_payload(
        opening_balance='1000', balance_type='Debit')))
    assert balance(db_session, data[0][0]) == -6000


@pytest.mark.parametrize('amount,kind,expected', [(500,'Cr Pay',-500),(1500,'Cr Pay',500),(500,'Dr Pay',-1500)])
def test_customer_rojmel_delta_and_direction(db_session, data, amount, kind, expected):
    saved = rojmel.create_rojmel(db_session, RojmelCreate(**receipt_payload(data, amount=amount, transaction_type=kind)))
    assert balance(db_session, data[0][0]) == expected
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(amount=250))
    assert balance(db_session, data[0][0]) == (-750 if kind=='Cr Pay' else -1250)
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(transaction_type='Dr Pay'))
    assert balance(db_session, data[0][0]) == -1250
    rojmel.delete_rojmel(db_session, saved.id)
    with pytest.raises(HTTPException): rojmel.delete_rojmel(db_session, saved.id)
    assert balance(db_session, data[0][0]) == -1000


def test_rojmel_switches_customer_party_and_unassigned(db_session, data):
    saved = rojmel.create_rojmel(db_session, RojmelCreate(**receipt_payload(data, 250)))
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(customer_id=data[0][1].id))
    assert [balance(db_session,c) for c in data[0]] == [-1000,-750]
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(customer_id=None, party_id=data[2].id, transaction_type='Dr Pay'))
    assert balance(db_session,data[0][1]) == -1000
    assert balance(db_session,data[2]) == 750
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(party_id=None, customer_id=data[0][0].id, transaction_type='Cr Pay'))
    assert balance(db_session,data[2]) == 1000
    assert balance(db_session,data[0][0]) == -750
    rojmel.update_rojmel(db_session, saved.id, RojmelUpdate(customer_id=None))
    assert balance(db_session,data[0][0]) == -1000


@pytest.mark.parametrize('change', ['both','missing','inactive','jv','cash_bank'])
def test_invalid_customer_rojmel_is_atomic(db_session, data, change):
    overrides = {'both': {'party_id':data[2].id}, 'missing':{'customer_id':999999},
                 'inactive':{}, 'jv':{'transaction_type':'JV'}, 'cash_bank':{'transaction_type':'Cash/Bank'}}[change]
    if change=='inactive': data[0][0].is_active=False; db_session.commit()
    before=snapshot(db_session)
    with pytest.raises(HTTPException): rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data,**overrides)))
    db_session.commit(); assert snapshot(db_session)==before


@pytest.mark.parametrize('domain', ['bill','return','rojmel'])
@pytest.mark.parametrize('operation', ['create','update','delete'])
def test_failure_after_balance_flush_rolls_everything_back(db_session,data,domain,operation):
    service, create, update, delete = {
        'bill': (bill, lambda:bill.create_bill(db_session,BillCreate(**bill_payload(data))),
                 lambda id:bill.update_bill(db_session,id,BillUpdate(**bill_payload(data,6000,buyer=1))), bill.delete_bill),
        'return':(sales_return,lambda:sales_return.create_sales_return(db_session,SalesReturnCreate(**return_payload(data))),
                  lambda id:sales_return.update_sales_return_by_id(db_session,id,SalesReturnUpdate(**return_payload(data,2000,buyer=1))),sales_return.delete_sales_return_by_id),
        'rojmel':(rojmel,lambda:rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data))),
                  lambda id:rojmel.update_rojmel(db_session,id,RojmelUpdate(amount=2500,customer_id=data[0][1].id)),rojmel.delete_rojmel),
    }[domain]
    saved=create() if operation!='create' else None
    id=(saved.bill_id if domain=='bill' else saved.id) if saved else None
    before=snapshot(db_session)
    original=service.replace_customer_effect
    def fail(*args,**kwargs):
        original(*args,**kwargs)
        db_session.flush()
        raise RuntimeError('Injected failure after all accounting writes')
    with patch.object(service,'replace_customer_effect',side_effect=fail):
        with pytest.raises(RuntimeError):
            if operation=='create': create()
            elif operation=='update': update(id)
            else: delete(db_session,id)
    db_session.commit(); assert snapshot(db_session)==before


def test_integrated_accounting_and_sql_dashboard(db_session,data):
    sale=bill.create_bill(db_session,BillCreate(**bill_payload(data)))
    assert balance(db_session,data[0][0])==-6000
    returned=sales_return.create_sales_return(db_session,SalesReturnCreate(**return_payload(data)))
    assert balance(db_session,data[0][0])==-4500
    first=rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data,2000)))
    assert balance(db_session,data[0][0])==-2500
    second=rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data,3000)))
    assert balance(db_session,data[0][0])==500
    data[0][0].is_active=False; db_session.commit()
    statements=[]
    def track(conn,cursor,statement,parameters,context,executemany): statements.append(statement)
    event.listen(db_session.get_bind(),'before_cursor_execute',track)
    try: totals=dashboard.summary(db_session,date.today(),date.today())
    finally: event.remove(db_session.get_bind(),'before_cursor_execute',track)
    assert totals['customer_receivable']==1000 # second Customer
    assert totals['customer_credit']==500 # includes inactive first Customer
    aggregate=[s for s in statements if 'FROM customers' in s]
    assert len(aggregate)==1 and 'sum(' in aggregate[0].lower() and 'GROUP BY' in aggregate[0]
    for entry in [second,first]: rojmel.delete_rojmel(db_session,entry.id)
    sales_return.delete_sales_return_by_id(db_session,returned.id)
    bill.delete_bill(db_session,sale.bill_id)
    assert balance(db_session,data[0][0])==-1000


def test_zero_dashboard_and_refund(db_session,data):
    receipt=rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data,1500)))
    refund=rojmel.create_rojmel(db_session,RojmelCreate(**receipt_payload(data,500,transaction_type='Dr Pay')))
    assert balance(db_session,data[0][0])==0
    assert data[0][0].current_balance_type=='Credit'
    result=dashboard.summary(db_session,date.today(),date.today())
    assert result['customer_credit']==0 and result['customer_receivable']==1000


def test_unchanged_effect_does_not_mutate_customer(db_session, data):
    saved = bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    with patch.object(customer, 'apply_customer_balance_delta') as mutation:
        bill.update_bill(db_session, saved.bill_id, BillUpdate(**bill_payload(data, remarks='Text only')))
        mutation.assert_not_called()


def test_rollback_between_old_and_new_customer_postings(db_session, data):
    saved = bill.create_bill(db_session, BillCreate(**bill_payload(data)))
    before = snapshot(db_session)
    original = customer.apply_customer_balance_delta
    def fail_second(db, customer_id, delta):
        if customer_id == data[0][1].id:
            raise RuntimeError('Second account unavailable')
        return original(db, customer_id, delta)
    with patch.object(customer, 'apply_customer_balance_delta', side_effect=fail_second):
        with pytest.raises(RuntimeError):
            bill.update_bill(db_session, saved.bill_id, BillUpdate(**bill_payload(data, buyer=1)))
    db_session.commit()
    assert snapshot(db_session) == before


def test_quotation_never_posts_customer_balance(db_session, data):
    from api.schema.quotation import QuotationCreate, QuotationUpdate
    payload = return_payload(data)
    payload.pop('return_reason')
    saved = quotation.create_quotation(db_session, QuotationCreate(**payload))
    assert balance(db_session, data[0][0]) == -1000
    quotation.update_quotation_by_id(db_session, saved.id, QuotationUpdate(remarks='Edited'))
    assert balance(db_session, data[0][0]) == -1000
    quotation.delete_quotation_by_id(db_session, saved.id)
    assert balance(db_session, data[0][0]) == -1000


def test_customer_rojmel_api_contract_and_invalid_switch(client, test_app, db_session, data):
    from api.router.rojmel import router as rojmel_router
    from api.router.dashboard import router as dashboard_router
    test_app.include_router(rojmel_router)
    test_app.include_router(dashboard_router)
    payload = RojmelCreate(**receipt_payload(data, 1500)).model_dump(mode='json')
    response = client.post('/rojmel/', json=payload)
    assert response.status_code == 201, response.text
    record = response.json()['data']
    assert record['customer_id'] == data[0][0].id and record['party_id'] is None
    db_session.expire_all()
    before = snapshot(db_session)
    response = client.patch(f"/rojmel/{record['id']}", json={'party_id': data[2].id})
    assert response.status_code == 422, response.text
    db_session.expire_all()
    assert snapshot(db_session) == before
    result = client.get('/dashboard/summary').json()
    assert Decimal(result['customer_receivable']) == 1000
    assert Decimal(result['customer_credit']) == 500


def test_inactive_historical_customer_rojmel_update_and_delete(db_session, data):
    record = rojmel.create_rojmel(db_session, RojmelCreate(**receipt_payload(data, 1500)))
    data[0][0].is_active = False
    db_session.commit()
    rojmel.update_rojmel(db_session, record.id, RojmelUpdate(amount=1000))
    assert balance(db_session, data[0][0]) == 0
    rojmel.delete_rojmel(db_session, record.id)
    assert balance(db_session, data[0][0]) == -1000
