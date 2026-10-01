from fastapi.testclient import TestClient

from api.tests.fixtures.customer_fixtures import CustomerApi


def test_create_customer_success(client: TestClient, customer_api: CustomerApi):
    payload = customer_api.create_payload()
    response = client.post(customer_api.base_url, json=payload)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["id"] == 1
    assert data["customer_code"] == "CUS-0001"
    assert data["customer_name"] == payload["customer_name"]
    assert data["is_active"] is True


def test_create_multiple_customers_generates_unique_codes(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="First Customer"),
    )
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Second Customer"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["customer_code"] == "CUS-0001"
    assert second.json()["customer_code"] == "CUS-0002"


def test_duplicate_customer_names_are_allowed(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Duplicate Customer"),
    )
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Duplicate Customer"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["customer_name"] == second.json()["customer_name"]
    assert first.json()["customer_code"] != second.json()["customer_code"]


def test_duplicate_customer_addresses_are_allowed(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            customer_name="First Customer",
            address="Common Customer Address",
        ),
    )
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            customer_name="Second Customer",
            address="Common Customer Address",
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["address"] == second.json()["address"]


def test_customer_code_from_request_is_ignored(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_code="CUS-9999"),
    )

    assert response.status_code == 201, response.text
    assert response.json()["customer_code"] == "CUS-0001"


def test_pan_is_extracted_from_gstin_when_pan_is_missing(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.post(
        customer_api.base_url,
        json=customer_api.gstin_payload(),
    )

    assert response.status_code == 201, response.text
    assert response.json()["gstin"] == "24ABCDE1234F1Z5"
    assert response.json()["pan_card"] == "ABCDE1234F"
