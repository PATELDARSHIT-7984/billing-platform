from api.validation.done_by import validate_done_by_snapshot
from api.utils.rounding import round_half_up
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.purchase_return import PurchaseReturn
from api.services.party import apply_party_balance_delta
from api.repository import purchase_return as purchase_return_repo
from api.repository import purchase as purchase_repo
from api.schema.purchase_return import (
    PurchaseReturnCreate,
    PurchaseReturnUpdate,
)
from api.validation import purchase_return as purchase_return_validation


# =============================================================================
# NUMBER GENERATION
# =============================================================================

def _next_number(
    db: Session,
    column,
    prefix: str,
) -> str:
    """
    Generates next sequential Purchase Return number.

    Example:
        PR-0001
        PR-0002

        PRO-0001
        PRO-0002
    """

    last_value = (
        purchase_return_repo
        .get_last_column_value(
            db,
            column,
        )
    )

    if not last_value:
        return f"{prefix}-0001"

    digits = "".join(
        char
        for char in str(last_value)
        if char.isdigit()
    )

    next_number = (
        int(digits or 0)
        + 1
    )

    return (
        f"{prefix}-"
        f"{next_number:04d}"
    )


def get_next_purchase_return_numbers(
    db: Session,
) -> dict:
    """
    Returns next Purchase Return and order numbers.
    """

    return {
        "return_no": _next_number(
            db,
            PurchaseReturn.return_no,
            "PR",
        ),
        "order_no": _next_number(
            db,
            PurchaseReturn.order_no,
            "PRO",
        ),
    }


# =============================================================================
# TOTAL CALCULATION
# =============================================================================

