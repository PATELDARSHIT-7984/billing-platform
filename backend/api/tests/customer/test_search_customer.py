import pytest
from fastapi.testclient import TestClient

from api.tests.fixtures.customer_fixtures import CustomerApi


@pytest.mark.parametrize('params', [{'skip': -1}, {'limit': 0}, {'limit': 501}])
def test_customer_pagination_bounds(client, customer_api, params):
    assert client.get(customer_api.base_url, params=params).status_code == 422


@pytest.mark.parametrize(
    "search_value",
    [
        "Unique Customer",
        "CUS-0001",
        "9876543210",
    ],
)
def test_search_customer_by_supported_fields(
    client: TestClient,
    customer_api: CustomerApi,
    search_value: str,
):
    create_response = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Unique Customer"),
    )
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        customer_api.base_url,
        params={"search": search_value},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["customer_code"] == "CUS-0001"


def test_search_customer_is_case_insensitive(
    client: TestClient,
    customer_api: CustomerApi,
):
    client.post(
        customer_api.base_url,
        json=customer_api.create_payload(customer_name="Mixed Case Customer"),
    )

    response = client.get(
        customer_api.base_url,
        params={"search": "mixed case"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_customer_no_match_returns_empty_list(
    client: TestClient,
    customer_api: CustomerApi,
):
    client.post(customer_api.base_url, json=customer_api.create_payload())

    response = client.get(
        customer_api.base_url,
        params={"search": "does-not-exist"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_customer_list_pagination(
    client: TestClient,
    customer_api: CustomerApi,
):
    for name in ["Echo", "Delta", "Charlie", "Bravo", "Alpha"]:
        client.post(
            customer_api.base_url,
            json=customer_api.create_payload(customer_name=name),
        )

    response = client.get(
        customer_api.base_url,
        params={"skip": 1, "limit": 2},
    )

    assert response.status_code == 200, response.text
    assert [item["customer_name"] for item in response.json()] == [
        "Bravo",
        "Charlie",
    ]
