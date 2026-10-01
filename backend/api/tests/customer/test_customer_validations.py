import pytest
from fastapi.testclient import TestClient

from api.tests.fixtures.customer_fixtures import CustomerApi


def test_create_customer_rejects_duplicate_gstin(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(customer_api.base_url, json=customer_api.gstin_payload())
    second = client.post(
        customer_api.base_url,
        json=customer_api.gstin_payload(
            customer_name="Another Customer",
            mobile="9876543213",
            email="another@example.com",
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 400
    assert second.json()["detail"] == "GSTIN already exists"


def test_create_customer_rejects_duplicate_pan(
    client: TestClient,
    customer_api: CustomerApi,
):
    first = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(pan_card="ABCDE1234F"),
    )
    second = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            customer_name="Another Customer",
            mobile="9876543213",
            email="another@example.com",
            pan_card="ABCDE1234F",
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 400
    assert second.json()["detail"] == "PAN already exists"


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"customer_name": "A"}, "customer_name"),
        ({"mobile": "1234567890"}, "mobile"),
        ({"mobile": "98765"}, "mobile"),
        ({"email": "not-an-email"}, "email"),
        ({"address": "A"}, "address"),
        ({"city": ""}, "city"),
        ({"state": ""}, "state"),
        ({"gstin": "INVALIDGSTIN"}, "gstin"),
        ({"pan_card": "ABC"}, "pan_card"),
    ],
)
def test_create_customer_schema_validation_errors(
    client: TestClient,
    customer_api: CustomerApi,
    overrides: dict,
    expected_field: str,
):
    response = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(**overrides),
    )

    assert response.status_code == 422
    assert expected_field in response.text


@pytest.mark.parametrize(
    "required_field",
    [
        "customer_name",
        "mobile",
        "address",
        "city",
        "state",
    ],
)
def test_create_customer_requires_mandatory_fields(
    client: TestClient,
    customer_api: CustomerApi,
    required_field: str,
):
    payload = customer_api.create_payload()
    payload.pop(required_field)

    response = client.post(customer_api.base_url, json=payload)

    assert response.status_code == 422
    assert required_field in response.text


def test_customer_gstin_and_pan_are_normalized_to_uppercase(
    client: TestClient,
    customer_api: CustomerApi,
):
    response = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(
            gstin="24abcde1234f1z5",
            pan_card="abcde1234f",
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["gstin"] == "24ABCDE1234F1Z5"
    assert response.json()["pan_card"] == "ABCDE1234F"


def test_update_customer_rejects_invalid_mobile(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.put(
        customer_api.detail_url(created["id"]),
        json=customer_api.update_payload(mobile="123"),
    )

    assert response.status_code == 422
    assert "mobile" in response.text


def test_update_customer_rejects_invalid_gstin(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.put(
        customer_api.detail_url(created["id"]),
        json=customer_api.update_payload(gstin="INVALIDGSTIN"),
    )

    assert response.status_code == 422
    assert "gstin" in response.text


def test_update_customer_rejects_invalid_pan(
    client: TestClient,
    customer_api: CustomerApi,
):
    created = client.post(
        customer_api.base_url,
        json=customer_api.create_payload(),
    ).json()

    response = client.put(
        customer_api.detail_url(created["id"]),
        json=customer_api.update_payload(pan_card="ABC"),
    )

    assert response.status_code == 422
    assert "pan_card" in response.text
