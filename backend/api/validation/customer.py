"""Validation layer for Customer entities."""
from fastapi import HTTPException, status

from api.services.gstin_identity import validate_available
from api.repository import customer as customer_repository


def validate_and_get_active_customer(db, customer_id: int):
    customer = customer_repository.get_active_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def validate_gstin_is_unique(db, gstin: str, exclude_id: int | None = None) -> None:
    validate_available(db, gstin, "customer", exclude_id)


def validate_pan_is_unique(db, pan_card: str, exclude_id: int | None = None) -> None:
    if not pan_card:
        return
    existing_pan = customer_repository.get_customer_by_pan(db, pan_card)
    if existing_pan and existing_pan.id != exclude_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PAN already exists")

