from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


def test_create_party_success(client: TestClient, party_api: PartyApi):
    payload = party_api.create_payload()
    response = client.post(party_api.base_url, json=payload)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["id"] == 1
    assert data["party_code"] == "PTY-0001"
    assert data["name"] == payload["name"]
    assert data["is_active"] is True


def test_create_multiple_parties_generates_unique_codes(
    client: TestClient,
    party_api: PartyApi,
):
    first = client.post(
        party_api.base_url,
        json=party_api.create_payload(name="First Party"),
    )
    second = client.post(
        party_api.base_url,
        json=party_api.create_payload(name="Second Party"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["party_code"] == "PTY-0001"
    assert second.json()["party_code"] == "PTY-0002"


def test_duplicate_party_names_are_allowed(
    client: TestClient,
    party_api: PartyApi,
):
    first = client.post(
        party_api.base_url,
        json=party_api.create_payload(name="Duplicate Traders"),
    )
    second = client.post(
        party_api.base_url,
        json=party_api.create_payload(name="Duplicate Traders"),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["name"] == second.json()["name"]
    assert first.json()["party_code"] != second.json()["party_code"]


def test_duplicate_party_addresses_are_allowed(
    client: TestClient,
    party_api: PartyApi,
):
    first = client.post(
        party_api.base_url,
        json=party_api.create_payload(
            name="First Supplier",
            address="Common Business Address",
        ),
    )
    second = client.post(
        party_api.base_url,
        json=party_api.create_payload(
            name="Second Supplier",
            address="Common Business Address",
        ),
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["address"] == second.json()["address"]


def test_party_code_from_request_is_ignored(
    client: TestClient,
    party_api: PartyApi,
):
    payload = party_api.create_payload(party_code="PTY-9999")
    response = client.post(party_api.base_url, json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["party_code"] == "PTY-0001"


def test_pan_is_extracted_from_gstin_when_pan_is_missing(
    client: TestClient,
    party_api: PartyApi,
):
    response = client.post(
        party_api.base_url,
        json=party_api.gstin_payload(),
    )

    assert response.status_code == 201, response.text
    assert response.json()["gstin"] == "24ABCDE1234F1Z5"
    assert response.json()["pan_card"] == "ABCDE1234F"
