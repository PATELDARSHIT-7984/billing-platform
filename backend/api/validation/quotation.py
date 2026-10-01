from fastapi import HTTPException, status

from api.repository import quotation as quotation_repository


def validate_and_get_active_customer(db, customer_id: int):
    customer = quotation_repository.get_active_customer_by_id(
        db,
        customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    return customer


def validate_and_get_active_item(db, item_id: int):
    item = quotation_repository.get_active_item_by_id(
        db,
        item_id,
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active item not found",
        )

    return item


def validate_and_get_quotation(
    db,
    quotation_id: int,
    include_inactive: bool = False,
):
    quotation = quotation_repository.get_quotation_by_id(
        db,
        quotation_id,
        include_inactive=include_inactive,
    )

    if not quotation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation not found",
        )

    return quotation


def validate_quotation_number_is_unique(
    db,
    quotation_no: str,
    exclude_id: int | None = None,
) -> None:
    if quotation_repository.get_quotation_by_quotation_no(
        db,
        quotation_no,
        exclude_id=exclude_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quotation number already exists",
        )


def validate_gst_type_is_exclusive(
    sgst: float,
    cgst: float,
    igst: float,
) -> None:
    if igst > 0 and (sgst > 0 or cgst > 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IGST cannot be applied together with SGST or CGST",
        )


def validate_shipping_details(
    show_shipping_address_on_bill: bool,
    ship_to: str | None,
    ship_to_address: str | None,
    shipping_state: str | None,
) -> None:
    if not show_shipping_address_on_bill:
        return

    if not ship_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ship To is required",
        )

    if not ship_to_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ship To Address is required",
        )

    if not shipping_state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipping State is required",
        )
