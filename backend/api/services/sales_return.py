from api.validation.done_by import validate_done_by_snapshot
from api.utils.rounding import round_half_up
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.sales_return import SalesReturn
from api.repository import sales_return as sales_return_repo
from api.schema.sales_return import (
    SalesReturnCreate,
    SalesReturnUpdate,
)
from api.validation import sales_return as sales_return_validation


# =============================================================================
# CUSTOMER NAME
# =============================================================================

def _customer_name(customer) -> str:
    """
    Returns the customer display name.
    """

    return (
        getattr(
            customer,
            "customer_name",
            None,
        )
        or getattr(
            customer,
            "name",
            None,
        )
        or "Unknown"
    )


# =============================================================================
# NUMBER GENERATION
# =============================================================================

def _next_number(
    db: Session,
    column,
    prefix: str,
) -> str:
    """
    Generates the next sequential Sales Return number.

    Example:
        SR-0001
        SR-0002

        SRO-0001
        SRO-0002
    """

    last_value = (
        sales_return_repo
        .get_last_column_value(
            db,
            column,
        )
    )

    if not last_value:
        return f"{prefix}-0001"

    digits = "".join(
        character
        for character in str(last_value)
        if character.isdigit()
    )

    next_number = (
        int(digits or 0)
        + 1
    )

    return (
        f"{prefix}-"
        f"{next_number:04d}"
    )


def get_next_sales_return_numbers(
    db: Session,
) -> dict:
    """
    Returns next Sales Return and order numbers.
    """

    return {
        "return_no": _next_number(
            db,
            SalesReturn.return_no,
            "SR",
        ),
        "order_no": _next_number(
            db,
            SalesReturn.order_no,
            "SRO",
        ),
    }


# =============================================================================
# CALCULATE TOTALS
# =============================================================================

def _calculate_sales_return_totals(
    items,
    is_gst: bool = True,
) -> tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    list[dict],
]:
    """
    Calculates Sales Return totals.

    If is_gst=False:
        SGST = 0
        CGST = 0
        IGST = 0
    """

    taxable_total = 0.0
    sgst_total = 0.0
    cgst_total = 0.0
    igst_total = 0.0

    lines = []

    for item in items:

        discount_rate = float(
            item.disc_percent
            or 0.0
        )

        # ---------------------------------------------------------------------
        # GST
        # ---------------------------------------------------------------------

        if is_gst:

            sgst_rate = float(
                item.sgst
                or 0.0
            )

            cgst_rate = float(
                item.cgst
                or 0.0
            )

            igst_rate = float(
                item.igst
                or 0.0
            )

        else:

            sgst_rate = 0.0
            cgst_rate = 0.0
            igst_rate = 0.0

        sales_return_validation.validate_gst_type_is_exclusive(
            sgst_rate,
            cgst_rate,
            igst_rate,
        )

        quantity = float(
            item.quantity
            or 0.0
        )

        price = float(
            item.price
            or 0.0
        )

        gross = (
            quantity
            * price
        )

        discount = (
            gross
            * discount_rate
            / 100
        )

        taxable = (
            gross
            - discount
        )

        sgst_amount = (
            taxable
            * sgst_rate
            / 100
        )

        cgst_amount = (
            taxable
            * cgst_rate
            / 100
        )

        igst_amount = (
            taxable
            * igst_rate
            / 100
        )

        amount = (
            taxable
            + sgst_amount
            + cgst_amount
            + igst_amount
        )

        taxable_total += taxable
        sgst_total += sgst_amount
        cgst_total += cgst_amount
        igst_total += igst_amount

        lines.append(
            {
                "amount": round_half_up(
                    amount,
                    2,
                ),
                "sgst": sgst_rate,
                "cgst": cgst_rate,
                "igst": igst_rate,
            }
        )

    net_total = (
        taxable_total
        + sgst_total
        + cgst_total
        + igst_total
    )

    grand_total = round_half_up(
        net_total, 0
    )

    round_off = (
        grand_total
        - net_total
    )

    return (
        round_half_up(
            taxable_total,
            2,
        ),
        round_half_up(
            sgst_total,
            2,
        ),
        round_half_up(
            cgst_total,
            2,
        ),
        round_half_up(
            igst_total,
            2,
        ),
        round_half_up(
            round_off,
            2,
        ),
        round_half_up(
            grand_total,
            2,
        ),
        lines,
    )