def _calculate_totals(
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
    Calculates Purchase Return totals.

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

        discount = float(
            item.disc_percent
            or 0.0
        )

        # ---------------------------------------------------------------------
        # GST MODE
        # ---------------------------------------------------------------------

        if is_gst:

            sgst = float(
                item.sgst
                or 0.0
            )

            cgst = float(
                item.cgst
                or 0.0
            )

            igst = float(
                item.igst
                or 0.0
            )

        else:

            sgst = 0.0
            cgst = 0.0
            igst = 0.0

        purchase_return_validation.validate_gst_type_is_exclusive(
            sgst,
            cgst,
            igst,
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

        discount_amount = (
            gross
            * discount
            / 100
        )

        taxable = (
            gross
            - discount_amount
        )

        sgst_amount = (
            taxable
            * sgst
            / 100
        )

        cgst_amount = (
            taxable
            * cgst
            / 100
        )

        igst_amount = (
            taxable
            * igst
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
                "sgst": sgst,
                "cgst": cgst,
                "igst": igst,
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
    Groups quantities by item_id.

    This prevents duplicate item rows from bypassing
    stock validation.

    Example:

        item 10 -> 3
        item 10 -> 5

    Result:

        {
            10: 8
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
                    "for Purchase Return items."
                ),
            )

        quantities[
            item.item_id
        ] += Decimal(str(item.quantity))

    return dict(
        quantities
    )


# =============================================================================
# ATTACH RESPONSE FIELDS
# =============================================================================

def _attach_fields(
    record: PurchaseReturn,
) -> PurchaseReturn:
    """
    Adds calculated response-only properties.
    """

    record.party_name = (
        record.party.name
        if record.party
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

    record.total_quantity = sum(
        float(
            item.quantity
            or 0.0
        )
        for item in record.items
    )

    for return_item in record.items:

        item_master = (
            return_item.item
        )

        current_stock = (
            float(
                item_master.current_stock
                or 0.0
            )
            if item_master
            else 0.0
        )

        old_return_quantity = float(
            return_item.quantity
            or 0.0
        )

        return_item.current_stock = (
            current_stock
        )

        # If user edits this return,
        # old returned quantity can first be restored.
        return_item.available_stock = (
            current_stock
            + old_return_quantity
        )

    return record


# =============================================================================
# VALIDATE CREATE STOCK
# =============================================================================

def _validate_create_stock(
    db: Session,
    items,
) -> dict:
    """
    Purchase Return CREATE deducts stock.

    Therefore the total return quantity for every item
    must be available in ItemMaster.
    """

    quantities = (
        _group_item_quantities(
            items
        )
    )

    item_objects = {}

    for item_id, return_quantity in quantities.items():

        item_master = (
            purchase_return_validation
            .validate_and_get_active_item(
                db,
                item_id,
                None,
            )
        )

        purchase_return_validation.validate_sufficient_stock(item_master, return_quantity)

        item_objects[
            item_id
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
    Purchase Return removes stock.

    Correct update formula:

        resulting_stock
            = current_stock
            + old_return_quantity
            - new_return_quantity

    Example:

        Original Return = 10
        Current Stock   = 40
        New Return      = 15

        resulting_stock
            = 40 + 10 - 15
            = 35
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
            purchase_return_repo
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

        additional = new_quantities.get(item_id, Decimal(0)) - old_quantities.get(item_id, Decimal(0))
        purchase_return_validation.validate_sufficient_stock(item_master, additional, additional=True)

        item_objects[
            item_id
        ] = item_master

    return item_objects


# =============================================================================
# CREATE PURCHASE RETURN
# =============================================================================

def _validate_original_purchase(db, original_bill_no, party_id, items, exclude_id=None):
    reference = (original_bill_no or "").strip().upper()
    if not reference:
        return None  # The current workflow explicitly supports standalone returns.
    purchase = purchase_repo.get_purchase_by_bill_no(db, reference)
    if purchase is None or not purchase.is_active:
        raise HTTPException(400, f"Original Purchase {reference} not found or inactive.")
    if purchase.party_id != party_id:
        raise HTTPException(400, f"Purchase {reference} does not belong to the selected Supplier.")

    purchased = _group_item_quantities(purchase.items)
    returned = _group_item_quantities(
        purchase_return_repo.get_active_return_quantities(db, reference, exclude_id),
    )
    names = {row.item_id: row.item_name for row in purchase.items}
    for item_id, requested in _group_item_quantities(items).items():
        if item_id not in purchased:
            name = next(row.item_name for row in items if row.item_id == item_id)
            raise HTTPException(400, f"Item '{name}' was not purchased on Purchase {reference}.")
        prior = returned.get(item_id, Decimal(0))
        remaining = purchased[item_id] - prior
        if requested > remaining:
            raise HTTPException(400, (
                f"Cannot return {requested.normalize():f} units of {names[item_id]} against Purchase {reference}. "
                f"Purchased quantity: {purchased[item_id].normalize():f}, already returned: {prior.normalize():f}, "
                f"remaining returnable quantity: {max(Decimal(0), remaining).normalize():f}."
            ))
    return purchase.bill_no


def create_purchase_return(
    db: Session,
    data: PurchaseReturnCreate,
) -> PurchaseReturn:
    """
    Purchase Return CREATE -> DEDUCT STOCK.
    """

    # -------------------------------------------------------------------------
    # Party
    # -------------------------------------------------------------------------

    validate_done_by_snapshot(db, data.done_by)

    try:
        party = (
            purchase_return_validation
            .validate_and_get_active_party(
                db,
                data.party_id,
            )
        )

        # -------------------------------------------------------------------------
        # Numbers
        # -------------------------------------------------------------------------

        numbers = (
            get_next_purchase_return_numbers(
                db
            )
        )

        return_no = (
            data.return_no
            .strip()
            .upper()
            if data.return_no
            else numbers["return_no"]
        )

        purchase_return_validation.validate_return_number_is_unique(
            db,
            return_no,
        )

        order_no = (
            data.order_no.strip()
            if data.order_no
            else numbers["order_no"]
        )

        # -------------------------------------------------------------------------
        # Due date
        # -------------------------------------------------------------------------

        due_date = (
            data.due_date
        )

        if data.due_term is not None:

            due_date = (
                data.return_date
                + timedelta(
                    days=data.due_term
                )
            )

        # -------------------------------------------------------------------------
        # Validate all stock BEFORE modifying database quantities
        # -------------------------------------------------------------------------

        original_bill_no = _validate_original_purchase(db, data.original_bill_no, party.id, data.items)

        validated_items = (
            _validate_create_stock(
                db,
                data.items,
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
        ) = _calculate_totals(
            data.items,
            is_gst=data.is_gst,
        )

        # -------------------------------------------------------------------------
        # Parent record
        # -------------------------------------------------------------------------

        record_payload = {
            "return_no": return_no,
            "order_no": order_no,
            "original_bill_no": original_bill_no,
            "return_date": (
                data.return_date
            ),
            "due_term": (
                data.due_term
            ),
            "due_date": due_date,
            "party_id": party.id,
            "is_gst": (
                data.is_gst
            ),
            "address": (
                data.address
            ),
            "city": (
                data.city
            ),
            "party_state": (
                data.party_state
            ),
            "contact_no": (
                data.contact_no
            ),
            "email": (
                data.email
            ),
            "done_by": (
                data.done_by
            ),
            "brokerage": (
                data.brokerage
                or 0.0
            ),
            "broker_remarks": (
                data.broker_remarks
            ),
            "return_reason": (
                data.return_reason
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
                data.delivery_date
            ),
            "transport": (
                data.transport
            ),
            "ship_to": (
                data.ship_to
            ),
            "ship_to_address": (
                data.ship_to_address
            ),
            "state": (
                data.state
            ),
            "reference": (
                data.reference
            ),
            "remarks": (
                data.remarks
            ),
            "show_shipping_address_on_bill": (
                data
                .show_shipping_address_on_bill
            ),
            "is_active": True,
        }

        record = (
            purchase_return_repo
            .create_purchase_return(
                db,
                record_payload,
            )
        )

        # -------------------------------------------------------------------------
        # Create items + deduct stock
        # -------------------------------------------------------------------------

        for item_data, line in zip(
            data.items,
            lines,
        ):

            item_master = (
                validated_items[
                    item_data.item_id
                ]
            )

            hsn_code = (
                item_data.hsn_code.strip()
                if item_data.hsn_code
                else ""
            )

            item_payload = {
                "purchase_return_id": (
                    record.id
                ),
                "item_id": (
                    item_master.id
                ),
                "item_name": (
                    item_master.name
                ),
                "hsn_code": (
                    hsn_code
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

            purchase_return_repo.create_purchase_return_item(
                db,
                item_payload,
            )

            # =====================================================================
            # PURCHASE RETURN CREATE -> DEDUCT STOCK
            # =====================================================================

            item_master.current_stock = float(
                Decimal(str(item_master.current_stock or 0)) - Decimal(str(item_data.quantity))
            )

        apply_party_balance_delta(db, record.party_id, -Decimal(str(record.grand_total)))

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(record)

    return _attach_fields(
        record
    )


# =============================================================================
# GET PURCHASE RETURN BY ID
# =============================================================================

def get_purchase_return_by_id(
    db: Session,
    record_id: int,
) -> PurchaseReturn:

    record = (
        purchase_return_validation
        .validate_and_get_purchase_return(
            db,
            record_id,
        )
    )

    return _attach_fields(
        record
    )


# =============================================================================
# GET ALL PURCHASE RETURNS
# =============================================================================

def get_all_purchase_returns(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[PurchaseReturn] | int:

    records = (
        purchase_return_repo
        .list_purchase_returns(
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
        _attach_fields(
            record
        )
        for record in records
    ]


# =============================================================================
# UPDATE PURCHASE RETURN
# =============================================================================

def update_purchase_return_by_id(
    db: Session,
    record_id: int,
    data: PurchaseReturnUpdate,
) -> PurchaseReturn:
    """
    Purchase Return UPDATE:

        current_stock
        + old_return_quantity
        - new_return_quantity
    """

    try:
        record = (
            purchase_return_validation
            .validate_and_get_purchase_return(
                db,
                record_id,
            )
        )

        if "done_by" in data.model_fields_set:
            validate_done_by_snapshot(db, data.done_by, previous=record.done_by)

        old_party_id = record.party_id
        old_grand_total = Decimal(str(record.grand_total))

        fields = (
            data.model_fields_set
        )

        update_payload = {}

        # =========================================================================
        # Prevent manual deactivation
        # =========================================================================

        if "is_active" in fields:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Purchase Return active status "
                    "cannot be changed directly."
                ),
            )

        # =========================================================================
        # Party
        # =========================================================================

        if (
            "party_id" in fields
            and data.party_id is not None
        ):

            party = (
                purchase_return_validation
                .validate_and_get_active_party(
                    db,
                    data.party_id,
                )
            )

            update_payload[
                "party_id"
            ] = party.id

        # =========================================================================
        # Return number
        # =========================================================================

        if (
            "return_no" in fields
            and data.return_no is not None
        ):

            return_no = (
                data.return_no
                .strip()
                .upper()
            )

            purchase_return_validation.validate_return_number_is_unique(
                db,
                return_no,
                exclude_id=record.id,
            )

            update_payload[
                "return_no"
            ] = return_no

        # =========================================================================
        # Basic number fields
        # =========================================================================

        if "order_no" in fields:

            update_payload[
                "order_no"
            ] = (
                data.order_no.strip()
                if data.order_no
                else None
            )

        if "original_bill_no" in fields:

            update_payload[
                "original_bill_no"
            ] = (
                data.original_bill_no
            )

        # =========================================================================
        # Return date
        # =========================================================================

        if (
            "return_date" in fields
            and data.return_date is not None
        ):

            update_payload[
                "return_date"
            ] = data.return_date

        # =========================================================================
        # Due term
        # =========================================================================

        if "due_term" in fields:

            update_payload[
                "due_term"
            ] = data.due_term

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
        # due_term explicitly changed
        # -------------------------------------------------------------------------

        if "due_term" in fields:

            if data.due_term is None:

                update_payload[
                    "due_date"
                ] = None

            else:

                update_payload[
                    "due_date"
                ] = (
                    effective_return_date
                    + timedelta(
                        days=data.due_term
                    )
                )

        # -------------------------------------------------------------------------
        # return_date changed while due_term remains
        # -------------------------------------------------------------------------

        elif (
            "return_date" in fields
            and effective_due_term is not None
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
        # Manual due_date only when due_term/date isn't controlling it
        # -------------------------------------------------------------------------

        elif "due_date" in fields:

            update_payload[
                "due_date"
            ] = data.due_date

        # =========================================================================
        # Effective GST
        # =========================================================================

        effective_is_gst = (
            data.is_gst
            if (
                "is_gst" in fields
                and data.is_gst is not None
            )
            else record.is_gst
        )

        update_payload["original_bill_no"] = _validate_original_purchase(
            db, update_payload.get("original_bill_no", record.original_bill_no),
            update_payload.get("party_id", record.party_id),
            data.items if data.items is not None else record.items, exclude_id=record.id,
        )

        # =========================================================================
        # ITEMS UPDATE
        # =========================================================================

        if (
            "items" in fields
            and data.items is not None
        ):

            # ---------------------------------------------------------------------
            # OLD returned quantities
            # ---------------------------------------------------------------------

            old_quantities = (
                _group_item_quantities(
                    record.items
                )
            )

            # ---------------------------------------------------------------------
            # NEW returned quantities
            # ---------------------------------------------------------------------

            new_quantities = (
                _group_item_quantities(
                    data.items
                )
            )

            # ---------------------------------------------------------------------
            # Validate new active items BEFORE changing anything
            # ---------------------------------------------------------------------

            validated_new_items = {}

            for item_data in data.items:

                if item_data.item_id in old_quantities:
                    item_master = purchase_return_repo.get_item_by_id_any_status(db, item_data.item_id)
                else:
                    item_master = purchase_return_validation.validate_and_get_active_item(
                        db, item_data.item_id, item_data.item_name,
                    )

                validated_new_items[
                    item_data.item_id
                ] = item_master

            # ---------------------------------------------------------------------
            # Validate resulting stock
            # ---------------------------------------------------------------------

            stock_items = (
                _validate_update_stock(
                    db,
                    old_quantities,
                    new_quantities,
                )
            )

            # ---------------------------------------------------------------------
            # Calculate totals
            # ---------------------------------------------------------------------

            (
                taxable_total,
                sgst_total,
                cgst_total,
                igst_total,
                round_off,
                grand_total,
                lines,
            ) = _calculate_totals(
                data.items,
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

                difference = old_quantities.get(item_id, Decimal(0)) - new_quantities.get(item_id, Decimal(0))
                item_master.current_stock = float(Decimal(str(item_master.current_stock or 0)) + difference)

            # ---------------------------------------------------------------------
            # Delete old child rows
            #
            # This does NOT delete the Purchase Return itself.
            # ---------------------------------------------------------------------

            for old_item in list(
                record.items
            ):

                purchase_return_repo.delete_purchase_return_item(
                    db,
                    old_item,
                )

            # ---------------------------------------------------------------------
            # Recreate updated rows
            # ---------------------------------------------------------------------

            for item_data, line in zip(
                data.items,
                lines,
            ):

                item_master = (
                    validated_new_items[
                        item_data.item_id
                    ]
                )

                item_payload = {
                    "purchase_return_id": (
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

                purchase_return_repo.create_purchase_return_item(
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
        # GST mode changed WITHOUT items payload
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
            ) = _calculate_totals(
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
            "party_state",
            "contact_no",
            "email",
            "done_by",
            "brokerage",
            "broker_remarks",
            "return_reason",
            "delivery_date",
            "transport",
            "ship_to",
            "ship_to_address",
            "state",
            "reference",
            "remarks",
            "show_shipping_address_on_bill",
        ]

        for field in simple_fields:

            if field in fields:

                update_payload[
                    field
                ] = getattr(
                    data,
                    field,
                )

        # =========================================================================
        # SAVE
        # =========================================================================

        updated_record = (
            purchase_return_repo
            .update_purchase_return(
                db,
                record,
                update_payload,
            )
        )

        new_party_id = updated_record.party_id
        new_grand_total = Decimal(str(updated_record.grand_total))
        if old_party_id == new_party_id:
            balance_delta = old_grand_total - new_grand_total
            if balance_delta:
                apply_party_balance_delta(db, new_party_id, balance_delta)
        else:
            apply_party_balance_delta(db, old_party_id, old_grand_total)
            apply_party_balance_delta(db, new_party_id, -new_grand_total)

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(
        updated_record
    )

    return _attach_fields(
        updated_record
    )


# =============================================================================
# DELETE PURCHASE RETURN
# =============================================================================

def delete_purchase_return_by_id(
    db: Session,
    record_id: int,
) -> dict:
    """
    Purchase Return DELETE -> RESTORE STOCK.

    The return stays in database as is_active=False.
    """

    try:
        record = (
            purchase_return_validation
            .validate_and_get_purchase_return(
                db,
                record_id,
            )
        )

        old_party_id = record.party_id
        old_grand_total = Decimal(str(record.grand_total))

        # -------------------------------------------------------------------------
        # Restore returned quantities
        # -------------------------------------------------------------------------

        for return_item in record.items:

            if return_item.item_id is None:

                raise HTTPException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    detail=(
                        f"Purchase Return item "
                        f"'{return_item.item_name}' "
                        f"is no longer linked to "
                        f"ItemMaster."
                    ),
                )

            item_master = (
                purchase_return_repo
                .get_item_by_id_any_status(
                    db,
                    return_item.item_id,
                )
            )

            if not item_master:

                raise HTTPException(
                    status_code=(
                        status.HTTP_404_NOT_FOUND
                    ),
                    detail=(
                        f"Item with ID "
                        f"{return_item.item_id} "
                        f"not found."
                    ),
                )

            # =====================================================================
            # PURCHASE RETURN DELETE -> ADD STOCK BACK
            # =====================================================================

            item_master.current_stock = float(
                Decimal(str(item_master.current_stock or 0)) + Decimal(str(return_item.quantity))
            )

        # Soft delete
        purchase_return_repo.deactivate_purchase_return(
            db,
            record,
        )

        apply_party_balance_delta(db, old_party_id, old_grand_total)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            f"Purchase Return "
            f"'{record.return_no}' "
            f"deleted successfully."
        )
    }
