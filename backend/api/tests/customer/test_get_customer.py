from fastapi.testclient import TestClient

from api.tests.fixtures.customer_fixtures import CustomerApi


def test_get_customer_by_id_success(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.get(customer_api.detail_url(created["id"]))

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]
    assert response.json()["customer_code"] == "CUS-0001"


def test_get_customer_not_found(client: TestClient, customer_api: CustomerApi):
    response = client.get(customer_api.detail_url(9999))

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_get_customer_with_invalid_id_returns_validation_error(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.get(customer_api.detail_url("invalid"))

    assert response.status_code == 422
    assert "customer_id" in response.text


def test_get_customer_list_empty(client: TestClient, customer_api: CustomerApi):
    response = client.get(customer_api.base_url)

    assert response.status_code == 200
    assert response.json() == []


def test_get_customer_list_success(
    client: TestClient,
    customer_api: CustomerApi,
):
    client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Bravo Customer"),
    )
    client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Alpha Customer"),
    )

    response = client.get(customer_api.base_url)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert response.json()[0]["customer_name"] == "Alpha Customer"
    assert response.json()[1]["customer_name"] == "Bravo Customer"
