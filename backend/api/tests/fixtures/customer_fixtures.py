"""Reusable URLs and payload builders for Customer API tests."""

from dataclasses import dataclass
from typing import Any

import pytest


@dataclass(frozen=True, slots=True)
class CustomerApi:
    base_url: str = "/customers/"

    def detail_url(self, customer_id: int | str) -> str:
        return f"/customers/{customer_id}"

    def create_payload(self, **overrides: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "customer_name": "Gunjan Patel",
            "mobile": "9876543210",
            "email": "gunjan@example.com",
            "address": "Satellite Road",
            "city": "Ahmedabad",
            "state": "Gujarat",
            "pincode": "380015",
            "gstin": None,
            "pan_card": None,
            "state_code": "24",
            "remarks": "Created by automated test",
        }
        payload.update(overrides)
        return payload

    def update_payload(self, **overrides: Any) -> dict[str, Any]:
        payload = self.create_payload(
            customer_name="Updated Gunjan Patel",
            mobile="9876543211",
            email="updated@example.com",
            address="Updated Satellite Road",
            remarks="Updated by automated test",
        )
        payload.update(overrides)
        return payload

    def gstin_payload(self, **overrides: Any) -> dict[str, Any]:
        payload = self.create_payload(
            customer_name="GST Registered Customer",
            mobile="9876543212",
            email="gst.customer@example.com",
            gstin="24ABCDE1234F1Z5",
            pan_card=None,
        )
        payload.update(overrides)
        return payload


@pytest.fixture
def customer_api() -> CustomerApi:
    return CustomerApi()
