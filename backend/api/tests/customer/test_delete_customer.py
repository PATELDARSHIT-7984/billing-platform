from fastapi.testclient import TestClient

from api.tests.fixtures.customer_fixtures import CustomerApi


def test_delete_customer_success(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.delete(customer_api.detail_url(created["id"]))

    assert response.status_code == 200, response.text
    assert "deleted successfully" in response.json()["message"]


def test_deleted_customer_is_not_available_by_id(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()
    client.delete(customer_api.detail_url(created["id"]))

    response = client.get(customer_api.detail_url(created["id"]))

    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_deleted_customer_is_not_returned_in_list(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()
    client.delete(customer_api.detail_url(created["id"]))

    response = client.get(customer_api.base_url)

    assert response.status_code == 200
    assert response.json() == []


def test_delete_customer_twice_returns_not_found(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()
    first = client.delete(customer_api.detail_url(created["id"]))
    second = client.delete(customer_api.detail_url(created["id"]))

    assert first.status_code == 200
    assert second.status_code == 404
    assert second.json()["detail"] == "Customer not found"


def test_delete_customer_with_invalid_id_returns_validation_error(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.delete(customer_api.detail_url("invalid"))

    assert response.status_code == 422
