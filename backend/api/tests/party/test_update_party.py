from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


def test_update_party_success(client: TestClient, party_api: PartyApi):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()
    update_payload = party_api.update_payload()

    response = client.put(
        party_api.detail_url(created["id"]),
        json=update_payload,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == update_payload["name"]
    assert data["mobile"] == update_payload["mobile"]


def test_partial_party_update_keeps_unchanged_fields(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()

    response = client.put(
        party_api.detail_url(created["id"]),
        json={"name": "Only Name Changed"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Only Name Changed"
    assert data["mobile"] == created["mobile"]
    assert data["address"] == created["address"]


def test_party_code_cannot_be_changed_during_update(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()

    response = client.put(
        party_api.detail_url(created["id"]),
        json={"name": "Updated Name", "party_code": "PTY-9999"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["party_code"] == created["party_code"]


def test_update_party_with_its_existing_gstin_is_allowed(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.gstin_payload()).json()

    response = client.put(
        party_api.detail_url(created["id"]),
        json={"name": "Updated GST Party", "gstin": created["gstin"]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["gstin"] == created["gstin"]


def test_update_party_rejects_another_partys_gstin(
    client: TestClient,
    party_api: PartyApi,
):
    first = client.post(party_api.base_url, json=party_api.gstin_payload()).json()
    second = client.post(
        party_api.base_url,
        json=party_api.create_payload(name="Second Party"),
    ).json()

    response = client.put(
        party_api.detail_url(second["id"]),
        json={"gstin": first["gstin"]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "GSTIN already exists"


def test_update_party_not_found(client: TestClient, party_api: PartyApi):
    response = client.put(
        party_api.detail_url(9999),
        json=party_api.update_payload(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Party not found"


def test_update_party_invalid_id_returns_validation_error(
    client: TestClient,
    party_api: PartyApi,
):
    response = client.put(
        party_api.detail_url("invalid"),
        json=party_api.update_payload(),
    )

    assert response.status_code == 422
