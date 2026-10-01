from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


def test_get_party_by_id_success(client: TestClient, party_api: PartyApi):
    created = client.post(party_api.base_url, json=party_api.create_payload())
    party_id = created.json()["id"]

    response = client.get(party_api.detail_url(party_id))

    assert response.status_code == 200, response.text
    assert response.json()["id"] == party_id
    assert response.json()["party_code"] == "PTY-0001"


def test_get_party_not_found(client: TestClient, party_api: PartyApi):
    response = client.get(party_api.detail_url(9999))

    assert response.status_code == 404
    assert response.json()["detail"] == "Party not found"


def test_get_party_with_invalid_id_returns_validation_error(
    client: TestClient,
    party_api: PartyApi,
):
    response = client.get(party_api.detail_url("invalid"))

    assert response.status_code == 422
    assert "party_id" in response.text


def test_get_party_list_empty(client: TestClient, party_api: PartyApi):
    response = client.get(party_api.base_url)

    assert response.status_code == 200
    assert response.json() == []


def test_get_party_list_success(client: TestClient, party_api: PartyApi):
    client.post(party_api.base_url, json=party_api.create_payload(name="First"))
    client.post(party_api.base_url, json=party_api.create_payload(name="Second"))

    response = client.get(party_api.base_url)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert response.json()[0]["party_code"] == "PTY-0002"
    assert response.json()[1]["party_code"] == "PTY-0001"