# =============================================================================
# GROUP QUANTITIES
# =============================================================================

def _group_item_quantities(
    items,
) -> dict[int, Decimal]:
    """
    Groups quantities by ItemMaster item_id.

    Prevents duplicate lines from causing incorrect
    stock calculations.

    Example:

        item 2 = 5
        item 2 = 3

    Result:

        {
            2: 8
        }
    """

    quantities = defaultdict(
        Decimal
    )

    for item in items:

        if item.item_id is None:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "item_id is required "
                    "for Sales Return items."
                ),
            )

        quantities[
            item.item_id
        ] += Decimal(str(item.quantity))

    return dict(
        quantities
    )


# =============================================================================
# RESPONSE FIELDS
# =============================================================================

def _attach_history_fields(
    record: SalesReturn,
) -> SalesReturn:
    """
    Adds runtime fields required by list/detail responses.
    """

    record.customer_name = (
        _customer_name(
            record.customer
        )
        if record.customer
        else "Unknown"
    )

    record.item_count = len(
        record.items
    )

    record.item_names = [
        item.item_name
        for item in record.items
    ]

    record.hsn_codes = [
        item.hsn_code
        for item in record.items
    ]

    record.total_boxes = sum(
        float(
            item.quantity
            or 0.0
        )
        for item in record.items
    )

    return record


# =============================================================================
# VALIDATE CREATE ITEMS
# =============================================================================

def _validate_create_items(
    db: Session,
    items,
) -> dict:
    """
    Validates all Sales Return items before stock is changed.

    Sales Return CREATE adds stock, therefore no stock sufficiency
    check is needed here.

    We only verify that ItemMaster references are valid.
    """

    item_objects = {}

    for item_data in items:

        if item_data.item_id is None:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "item_id is required "
                    "for Sales Return items."
                ),
            )

        item_master = (
            sales_return_validation
            .validate_and_get_item_for_return(
                db,
                item_data.item_id,
                item_data.item_name,
            )
        )

        item_objects[
            item_data.item_id
        ] = item_master

    return item_objects


# =============================================================================
# VALIDATE UPDATE STOCK
# =============================================================================

def _validate_update_stock(
    db: Session,
    old_quantities: dict[int, Decimal],
    new_quantities: dict[int, Decimal],
) -> dict:
    """
    Sales Return adds stock.

    Correct update formula:

        resulting_stock
            = current_stock
            - old_return_quantity
            + new_return_quantity

    This validation matters when reducing/removing a Sales Return.

    Example:

        Old Sales Return = 10
        Current stock    = 4
        New Sales Return = 2

        resulting_stock =
            4 - 10 + 2
            = -4

    The returned stock has already been consumed,
    so the edit must be rejected.
    """

    all_item_ids = (
        set(
            old_quantities.keys()
        )
        | set(
            new_quantities.keys()
        )
    )

    item_objects = {}

    for item_id in all_item_ids:

        item_master = (
            sales_return_repo
            .get_item_by_id_any_status(
                db,
                item_id,
            )
        )

        if not item_master:

            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Item with ID "
                    f"{item_id} not found."
                ),
            )

        reversal = old_quantities.get(item_id, Decimal(0)) - new_quantities.get(item_id, Decimal(0))
        sales_return_validation.validate_stock_not_already_used(
            item_master.current_stock or 0, reversal, item_master.name,
        )

        item_objects[
            item_id
        ] = item_master

    return item_objects


