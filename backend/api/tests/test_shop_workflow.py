"""One shop workflow through public APIs; ORM access is read-only verification."""
from decimal import Decimal
from importlib import import_module

from sqlalchemy import select
from api.config.database import Base
from api.model.bill import Bill
from api.model.purchase_return import PurchaseReturn
from api.model.sales_return import SalesReturn


ROUTERS = [import_module(f'api.router.{name}').router for name in (
    'item_master', 'purchase', 'purchase_return', 'bill', 'sales_return',
    'rojmel', 'bank', 'done_by',
)]


def test_complete_shop_workflow(client, test_app, db_session, party_api, customer_api):
    for router in ROUTERS:
        test_app.include_router(router)

    def api(method, path, payload=None):
        response = client.request(method, path, json=payload) if payload is not None else client.request(method, path)
        assert response.status_code in (200, 201), response.text
        body = response.json()
        return body['data'] if path.startswith('/rojmel') else body

    def snapshot():
        db_session.expire_all()
        return {table.name: [tuple(row) for row in db_session.execute(select(table).order_by(*table.primary_key.columns))]
                for table in Base.metadata.sorted_tables}

    def reject(method, path, payload=None, message=None):
        before = snapshot()
        response = client.request(method, path, json=payload) if payload is not None else client.request(method, path)
        assert response.status_code in (400, 404), response.text
        if message: assert message in response.json()['detail']
        db_session.commit()  # A later commit must not persist partial changes.
        assert snapshot() == before

    # 1-2: Master records, created using the same APIs as the shop UI.
    supplier = api('POST', '/parties/', party_api.create_payload(name='ABC Electronics'))
    supplier_url = f"/parties/{supplier['id']}"
    assert supplier['party_code'] and Decimal(str(supplier['opening_balance'])) == 0
    item = api('POST', '/item-master/', dict(name='LED Bulb', code='LED-001', hsn_code='8539',
        unit='units', current_stock=0, purchase_price=100, sale_price=150, cgst=9, sgst=9))
    item_url = f"/item-master/{item['id']}"

    def state(stock, payable):
        actual = api('GET', item_url)
        party = api('GET', supplier_url)
        assert actual['current_stock'] == stock and stock >= 0
        assert actual['is_active'] and party['is_active']
        assert Decimal(str(party['opening_balance'])) == 0
        assert Decimal(str(party['current_balance'])) == payable
        assert party['current_balance_type'] == 'Credit'

    def line(quantity, price=100):
        return dict(item_id=item['id'], item_name='LED Bulb', hsn_code='8539', unit='units',
                    quantity=quantity, price=price, cgst=9, sgst=9, igst=0)

    def history(path, expected):
        page = api('GET', path + '?page=1&page_size=20')
        assert page['total'] == expected and len(page['items']) == expected
        assert page['page'] == 1 and page['page_size'] == 20
        assert page['total_pages'] == (1 if expected else 0)
        return page['items']

    state(0, Decimal(0))
    # 3: Purchase 20, then pay 500 through Rojmel (4).
    purchase = api('POST', '/purchases/', dict(bill_no='PUR-SHOP-001', party_id=supplier['id'],
        is_gst=True, items=[line(20)]))
    purchase_url = f"/purchases/{purchase['id']}"
    purchase_total = Decimal(str(purchase['grand_total']))
    state(20, purchase_total)
    assert history('/purchases/', 1)[0]['id'] == purchase['id']
    # Required existing Rojmel lookup records; no changes to their behavior.
    bank = api('POST', '/banks/', dict(name='Cash'))
    operator = api('POST', '/done-by/', dict(name='Shop Owner'))
    payment = api('POST', '/rojmel/', dict(transaction_type='Dr Pay', party_id=supplier['id'],
        amount=500, receipt_no='AUTO', given_taken_date='2026-09-17', effective_date='2026-09-17',
        cash_bank_id=bank['id'], done_by_id=operator['id'], pay_mode='Cash'))
    paid = Decimal(str(payment['amount']))
    assert paid == 500
    state(20, purchase_total - paid)
    assert history('/rojmel/', 1)[0]['id'] == payment['id']

    # 5-7: Reduce Purchase, return three, reject reducing below returned quantity.
    purchase = api('PUT', purchase_url, dict(items=[line(18)]))
    purchase_total = Decimal(str(purchase['grand_total']))
    state(18, purchase_total - paid)
    purchase_return = api('POST', '/purchase-returns/', dict(party_id=supplier['id'],
        original_bill_no=purchase['bill_no'], return_reason='Damaged packaging', items=[line(3)]))
    pr_url = f"/purchase-returns/{purchase_return['id']}"
    return_total = Decimal(str(purchase_return['grand_total']))
    payable = purchase_total - paid - return_total
    state(15, payable)
    assert history('/purchase-returns/', 1)[0]['id'] == purchase_return['id']
    assert purchase['items'][0]['quantity'] - purchase_return['items'][0]['quantity'] == 15
    reject('PUT', purchase_url, dict(items=[line(2)]), 'already been returned')
    state(15, payable)

    # 8-9: Create and edit Customer; inventory and supplier payable stay intact.
    customer = api('POST', '/customers/', customer_api.create_payload(customer_name='Rahul Patel'))
    customer_url = f"/customers/{customer['id']}"
    assert api('GET', customer_url)['customer_name'] == 'Rahul Patel'
    customer = api('PUT', customer_url, customer_api.update_payload(
        customer_name='Rahul Patel', mobile='9876543211', address='Updated Shop Road'))
    assert customer['address'] == 'Updated Shop Road'
    state(15, payable)

    def sale_payload(quantity):
        return dict(customer_id=customer['id'], bill_date='2026-09-17', is_gst=True,
            items=[dict(item_id=item['id'], quantity=quantity, rate=150,
                        disc_percent=0, cgst=9, sgst=9, igst=0)])

    # 10-12: Sell five, increase to seven, reject thirteen additional units.
    sale = api('POST', '/bills/', sale_payload(5))
    sale_url = f"/bills/{sale['bill_id']}"
    assert sale['invoice_no']
    detail = api('GET', sale_url)
    assert detail['bill']['customer_name'] == 'Rahul Patel'
    assert detail['bill']['address'] == 'Updated Shop Road'
    assert detail['items'][0]['rate'] == 150
    assert Decimal(str(detail['bill']['grand_total'])) == Decimal('885')
    state(10, payable)
    assert history('/bills/', 1)[0]['bill_id'] == sale['bill_id']
    detail = api('PUT', sale_url, sale_payload(7))
    assert detail['items'][0]['quantity'] == 7
    assert Decimal(str(detail['bill']['grand_total'])) == Decimal('1239')
    state(8, payable)
    reject('PUT', sale_url, sale_payload(20), 'Additional quantity')
    state(8, payable)

    # 13-16: Return two; block excess returns, invalid original edits and deletion.
    return_payload = dict(customer_id=customer['id'], original_invoice_no=sale['invoice_no'],
                          return_reason='Customer return', items=[line(2, 150)])
    sales_return = api('POST', '/sales-returns/', return_payload)
    sr_url = f"/sales-returns/{sales_return['id']}"
    state(10, payable)
    assert detail['items'][0]['quantity'] - sales_return['items'][0]['quantity'] == 5
    assert history('/sales-returns/', 1)[0]['id'] == sales_return['id']
    reject('POST', '/sales-returns/', return_payload | dict(items=[line(6, 150)]), 'Remaining returnable quantity: 5')
    reject('PUT', sale_url, sale_payload(1), 'already been returned')
    reject('DELETE', sale_url, message='active Sales Returns')
    state(10, payable)

    # 17-19: Reverse Return, Sale, then Purchase Return; each effect occurs once.
    api('DELETE', sr_url)
    state(8, payable)
    assert db_session.get(SalesReturn, sales_return['id']).is_active is False
    api('DELETE', sale_url)
    state(15, payable)
    assert db_session.get(Bill, sale['bill_id']).is_active is False
    reject('DELETE', sale_url)
    api('DELETE', pr_url)
    state(18, purchase_total - paid)
    assert db_session.get(PurchaseReturn, purchase_return['id']).is_active is False
    reject('DELETE', pr_url)

    # 20-24: Final documents, history, masters and exact accounting invariant.
    final_purchase = api('GET', purchase_url)
    assert final_purchase['is_active'] and final_purchase['items'][0]['quantity'] == 18
    for path, count in [('/purchases/', 1), ('/purchase-returns/', 0), ('/bills/', 0),
                        ('/sales-returns/', 0), ('/rojmel/', 1)]:
        history(path, count)
    assert api('GET', f"/rojmel/{payment['id']}") == payment
    final_customer = api('GET', customer_url)
    assert final_customer['is_active'] and final_customer['address'] == 'Updated Shop Road'
    assert final_customer['mobile'] == '9876543211'
    state(18, Decimal(str(final_purchase['grand_total'])) - paid)
    print(f"Supplier {supplier['id']}/{supplier['party_code']}; item {item['id']}; "
          f"invoice {sale['invoice_no']}; purchase total {purchase_total}; "
          f"purchase return total {return_total}; final payable {purchase_total - paid}; stock 18")
