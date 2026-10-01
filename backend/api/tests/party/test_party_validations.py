import pytest
from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


def test_create_party_rejects_duplicate_gstin(
    client: TestClient,
    party_api: PartyApi,
):
    first = client.post(party_api.base_url, json=party_api.gstin_payload())
    second = client.post(
        party_api.base_url,
        json=party_api.gstin_payload(
            name="Another Party",
            mobile="9876543213",
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 400
    assert second.json()["detail"] == "GSTIN already exists"


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"name": "A"}, "name"),
        ({"party_type": "Invalid"}, "party_type"),
        ({"balance_type": "Invalid"}, "balance_type"),
        ({"gstin": "123"}, "gstin"),
        ({"pan_card": "ABC"}, "pan_card"),
        ({"opening_balance": "not-a-number"}, "opening_balance"),
    ],
)
def test_create_party_schema_validation_errors(
    client: TestClient,
    party_api: PartyApi,
    overrides: dict,
    expected_field: str,
):
    response = client.post(
        party_api.base_url,
        json=party_api.create_payload(**overrides),
    )

    assert response.status_code == 422
    assert expected_field in response.text


def test_create_party_requires_name(client: TestClient, party_api: PartyApi):
    payload = party_api.create_payload()
    payload.pop("name")

    response = client.post(party_api.base_url, json=payload)

    assert response.status_code == 422
    assert "name" in response.text


def test_gstin_and_pan_are_normalized_to_uppercase(
    client: TestClient,
    party_api: PartyApi,
):
    response = client.post(
        party_api.base_url,
        json=party_api.create_payload(
            gstin="24abcde1234f1z5",
            pan_card="abcde1234f",
        ),
    )

    assert response.status_code == 201, response.text
    assert response.json()["gstin"] == "24ABCDE1234F1Z5"
    assert response.json()["pan_card"] == "ABCDE1234F"