# =============================================================================
# CREATE SALES RETURN
# =============================================================================

def _validate_original_invoice(db, invoice_no, customer_id, items, exclude_id=None):
    reference = (invoice_no or "").strip().upper()
    if not reference:
        return None  # Standalone returns are explicitly supported by the current UI.
    bill = sales_return_repo.get_active_bill_by_invoice_no(db, reference)
    if bill is None:
        raise HTTPException(400, f"Active Sales invoice {reference} not found.")
    if bill.customer_id != customer_id:
        raise HTTPException(400, f"Invoice {reference} does not belong to the selected Customer.")
    sold = _group_item_quantities([row for row in bill.bill_items if row.is_active])
    returned = _group_item_quantities(sales_return_repo.get_active_return_quantities(db, reference, exclude_id))
    names = {row.item_id: row.item_name for row in bill.bill_items}
    for item_id, requested in _group_item_quantities(items).items():
        if item_id not in sold:
            name = next(row.item_name for row in items if row.item_id == item_id)
            raise HTTPException(400, f"Item '{name}' was not sold on invoice {reference}.")
        prior = returned.get(item_id, Decimal(0))
        remaining = sold[item_id] - prior
        if requested > remaining:
            raise HTTPException(400, (
                f"Cannot return {requested.normalize():f} units of {names[item_id]} against invoice {reference}. "
                f"Sold quantity: {sold[item_id].normalize():f}. Previously returned: {prior.normalize():f}. "
                f"Remaining returnable quantity: {max(Decimal(0), remaining).normalize():f}."
            ))
    return bill.invoice_no


