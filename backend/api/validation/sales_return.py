"""
Business-rule validation layer for SalesReturn / SalesReturnItem
records.

Same conventions as validation/bank.py. Return/order-number
formatting and tax/total math stay in the service layer -- this
module enforces existence checks, return-number uniqueness, the
IGST-vs-CGST/SGST exclusivity rule, and the "stock already used"
guard on update.

Note: item lookups here deliberately use
get_item_by_id_any_status (no is_active filter), matching the
original service's _build_return_item, which does not filter by
active status when receiving stock back from a return.
"""

from decimal import Decimal

from fastapi import HTTPException, status

from api.repository import sales_return as sales_return_repository


def validate_and_get_active_customer(db, customer_id: int):
    customer = sales_return_repository.get_active_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def validate_and_get_sales_return(db, sales_return_id: int):
    record = sales_return_repository.get_sales_return_by_id(db, sales_return_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sales return not found")
    return record


def validate_return_number_is_unique(db, return_no: str, exclude_id: int | None = None) -> None:
    if sales_return_repository.get_sales_return_by_return_no(db, return_no, exclude_id=exclude_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sales return number already exists",
        )


def validate_gst_type_is_exclusive(sgst: float, cgst: float, igst: float) -> None:
    if igst > 0 and (sgst > 0 or cgst > 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IGST cannot be applied together with SGST or CGST",
        )


def validate_and_get_item_for_return(db, item_id: int | None, item_name: str):
    item = sales_return_repository.get_item_by_id_any_status(db, item_id) if item_id is not None else None
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{item_name}' not found",
        )
    return item


def validate_stock_not_already_used(current_stock: float, quantity_to_reverse: float, item_name: str) -> None:
    current_stock = Decimal(str(current_stock))
    quantity_to_reverse = Decimal(str(quantity_to_reverse))
    if not current_stock.is_finite():
        raise HTTPException(400, f"Cannot reverse Sales Return for {item_name}. Current stock is invalid.")
    if current_stock < quantity_to_reverse:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot reverse Sales Return for {item_name}. Reversing the Return requires removing "
                f"{quantity_to_reverse.normalize():f} units from stock, but only "
                f"{current_stock.normalize():f} units are currently available."
            ),
        )
