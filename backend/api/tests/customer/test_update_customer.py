from fastapi.testclient import TestClient
import pytest

from api.tests.fixtures.customer_fixtures import CustomerApi


def test_update_keeps_own_normalized_tax_ids(client, customer_api):
    created = client.post(customer_api.base_url, json=customer_api.gstin_payload()).json()
    response = client.put(customer_api.detail_url(created['id']), json=customer_api.update_payload(
        gstin=' 24abcde1234f1z5 ', pan_card=' abcde1234f '))
    assert response.status_code == 200, response.text
    assert response.json()['gstin'] == '24ABCDE1234F1Z5'
    assert response.json()['pan_card'] == 'ABCDE1234F'


@pytest.mark.parametrize('field,value,message', [
    ('gstin', '24ABCDE1234F1Z5', 'GSTIN already exists'),
    ('pan_card', 'ABCDE1234F', 'PAN already exists'),
])
@pytest.mark.parametrize('operation', ['create', 'update'])
def test_inactive_tax_ids_remain_reserved(client, customer_api, field, value, message, operation):
    owner = client.post(customer_api.base_url, json=customer_api.create_payload(**{field: value})).json()
    assert client.delete(customer_api.detail_url(owner['id'])).status_code == 200
    if operation == 'create':
        response = client.post(customer_api.base_url, json=customer_api.create_payload(**{field: value}))
    else:
        other = client.post(customer_api.base_url, json=customer_api.create_payload()).json()
        response = client.put(customer_api.detail_url(other['id']),
                              json=customer_api.update_payload(**{field: value}))
        assert client.get(customer_api.detail_url(other['id'])).json() == other
    assert response.status_code == 400, response.text
    assert response.json()['detail'] == message


@pytest.mark.parametrize('field,value', [
    ('customer_name', 'A'), ('customer_name', 'A' * 101),
    ('address', 'A'), ('city', ''), ('state', ''),
])
def test_update_reuses_create_field_constraints(client, customer_api, field, value):
    created = client.post(customer_api.base_url, json=customer_api.create_payload()).json()
    response = client.put(customer_api.detail_url(created['id']),
                          json=customer_api.update_payload(**{field: value}))
    assert response.status_code == 422
    assert client.get(customer_api.detail_url(created['id'])).json() == created


def test_update_customer_success(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()
    update_payload = customer_api.update_payload()

    response = client.put(
        customer_api.detail_url(created["id"]),
        json=update_payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["customer_name"] == update_payload["customer_name"]
    assert data["mobile"] == update_payload["mobile"]
    assert data["email"] == update_payload["email"]


def test_customer_code_cannot_be_changed_during_update(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    update_payload = customer_api.update_payload(customer_code="CUS-9999")
    response = client.put(
        customer_api.detail_url(created["id"]),
        json=update_payload,
    )

    assert response.status_code == 200, response.text
    assert response.json()["customer_code"] == created["customer_code"]


def test_update_customer_not_found(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.put(
        customer_api.detail_url(9999),
        json=customer_api.update_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_update_customer_with_invalid_id_returns_validation_error(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.put(
        customer_api.detail_url("invalid"),
        json=customer_api.update_payload(),
    )

    assert response.status_code == 422


def test_update_customer_rejects_invalid_email(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.put(
        customer_api.detail_url(created["id"]),
        json=customer_api.update_payload(email="not-an-email"),
    )

    assert response.status_code == 422
    assert "email" in response.text


def test_update_customer_rejects_another_customers_gstin(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.gstin_payload(),
    ).json()
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            customer_name="Second Customer",
            mobile="9876543213",
            email="second@example.com",
        ),
    ).json()

    response = client.put(
        customer_api.detail_url(second["id"]),
        json=customer_api.update_payload(
            customer_name="Second Customer Updated",
            mobile="9876543213",
            email="second@example.com",
            gstin=first["gstin"],
            pan_card=None,
        ),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "GSTIN already exists"


def test_update_customer_rejects_another_customers_pan(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(pan_card="ABCDE1234F"),
    ).json()
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            customer_name="Second Customer",
            mobile="9876543213",
            email="second@example.com",
        ),
    ).json()

    response = client.put(
        customer_api.detail_url(second["id"]),
        json=customer_api.update_payload(
            customer_name="Second Customer Updated",
            mobile="9876543213",
            email="second@example.com",
            pan_card=first["pan_card"],
        ),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PAN already exists"
