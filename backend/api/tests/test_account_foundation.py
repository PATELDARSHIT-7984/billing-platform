from decimal import Decimal

import pytest

from api.model.customer import Customer


@pytest.mark.parametrize('amount,direction,current_type', [
    ('0', 'Credit', 'Credit'), ('0', 'Debit', 'Credit'),
    ('125.50', 'Credit', 'Credit'), ('125.50', 'Debit', 'Debit'),
])
def test_customer_opening_balance(client, customer_api, amount, direction, current_type):
    response = client.post('/customers/', json=customer_api.create_payload(
        opening_balance=amount, balance_type=direction))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert Decimal(saved['opening_balance']) == Decimal(amount)
    assert Decimal(saved['current_balance']) == Decimal(amount)
    assert saved['balance_type'] == direction
    assert saved['current_balance_type'] == current_type
    assert client.get(customer_api.detail_url(saved['id'])).json() == saved


@pytest.mark.parametrize('old_type,new_amount,new_type,expected,direction', [
    ('Credit', '1200', 'Credit', '1700', 'Credit'),
    ('Credit', '1200', 'Debit', '700', 'Debit'),
    ('Debit', '1200', 'Credit', '1700', 'Credit'),
    ('Debit', '500', 'Debit', '0', 'Credit'),
])
def test_customer_opening_delta_preserves_other_effects(client, customer_api, db_session,
                                                       old_type, new_amount, new_type, expected, direction):
    saved = client.post('/customers/', json=customer_api.create_payload(
        opening_balance='1000', balance_type=old_type)).json()
    customer = db_session.get(Customer, saved['id'])
    # Simulate an existing signed +500 effect; this task adds no posting service.
    customer.current_balance = Decimal('1500' if old_type == 'Credit' else '500')
    customer.current_balance_type = old_type
    db_session.commit()
    response = client.put(customer_api.detail_url(saved['id']), json=customer_api.update_payload(
        opening_balance=new_amount, balance_type=new_type))
    assert response.status_code == 200, response.text
    assert Decimal(response.json()['current_balance']) == Decimal(expected)
    assert response.json()['current_balance_type'] == direction


def test_old_customer_clients_preserve_balance_and_cannot_override_current(client, customer_api):
    saved = client.post('/customers/', json=customer_api.create_payload(
        opening_balance='42', balance_type='Debit', current_balance='999')).json()
    assert Decimal(saved['current_balance']) == 42
    response = client.put(customer_api.detail_url(saved['id']), json=customer_api.update_payload(
        current_balance='999', current_balance_type='Credit'))
    assert response.status_code == 200, response.text
    assert Decimal(response.json()['opening_balance']) == 42
    assert Decimal(response.json()['current_balance']) == 42
    assert response.json()['current_balance_type'] == 'Debit'


@pytest.mark.parametrize('overrides', [
    {'opening_balance': '-1'}, {'opening_balance': 'NaN'}, {'opening_balance': 'Infinity'},
    {'opening_balance': '-Infinity'}, {'opening_balance': None},
    {'opening_balance': '0.001'}, {'opening_balance': '10000000000000000'},
    {'balance_type': 'Invalid'}, {'balance_type': None},
])
def test_customer_balance_validation(client, customer_api, overrides):
    assert client.post('/customers/', json=customer_api.create_payload(**overrides)).status_code == 422
    saved = client.post('/customers/', json=customer_api.create_payload()).json()
    assert client.put(customer_api.detail_url(saved['id']), json=customer_api.update_payload(**overrides)).status_code == 422


@pytest.mark.parametrize('party_type', ['Supplier', 'PURCHASE_VENDOR', 'Customer'])
@pytest.mark.parametrize('gstin', [None, '', '24ABCDE1234F1Z5'])
def test_party_classification_preserves_existing_rules(client, party_api, party_type, gstin):
    response = client.post('/parties/', json=party_api.create_payload(
        party_type=party_type, gstin=gstin, opening_balance='100', balance_type='Debit'))
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['party_type'] == party_type
    assert Decimal(saved['current_balance']) == 100
    assert saved['current_balance_type'] == 'Debit'
    updated = client.put(party_api.detail_url(saved['id']), json={'name': 'Renamed'})
    assert updated.json()['party_type'] == party_type
    assert client.get(party_api.detail_url(saved['id'])).status_code == 200


def test_purchase_vendor_tax_validation_and_inactive_uniqueness(client, party_api):
    assert client.post('/parties/', json=party_api.create_payload(
        party_type='PURCHASE_VENDOR', gstin='bad')).status_code == 422
    payload = party_api.gstin_payload(party_type='PURCHASE_VENDOR')
    saved = client.post('/parties/', json=payload).json()
    assert client.delete(party_api.detail_url(saved['id'])).status_code == 200
    assert client.post('/parties/', json=payload).status_code == 400
    assert client.get('/parties/', params={'party_type': 'PURCHASE_VENDOR'}).json() == []


def test_party_filters_search_pages_and_legacy_arrays(client, party_api):
    for kind in ['Supplier', 'PURCHASE_VENDOR', 'Customer']:
        for i in range(3):
            client.post('/parties/', json=party_api.create_payload(name=f'Match {i}', party_type=kind))
    assert len(client.get('/parties/').json()) == 9
    for kind in ['Supplier', 'PURCHASE_VENDOR', 'Customer']:
        data = client.get('/parties/', params={'party_type': kind, 'search': 'Match', 'page': 2, 'page_size': 2}).json()
        assert data['total'] == 3 and data['total_pages'] == 2
        assert len(data['items']) == 1 and data['items'][0]['party_type'] == kind
        assert len(client.get('/parties/', params={'party_type': kind, 'skip': 1, 'limit': 1}).json()) == 1
    assert client.get('/parties/', params={'party_type': 'PURCHASE_VENDOR', 'search': 'absent', 'page': 1}).json()['total'] == 0
    assert client.get('/parties/', params={'party_type': 'Invalid'}).status_code == 422


def test_customer_pagination_defaults_ties_search_and_inactive(client, customer_api):
    ids = []
    for _ in range(3):
        response = client.post('/customers/', json=customer_api.create_payload(customer_name='Same Name'))
        assert response.status_code == 201
        assert Decimal(response.json()['current_balance']) == 0
        ids.append(response.json()['id'])
    client.post('/customers/', json=customer_api.create_payload(customer_name='Other Name'))
    data = client.get('/customers/', params={'search': 'Same', 'page': 2, 'page_size': 2}).json()
    assert data['total'] == 3 and data['items'][0]['id'] == ids[2]
    assert isinstance(client.get('/customers/').json(), list)
    client.delete(customer_api.detail_url(ids[0]))
    assert client.get('/customers/', params={'search': 'Same', 'page': 1}).json()['total'] == 2
    assert client.get('/customers/', params={'search': 'absent', 'page': 1}).json()['total'] == 0


@pytest.mark.parametrize('endpoint', ['/parties/', '/customers/'])
@pytest.mark.parametrize('params', [{'page': 0}, {'page_size': 201}, {'limit': 501}, {'skip': -1}])
def test_management_pagination_bounds(client, endpoint, params):
    assert client.get(endpoint, params=params).status_code == 422
