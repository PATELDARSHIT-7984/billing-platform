"""
Business-rule validation layer for PurchaseReturn / PurchaseReturnItem
records.

Same conventions as validation/bank.py. Return/order-number
formatting and tax/total math stay in the service layer -- this
module enforces existence checks, return-number uniqueness, the
IGST-vs-CGST/SGST exclusivity rule, and stock sufficiency.
"""

from decimal import Decimal

from fastapi import HTTPException, status

from api.repository import purchase_return as purchase_return_repository


def validate_and_get_active_party(db, party_id: int):
    party = purchase_return_repository.get_active_party_by_id(db, party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return party


def validate_and_get_purchase_return(db, record_id: int):
    record = purchase_return_repository.get_purchase_return_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase return not found")
    return record


def validate_return_number_is_unique(db, return_no: str, exclude_id: int | None = None) -> None:
    if purchase_return_repository.get_purchase_return_by_return_no(db, return_no, exclude_id=exclude_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase return number already exists",
        )


def validate_gst_type_is_exclusive(sgst: float, cgst: float, igst: float) -> None:
    if igst > 0 and (sgst > 0 or cgst > 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IGST cannot be used together with SGST or CGST",
        )


def validate_and_get_active_item(db, item_id: int, item_name: str):
    item = purchase_return_repository.get_active_item_by_id(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{item_name}' not found",
        )
    return item


def validate_sufficient_stock(item, requested_quantity: Decimal, *, additional: bool = False) -> None:
    current_stock = Decimal(str(item.current_stock or 0))
    if not current_stock.is_finite():
        raise HTTPException(400, f"Cannot return {item.name}. Current stock is invalid.")
    if requested_quantity > current_stock:
        label = "Additional quantity required" if additional else "Requested quantity"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"Cannot return {item.name}. {label} is {requested_quantity.normalize():f} units, "
                    f"but only {current_stock.normalize():f} units are currently available."),
        )
