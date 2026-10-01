import pytest
from fastapi.testclient import TestClient

from api.tests.fixtures.party_fixtures import PartyApi


@pytest.mark.parametrize(
    "search_value",
    [
        "Unique Party",
        "PTY-0001",
        "9876543212",
        "Ahmedabad",
        "Gujarat",
        "24ABCDE1234F1Z5",
        "ABCDE1234F",
    ],
)
def test_search_party_by_supported_fields(
    client: TestClient,
    party_api: PartyApi,
    search_value: str,
):
    create_response = client.post(
        party_api.base_url,
        json=party_api.gstin_payload(name="Unique Party"),
    )
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        party_api.base_url,
        params={"search": search_value},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["party_code"] == "PTY-0001"


def test_search_party_is_case_insensitive(
    client: TestClient,
    party_api: PartyApi,
):
    client.post(
        party_api.base_url,
        json=party_api.create_payload(name="Mixed Case Traders"),
    )

    response = client.get(
        party_api.base_url,
        params={"search": "mixed case"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_party_no_match_returns_empty_list(
    client: TestClient,
    party_api: PartyApi,
):
    client.post(party_api.base_url, json=party_api.create_payload())

    response = client.get(
        party_api.base_url,
        params={"search": "does-not-exist"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_party_list_pagination(client: TestClient, party_api: PartyApi):
    for index in range(5):
        client.post(
            party_api.base_url,
            json=party_api.create_payload(name=f"Party {index}"),
        )

    response = client.get(
        party_api.base_url,
        params={"skip": 1, "limit": 2},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert [item["party_code"] for item in response.json()] == [
        "PTY-0004",
        "PTY-0003",
    ]
