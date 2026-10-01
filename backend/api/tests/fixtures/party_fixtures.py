"""Reusable URLs and payload builders for Party API tests."""

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass(frozen=True, slots=True)
class PartyApi:
    base_url: str = "/parties/"

    def detail_url(self, party_id: int | str) -> str:
        return f"/parties/{party_id}"

    def create_payload(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Shree Ram Traders",
            "party_type": "Supplier",
            "country_code": "+91",
            "mobile": "9876543210",
            "address": "Satellite Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "gstin": None,
            "pan_card": None,
            "opening_balance": "0.00",
            "balance_type": "Credit",
            "opening_remark": "Created by automated test",
        }
        payload.update(overrides)
        return payload

    def update_payload(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Updated Shree Ram Traders",
            "mobile": "9876543211",
            "address": "Updated Satellite Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "opening_remark": "Updated by automated test",
        }
        payload.update(overrides)
        return payload

    def gstin_payload(self, **overrides: Any) -> dict[str, Any]:
        payload = self.create_payload(
            name="GST Registered Party",
            mobile="9876543212",
            gstin="24ABCDE1234F1Z5",
            pan_card=None,
        )
        payload.update(overrides)
        return payload


@pytest.fixture
def party_api() -> PartyApi:
    return PartyApi()
