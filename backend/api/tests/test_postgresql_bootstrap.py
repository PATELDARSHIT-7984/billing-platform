"""Opt-in smoke test of an already migrated, disposable PostgreSQL database."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from api.config.database import Base, DATABASE_URL
from api.dependencies import dependencies
from api.main import app


def test_migrated_postgresql_application(monkeypatch):
    database = os.environ.get('BILLING_BOOTSTRAP_TEST_DATABASE')
    if not database:
        pytest.skip('Set BILLING_BOOTSTRAP_TEST_DATABASE to a migrated disposable database')
    assert database.startswith('billing_test_bootstrap_'), 'Refusing a non-test database'
    engine = create_engine(make_url(DATABASE_URL).set(database=database))
    monkeypatch.setattr(dependencies, 'SessionLocal', sessionmaker(bind=engine))
    token = uuid4().hex[:12]
    try:
        with engine.connect() as connection:
            assert connection.execute(text('SELECT current_database()')).scalar_one() == database
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'c4a9e7120d35'
            assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) | {'alembic_version'}
        with TestClient(app) as client:
            assert client.get('/health').json() == {'status': 'ok'}
            response = client.post('/parties/', json={'name': 'Bootstrap ' + token, 'opening_balance': 1500})
            assert response.status_code == 201, response.text
            party = response.json()
            assert float(party['current_balance']) == 1500
            response = client.post('/customers/', json={
                'customer_name': 'Bootstrap ' + token, 'mobile': '9876543210',
                'address': 'Test address', 'city': 'Ahmedabad', 'state': 'Gujarat'})
            assert response.status_code == 201, response.text
            customer = response.json()
            response = client.post('/item-master/', json={
                'name': 'Bootstrap ' + token, 'hsn_code': '6907', 'unit': 'Box',
                'current_stock': 10, 'sale_price': 100})
            assert response.status_code == 201, response.text
            item = response.json()
            response = client.post('/bills/', json={
                'customer_id': customer['id'], 'bill_date': '2026-09-16',
                'items': [{'item_id': item['id'], 'quantity': 1, 'rate': 100}]})
            assert response.status_code == 201, response.text
            bill = response.json()
            assert client.get(f"/bills/{bill['bill_id']}").json()['bill']['grand_total'] == 118
            response = client.post('/purchases/', json={
                'bill_no': 'BOOT-' + token, 'party_id': party['id'],
                'items': [{'item_id': item['id'], 'item_name': item['name'],
                           'hsn_code': '6907', 'unit': 'Box', 'quantity': 2, 'price': 100.5}]})
            assert response.status_code == 201, response.text
            purchase = response.json()
            assert client.get(f"/purchases/{purchase['id']}").status_code == 200
            assert float(client.get(f"/parties/{party['id']}").json()['current_balance']) == 1701
            assert client.get(f"/item-master/{item['id']}").json()['current_stock'] == 11
        with engine.connect() as connection:
            assert connection.execute(text("SELECT nextval('party_code_seq')")).scalar_one() > int(party['party_code'].split('-')[1])
            assert connection.execute(text("SELECT nextval('customer_code_seq')")).scalar_one() > int(customer['customer_code'].split('-')[1])
    finally:
        engine.dispose()
