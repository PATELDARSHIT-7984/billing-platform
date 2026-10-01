from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


def test_delete_party_success(client: TestClient, party_api: PartyApi):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()

    response = client.delete(party_api.detail_url(created["id"]))

    assert response.status_code == 200, response.text
    assert "deleted successfully" in response.json()["message"]


def test_deleted_party_is_not_available_by_id(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()
    client.delete(party_api.detail_url(created["id"]))

    response = client.get(party_api.detail_url(created["id"]))

    assert response.status_code == 404
    assert response.json()["detail"] == "Party not found"


def test_deleted_party_is_not_returned_in_list(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()
    client.delete(party_api.detail_url(created["id"]))

    response = client.get(party_api.base_url)

    assert response.status_code == 200
    assert response.json() == []


def test_delete_party_twice_returns_not_found(
    client: TestClient,
    party_api: PartyApi,
):
    created = client.post(party_api.base_url, json=party_api.create_payload()).json()
    first = client.delete(party_api.detail_url(created["id"]))
    second = client.delete(party_api.detail_url(created["id"]))

    assert first.status_code == 200
    assert second.status_code == 404
    assert second.json()["detail"] == "Party not found"


def test_delete_party_with_invalid_id_returns_validation_error(
    client: TestClient,
    party_api: PartyApi,
):
    response = client.delete(party_api.detail_url("invalid"))

    assert response.status_code == 422
