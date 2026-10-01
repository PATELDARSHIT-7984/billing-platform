"""
Business-rule validation layer for Bill / BillItem records.

Same conventions as validation/bank.py. Invoice-number generation,
GST math, and amount-in-words conversion stay in the service layer --
this module enforces existence checks and stock sufficiency.
"""

from math import isfinite

from fastapi import HTTPException, status

from api.repository import bill as bill_repository


def validate_and_get_active_customer(db, customer_id: int):
    customer = bill_repository.get_active_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def validate_and_get_active_item(db, item_id: int):
    item = bill_repository.get_active_item_by_id(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found",
        )
    return item


def validate_sufficient_stock(item, requested_quantity: int, *, additional: bool = False) -> None:
    current_stock = float(item.current_stock or 0.0)
    if not isfinite(current_stock):
        raise HTTPException(400, f"Cannot sell {item.name}. Current stock is invalid; correct Item Master stock first.")
    if requested_quantity > current_stock:
        quantity_label = "Additional quantity required" if additional else "Requested quantity"
        available = str(current_stock).removesuffix(".0")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot sell {item.name}. {quantity_label} is {requested_quantity} units, "
                f"but only {available} units are available."
            ),
        )


def validate_and_get_active_bill(db, bill_id: int):
    bill = bill_repository.get_bill_by_id(db, bill_id)
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bill with ID {bill_id} not found",
        )
    return bill
