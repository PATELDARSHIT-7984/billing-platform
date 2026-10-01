"""
Business-rule validation layer for Purchase / PurchaseItem records.

Same conventions as validation/bank.py. Due-date math and tax/total
calculations are not validation and stay in the service layer -- this
module enforces existence checks, bill-number uniqueness, the
mandatory-HSN-code rule, and the IGST-vs-CGST/SGST exclusivity rule.
"""

from decimal import Decimal

from fastapi import HTTPException, status

from api.repository import bill as bill_repository
from api.repository import purchase as purchase_repository


def validate_and_get_active_purchase(db, purchase_id: int):
    purchase = purchase_repository.get_purchase_by_id(db, purchase_id)
    if not purchase:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase with ID {purchase_id} not found",
        )
    return purchase


def validate_and_get_active_party(db, party_id: int):
    party = purchase_repository.get_active_party_by_id(db, party_id)
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Party with ID {party_id} not found",
        )
    return party


def validate_and_get_active_item(db, item_id: int):
    item = purchase_repository.get_active_item_by_id(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found",
        )
    return item


def validate_bill_number_is_unique(db, bill_no: str, exclude_purchase_id: int | None = None) -> None:
    if purchase_repository.get_purchase_by_bill_no(db, bill_no, exclude_id=exclude_purchase_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bill number '{bill_no}' already exists",
        )


def validate_hsn_code_present(hsn_code: str, item_name: str) -> None:
    if not hsn_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HSN Code is required for item '{item_name}'",
        )


def validate_gst_type_is_exclusive(sgst: float, cgst: float, igst: float) -> None:
    if igst > 0 and (sgst > 0 or cgst > 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IGST cannot be applied together with CGST or SGST",
        )

def validate_purchase_stock_adjustment(
    db,
    item_id: int,
    item_name: str,
    current_stock: float,
    old_quantity: Decimal,
    new_quantity: Decimal,
) -> float:
    """Return the checked aggregate stock; invoice history is context on failure only."""
    available = Decimal(str(current_stock or 0))
    resulting_stock = available + (new_quantity - old_quantity)

    if resulting_stock < 0:
        message = (
            f"Cannot reduce {item_name} purchase quantity from {old_quantity.normalize():f} "
            f"to {new_quantity.normalize():f}. This update requires removing "
            f"{(old_quantity - new_quantity).normalize():f} units, but only "
            f"{available.normalize():f} units are currently available."
        )
        invoices, remaining = bill_repository.get_active_invoice_references_for_item(db, item_id)
        if invoices:
            message += " Related active Sales invoices containing this item: " + ", ".join(invoices)
            if remaining:
                message += f" and {remaining} more"
            message += "."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return float(resulting_stock)
