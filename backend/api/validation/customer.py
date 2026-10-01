"""
Business-rule validation layer for Customer records.

Same conventions as validation/bank.py. Customer-code generation and
GSTIN/PAN normalization are not validation and stay in the service
layer -- this module only enforces "does this customer exist" and
GSTIN/PAN uniqueness across active and inactive records.
"""

from fastapi import HTTPException, status

from api.repository import customer as customer_repository


def validate_and_get_active_customer(db, customer_id: int):
    customer = customer_repository.get_active_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def validate_gstin_is_unique(db, gstin: str, exclude_id: int | None = None) -> None:
    if not gstin:
        return

    existing_gstin = customer_repository.get_customer_by_gstin(db, gstin)
    if existing_gstin and existing_gstin.id != exclude_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GSTIN already exists")


def validate_pan_is_unique(db, pan_card: str, exclude_id: int | None = None) -> None:
    if not pan_card:
        return

    existing_pan = customer_repository.get_customer_by_pan(db, pan_card)
    if existing_pan and existing_pan.id != exclude_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PAN already exists")
