"""Master selections and historical snapshots through transaction APIs."""
from importlib import import_module

import pytest
from sqlalchemy import select
from api.config.database import Base

ROUTERS = [import_module(f'api.router.{name}').router for name in (
    'done_by', 'item_master', 'purchase', 'bill', 'quotation', 'purchase_return', 'sales_return',
)]


def snapshot(db):
    db.expire_all()
    return {table.name: [tuple(row) for row in db.execute(select(table).order_by(*table.primary_key.columns))]
            for table in Base.metadata.sorted_tables}


@pytest.fixture(params=['purchases', 'bills', 'quotations', 'purchase-returns', 'sales-returns'])
def transaction(request, client, test_app, party_api, customer_api):
    for router in ROUTERS: test_app.include_router(router)
    def post(path, payload):
        response = client.post(path, json=payload)
        assert response.status_code == 201, response.text
        return response.json()
    party = post('/parties/', party_api.create_payload())
    customer = post('/customers/', customer_api.create_payload())
    item = post('/item-master/', dict(name='LED Bulb', hsn_code='8539', unit='units', current_stock=50, sale_price=150))
    active = post('/done-by/', dict(name='Rahul'))
    other = post('/done-by/', dict(name='Amit'))
    inactive = post('/done-by/', dict(name='Former Cashier'))
    assert client.delete(f"/done-by/{inactive['id']}").status_code == 200
    module = request.param
    payload = dict(items=[dict(item_id=item['id'], item_name=item['name'], hsn_code='8539',
                              unit='units', quantity=2, price=100)], done_by='Rahul')
    if module in ['purchases', 'purchase-returns']: payload['party_id'] = party['id']
    else: payload['customer_id'] = customer['id']
    if module == 'purchases': payload['bill_no'] = 'PUR-DONE-BY'
    if module == 'bills': payload['bill_date'] = '2026-09-22'
    if 'returns' in module: payload['return_reason'] = 'Damaged'
    return dict(url=f'/{module}/', payload=payload, active=active, other=other, module=module)


def create(client, transaction):
    response = client.post(transaction['url'], json=transaction['payload'])
    assert response.status_code == 201, response.text
    data = response.json()
    return transaction['url'] + str(data.get('id', data.get('bill_id')))


def details(client, url):
    response = client.get(url)
    assert response.status_code == 200, response.text
    body = response.json()
    return body.get('bill', body)


@pytest.mark.parametrize('name,allowed', [('Rahul', True), ('Random Person', False),
    ('Former Cashier', False), ('Lalit', False), ('Darshit', False), (None, True)])
def test_create_requires_active_master(client, db_session, transaction, name, allowed):
    before = snapshot(db_session)
    response = client.post(transaction['url'], json=transaction['payload'] | dict(done_by=name))
    assert response.status_code == (201 if allowed else 400), response.text
    if not allowed:
        db_session.commit(); assert snapshot(db_session) == before
    else: assert response.json()['done_by'] == name


@pytest.mark.parametrize('echo_saved', [False, True])
def test_deactivation_preserves_unrelated_edits(client, transaction, echo_saved):
    url = create(client, transaction)
    assert client.delete(f"/done-by/{transaction['active']['id']}").status_code == 200
    assert 'Rahul' not in [row['name'] for row in client.get('/done-by/').json()]
    assert details(client, url)['done_by'] == 'Rahul'
    payload = transaction['payload'] | dict(remarks='Historical edit')
    if not echo_saved: payload.pop('done_by')
    response = client.put(url, json=payload)
    assert response.status_code == 200, response.text
    assert details(client, url)['done_by'] == 'Rahul'
    assert details(client, url)['remarks'] == 'Historical edit'


@pytest.mark.parametrize('name,allowed', [('Amit', True), ('Former Cashier', False), ('Random Person', False), (None, True)])
def test_change_selection_is_atomic_and_financially_neutral(client, db_session, transaction, name, allowed):
    url = create(client, transaction)
    before = snapshot(db_session)
    payload = transaction['payload'] | dict(done_by=name)
    response = client.put(url, json=payload if transaction['module'] == 'bills' else dict(done_by=name))
    assert response.status_code == (200 if allowed else 400), response.text
    db_session.commit()
    after = snapshot(db_session)
    if not allowed: assert after == before
    else:
        assert details(client, url)['done_by'] == name
        for table in ('item_master', 'parties', 'rojmel'):
            if table in before: assert after[table] == before[table]
        # Every stored monetary total on the original stays unchanged.
        document_table = {'purchases': 'purchases', 'bills': 'bill', 'quotations': 'quotations',
                          'purchase-returns': 'purchase_returns', 'sales-returns': 'sales_returns'}[transaction['module']]
        table = Base.metadata.tables[document_table]
        for index, column in enumerate(table.columns):
            if any(token in column.name for token in ('total', 'amount', 'round_off')):
                assert after[document_table][0][index] == before[document_table][0][index]


def test_rename_preserves_snapshot_and_changes_new_choices(client, transaction):
    url = create(client, transaction)
    response = client.patch(f"/done-by/{transaction['active']['id']}", json=dict(name='Rahul Patel'))
    assert response.status_code == 200
    assert details(client, url)['done_by'] == 'Rahul'
    unchanged = transaction['payload'] | dict(remarks='Retain old name after rename')
    assert client.put(url, json=unchanged).status_code == 200
    assert details(client, url)['done_by'] == 'Rahul'
    payload = transaction['payload'] | dict(done_by='Rahul Patel')
    response = client.put(url, json=payload)
    assert response.status_code == 200, response.text
    assert details(client, url)['done_by'] == 'Rahul Patel'


@pytest.mark.parametrize('name', ['Lalit', 'Darshit'])
def test_former_constants_work_only_as_real_master_records(client, transaction, name):
    assert client.post('/done-by/', json=dict(name=name)).status_code == 201
    response = client.post(transaction['url'], json=transaction['payload'] | dict(done_by=name))
    assert response.status_code == 201, response.text
    assert response.json()['done_by'] == name


def test_master_duplicate_names_rejected(client, test_app):
    test_app.include_router(ROUTERS[0])
    first = client.post('/done-by/', json=dict(name='Rahul')).json()
    assert client.post('/done-by/', json=dict(name='Rahul')).status_code == 400
    second = client.post('/done-by/', json=dict(name='Amit')).json()
    assert client.patch(f"/done-by/{second['id']}", json=dict(name='Rahul')).status_code == 400
    client.delete(f"/done-by/{first['id']}")
    assert client.post('/done-by/', json=dict(name='Rahul')).status_code == 400