def create_sales_return(
    db: Session,
    sales_return_data: SalesReturnCreate,
) -> SalesReturn:
    """
    SALES RETURN CREATE -> ADD STOCK
    """

    # -------------------------------------------------------------------------
    # Customer
    # -------------------------------------------------------------------------

    validate_done_by_snapshot(db, sales_return_data.done_by)

    customer = (
        sales_return_validation
        .validate_and_get_active_customer(
            db,
            sales_return_data.customer_id,
        )
    )

    # -------------------------------------------------------------------------
    # Numbers
    # -------------------------------------------------------------------------

    numbers = (
        get_next_sales_return_numbers(
            db
        )
    )

    return_no = (
        sales_return_data
        .return_no
        .strip()
        .upper()
        if sales_return_data.return_no
        else numbers["return_no"]
    )

    sales_return_validation.validate_return_number_is_unique(
        db,
        return_no,
    )

    order_no = (
        sales_return_data
        .order_no
        .strip()
        if sales_return_data.order_no
        else numbers["order_no"]
    )

    # -------------------------------------------------------------------------
    # Due Date
    # -------------------------------------------------------------------------

    due_date = (
        sales_return_data.due_date
    )

    if (
        sales_return_data.due_term
        is not None
    ):

        due_date = (
            sales_return_data.return_date
            + timedelta(
                days=(
                    sales_return_data
                    .due_term
                )
            )
        )

    # -------------------------------------------------------------------------
    # Validate all ItemMaster references BEFORE changing stock
    # -------------------------------------------------------------------------

    original_invoice_no = _validate_original_invoice(
        db, sales_return_data.original_invoice_no, customer.id, sales_return_data.items,
    )

    validated_items = (
        _validate_create_items(
            db,
            sales_return_data.items,
        )
    )

    # -------------------------------------------------------------------------
    # Totals
    # -------------------------------------------------------------------------

    (
        taxable_total,
        sgst_total,
        cgst_total,
        igst_total,
        round_off,
        grand_total,
        lines,
    ) = _calculate_sales_return_totals(
        sales_return_data.items,
        is_gst=(
            sales_return_data.is_gst
        ),
    )

    # -------------------------------------------------------------------------
    # Parent
    # -------------------------------------------------------------------------

    record_payload = {
        "return_no": return_no,
        "order_no": order_no,
        "original_invoice_no": original_invoice_no,
        "return_date": (
            sales_return_data
            .return_date
        ),
        "due_term": (
            sales_return_data
            .due_term
        ),
        "due_date": due_date,
        "customer_id": (
            customer.id
        ),
        "is_gst": (
            sales_return_data
            .is_gst
        ),
        "address": (
            sales_return_data
            .address
        ),
        "city": (
            sales_return_data
            .city
        ),
        "state": (
            sales_return_data
            .state
        ),
        "contact_no": (
            sales_return_data
            .contact_no
        ),
        "email": (
            sales_return_data
            .email
        ),
        "done_by": (
            sales_return_data
            .done_by
        ),
        "brokerage": (
            sales_return_data
            .brokerage
            or 0.0
        ),
        "broker_remarks": (
            sales_return_data
            .broker_remarks
        ),
        "return_reason": (
            sales_return_data
            .return_reason
        ),
        "taxable_amount": (
            taxable_total
        ),
        "sgst_total": (
            sgst_total
        ),
        "cgst_total": (
            cgst_total
        ),
        "igst_total": (
            igst_total
        ),
        "round_off": (
            round_off
        ),
        "grand_total": (
            grand_total
        ),
        "delivery_date": (
            sales_return_data
            .delivery_date
        ),
        "ship_to": (
            sales_return_data
            .ship_to
        ),
        "ship_to_address": (
            sales_return_data
            .ship_to_address
        ),
        "shipping_state": (
            sales_return_data
            .shipping_state
        ),
        "transport": (
            sales_return_data
            .transport
        ),
        "reference": (
            sales_return_data
            .reference
        ),
        "remarks": (
            sales_return_data
            .remarks
        ),
        "show_shipping_address_on_bill": (
            sales_return_data
            .show_shipping_address_on_bill
        ),
        "is_active": True,
    }

    try:
        record = (
            sales_return_repo
            .create_sales_return(
                db,
                record_payload,
            )
        )

        # -------------------------------------------------------------------------
        # Child rows + stock
        # -------------------------------------------------------------------------

        for item_data, line in zip(
            sales_return_data.items,
            lines,
        ):

            item_master = (
                validated_items[
                    item_data.item_id
                ]
            )

            item_payload = {
                "sales_return_id": (
                    record.id
                ),
                "item_id": (
                    item_master.id
                ),
                "item_name": (
                    item_master.name
                ),
                "hsn_code": (
                    item_data.hsn_code.strip()
                    if item_data.hsn_code
                    else ""
                ),
                "quantity": (
                    item_data.quantity
                ),
                "unit": (
                    item_master.unit
                ),
                "price": (
                    item_data.price
                ),
                "disc_percent": (
                    item_data.disc_percent
                    or 0.0
                ),
                "sgst": (
                    line["sgst"]
                ),
                "cgst": (
                    line["cgst"]
                ),
                "igst": (
                    line["igst"]
                ),
                "amount": (
                    line["amount"]
                ),
            }

            sales_return_repo.create_sales_return_item(
                db,
                item_payload,
            )

            # =====================================================================
            # SALES RETURN CREATE -> ADD STOCK
            # =====================================================================

            item_master.current_stock = float(
                Decimal(str(item_master.current_stock or 0)) + Decimal(str(item_data.quantity))
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(record)

    return _attach_history_fields(
        record
    )


# =============================================================================
# GET SALES RETURN
# =============================================================================

def get_sales_return_by_id(
    db: Session,
    sales_return_id: int,
) -> SalesReturn:

    record = (
        sales_return_validation
        .validate_and_get_sales_return(
            db,
            sales_return_id,
        )
    )

    return _attach_history_fields(
        record
    )


# =============================================================================
# GET ALL SALES RETURNS
# =============================================================================

def get_all_sales_returns(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[SalesReturn] | int:

    records = (
        sales_return_repo
        .list_sales_returns(
            db,
            search=search,
            skip=skip,
            limit=limit,
            count_only=count_only,
        )
    )

    if count_only:
        return records

    return [
        _attach_history_fields(
            record
        )
        for record in records
    ]


# =============================================================================
# UPDATE SALES RETURN
# =============================================================================

def update_sales_return_by_id(
    db: Session,
    sales_return_id: int,
    sales_return_data: SalesReturnUpdate,
) -> SalesReturn:
    """
    Sales Return UPDATE stock formula:

        current_stock
        - old_return_quantity
        + new_return_quantity
    """

    record = (
        sales_return_validation
        .validate_and_get_sales_return(
            db,
            sales_return_id,
        )
    )

    if "done_by" in sales_return_data.model_fields_set:
        validate_done_by_snapshot(db, sales_return_data.done_by, previous=record.done_by)

    try:
        fields = (
            sales_return_data
            .model_fields_set
        )

        update_payload = {}

        # =========================================================================
        # Prevent direct active status modification
        # =========================================================================

        if "is_active" in fields:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Sales Return active status "
                    "cannot be changed directly."
                ),
            )

        # =========================================================================
        # Customer
        # =========================================================================

        if (
            "customer_id" in fields
            and sales_return_data.customer_id
            is not None
        ):

            customer = (
                sales_return_validation
                .validate_and_get_active_customer(
                    db,
                    sales_return_data.customer_id,
                )
            )

            update_payload[
                "customer_id"
            ] = customer.id

        # =========================================================================
        # Return Number
        # =========================================================================

        if (
            "return_no" in fields
            and sales_return_data.return_no
            is not None
        ):

            return_no = (
                sales_return_data
                .return_no
                .strip()
                .upper()
            )

            sales_return_validation.validate_return_number_is_unique(
                db,
                return_no,
                exclude_id=record.id,
            )

            update_payload[
                "return_no"
            ] = return_no

        # =========================================================================
        # Order No
        # =========================================================================

        if "order_no" in fields:

            update_payload[
                "order_no"
            ] = (
                sales_return_data
                .order_no
                .strip()
                if sales_return_data.order_no
                else None
            )

        # =========================================================================
        # Original Invoice
        # =========================================================================

        if "original_invoice_no" in fields:

            update_payload[
                "original_invoice_no"
            ] = (
                sales_return_data
                .original_invoice_no
            )

        # =========================================================================
        # Return Date
        # =========================================================================

        if (
            "return_date" in fields
            and sales_return_data.return_date
            is not None
        ):

            update_payload[
                "return_date"
            ] = (
                sales_return_data
                .return_date
            )

        # =========================================================================
        # Due Term
        # =========================================================================

        if "due_term" in fields:

            update_payload[
                "due_term"
            ] = (
                sales_return_data
                .due_term
            )

        effective_return_date = (
            update_payload.get(
                "return_date",
                record.return_date,
            )
        )

        effective_due_term = (
            update_payload.get(
                "due_term",
                record.due_term,
            )
        )

        # -------------------------------------------------------------------------
        # Due term changed
        # -------------------------------------------------------------------------

        if "due_term" in fields:

            if (
                sales_return_data.due_term
                is None
            ):

                update_payload[
                    "due_date"
                ] = None

            else:

                update_payload[
                    "due_date"
                ] = (
                    effective_return_date
                    + timedelta(
                        days=(
                            sales_return_data
                            .due_term
                        )
                    )
                )

        # -------------------------------------------------------------------------
        # Return date changed
        # -------------------------------------------------------------------------

        elif (
            "return_date" in fields
            and effective_due_term
            is not None
        ):

            update_payload[
                "due_date"
            ] = (
                effective_return_date
                + timedelta(
                    days=effective_due_term
                )
            )

        # -------------------------------------------------------------------------
        # Manual due date
        # -------------------------------------------------------------------------

        elif "due_date" in fields:

            update_payload[
                "due_date"
            ] = (
                sales_return_data
                .due_date
            )

        # =========================================================================
        # Effective GST
        # =========================================================================

        effective_is_gst = (
            sales_return_data.is_gst
            if (
                "is_gst" in fields
                and sales_return_data.is_gst
                is not None
            )
            else record.is_gst
        )

        update_payload["original_invoice_no"] = _validate_original_invoice(
            db, update_payload.get("original_invoice_no", record.original_invoice_no),
            update_payload.get("customer_id", record.customer_id),
            sales_return_data.items if sales_return_data.items is not None else record.items,
            exclude_id=record.id,
        )

        # =========================================================================
        # ITEMS
        # =========================================================================

        if (
            "items" in fields
            and sales_return_data.items
            is not None
        ):

            # ---------------------------------------------------------------------
            # OLD quantities
            # ---------------------------------------------------------------------

            old_quantities = (
                _group_item_quantities(
                    record.items
                )
            )

            # ---------------------------------------------------------------------
            # NEW quantities
            # ---------------------------------------------------------------------

            new_quantities = (
                _group_item_quantities(
                    sales_return_data.items
                )
            )

            # ---------------------------------------------------------------------
            # Validate all new ItemMaster references first
            # ---------------------------------------------------------------------

            validated_new_items = {}

            for item_data in (
                sales_return_data.items
            ):

                item_master = (
                    sales_return_validation
                    .validate_and_get_item_for_return(
                        db,
                        item_data.item_id,
                        item_data.item_name,
                    )
                )

                validated_new_items[
                    item_data.item_id
                ] = item_master

            # ---------------------------------------------------------------------
            # Validate final stock BEFORE changing anything
            # ---------------------------------------------------------------------

            stock_items = (
                _validate_update_stock(
                    db,
                    old_quantities,
                    new_quantities,
                )
            )

            # ---------------------------------------------------------------------
            # Totals
            # ---------------------------------------------------------------------

            (
                taxable_total,
                sgst_total,
                cgst_total,
                igst_total,
                round_off,
                grand_total,
                lines,
            ) = _calculate_sales_return_totals(
                sales_return_data.items,
                is_gst=(
                    effective_is_gst
                ),
            )

            # ---------------------------------------------------------------------
            # APPLY ONLY STOCK DIFFERENCE
            # ---------------------------------------------------------------------

            all_item_ids = (
                set(
                    old_quantities.keys()
                )
                | set(
                    new_quantities.keys()
                )
            )

            for item_id in all_item_ids:

                item_master = (
                    stock_items[
                        item_id
                    ]
                )

                difference = new_quantities.get(item_id, Decimal(0)) - old_quantities.get(item_id, Decimal(0))
                item_master.current_stock = float(Decimal(str(item_master.current_stock or 0)) + difference)

            # ---------------------------------------------------------------------
            # Delete old SalesReturnItem rows
            # ---------------------------------------------------------------------

            for old_item in list(
                record.items
            ):

                sales_return_repo.delete_sales_return_item(
                    db,
                    old_item,
                )

            # ---------------------------------------------------------------------
            # Recreate updated child rows
            # ---------------------------------------------------------------------

            for item_data, line in zip(
                sales_return_data.items,
                lines,
            ):

                item_master = (
                    validated_new_items[
                        item_data.item_id
                    ]
                )

                item_payload = {
                    "sales_return_id": (
                        record.id
                    ),
                    "item_id": (
                        item_master.id
                    ),
                    "item_name": (
                        item_master.name
                    ),
                    "hsn_code": (
                        item_data.hsn_code.strip()
                        if item_data.hsn_code
                        else ""
                    ),
                    "quantity": (
                        item_data.quantity
                    ),
                    "unit": (
                        item_master.unit
                    ),
                    "price": (
                        item_data.price
                    ),
                    "disc_percent": (
                        item_data.disc_percent
                        or 0.0
                    ),
                    "sgst": (
                        line["sgst"]
                    ),
                    "cgst": (
                        line["cgst"]
                    ),
                    "igst": (
                        line["igst"]
                    ),
                    "amount": (
                        line["amount"]
                    ),
                }

                sales_return_repo.create_sales_return_item(
                    db,
                    item_payload,
                )

            update_payload.update(
                {
                    "taxable_amount": (
                        taxable_total
                    ),
                    "sgst_total": (
                        sgst_total
                    ),
                    "cgst_total": (
                        cgst_total
                    ),
                    "igst_total": (
                        igst_total
                    ),
                    "round_off": (
                        round_off
                    ),
                    "grand_total": (
                        grand_total
                    ),
                }
            )

        # =========================================================================
        # GST changed without items
        # =========================================================================

        elif "is_gst" in fields:

            (
                taxable_total,
                sgst_total,
                cgst_total,
                igst_total,
                round_off,
                grand_total,
                _,
            ) = _calculate_sales_return_totals(
                record.items,
                is_gst=effective_is_gst,
            )

            update_payload.update(
                {
                    "taxable_amount": (
                        taxable_total
                    ),
                    "sgst_total": (
                        sgst_total
                    ),
                    "cgst_total": (
                        cgst_total
                    ),
                    "igst_total": (
                        igst_total
                    ),
                    "round_off": (
                        round_off
                    ),
                    "grand_total": (
                        grand_total
                    ),
                }
            )

        # =========================================================================
        # SIMPLE FIELDS
        # =========================================================================

        simple_fields = [
            "is_gst",
            "address",
            "city",
            "state",
            "contact_no",
            "email",
            "done_by",
            "brokerage",
            "broker_remarks",
            "return_reason",
            "delivery_date",
            "ship_to",
            "ship_to_address",
            "shipping_state",
            "transport",
            "reference",
            "remarks",
            "show_shipping_address_on_bill",
        ]

        for field in simple_fields:

            if field in fields:

                update_payload[
                    field
                ] = getattr(
                    sales_return_data,
                    field,
                )

        # =========================================================================
        # SAVE
        # =========================================================================

        updated_record = (
            sales_return_repo
            .update_sales_return(
                db,
                record,
                update_payload,
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(
        updated_record
    )

    return _attach_history_fields(
        updated_record
    )


# =============================================================================
# DELETE SALES RETURN
# =============================================================================

def delete_sales_return_by_id(
    db: Session,
    sales_return_id: int,
) -> dict:
    """
    SALES RETURN DELETE -> DEDUCT RETURNED STOCK.

    The Sales Return remains in the database
    with is_active=False.
    """

    record = (
        sales_return_validation
        .validate_and_get_sales_return(
            db,
            sales_return_id,
        )
    )

    # -------------------------------------------------------------------------
    # First validate ALL stock before modifying anything
    # -------------------------------------------------------------------------

    quantities = _group_item_quantities(record.items)
    item_objects = _validate_update_stock(db, quantities, {})

    # -------------------------------------------------------------------------
    # Reverse Sales Return stock
    # -------------------------------------------------------------------------

    try:
        for item_id, return_quantity in quantities.items():

            item_master = (
                item_objects[
                    item_id
                ]
            )

            # =====================================================================
            # SALES RETURN DELETE -> DEDUCT STOCK
            # =====================================================================

            item_master.current_stock = float(Decimal(str(item_master.current_stock or 0)) - return_quantity)

        # -------------------------------------------------------------------------
        # Soft delete
        # -------------------------------------------------------------------------

        sales_return_repo.deactivate_sales_return(
            db,
            record,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            f"Sales Return "
            f"'{record.return_no}' "
            f"deleted successfully."
        )
    }