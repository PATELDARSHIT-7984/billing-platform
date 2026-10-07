from api.validation.done_by import validate_done_by_snapshot
from api.utils.rounding import round_half_up
from collections import defaultdict
from datetime import timedelta
from typing import Optional
from decimal import Decimal

from api.services.party import apply_party_balance_delta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.purchase import Purchase
from api.repository import item_master as item_master_repo
from api.repository import purchase as purchase_repo
from api.repository import purchase_return as purchase_return_repo
from api.schema.purchase import PurchaseCreate, PurchaseUpdate
from api.validation import purchase as purchase_validation


# =============================================================================
# Helper: Calculate Purchase Totals
# =============================================================================
def _calculate_purchase_totals(
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
    Calculates purchase totals.

    Returns:
        taxable_total
        sgst_total
        cgst_total
        igst_total
        round_off
        grand_total
        line_amounts
    """

    taxable_total = 0.0
    sgst_total = 0.0
    cgst_total = 0.0
    igst_total = 0.0

    line_amounts = []

    for item in items:
        discount = float(item.disc_percent or 0.0)

        # ---------------------------------------------------------------------
        # GST Logic
        # ---------------------------------------------------------------------
        # If purchase is non-GST, backend forces all taxes to zero.
        # ---------------------------------------------------------------------
        if is_gst:
            sgst = float(item.sgst or 0.0)
            cgst = float(item.cgst or 0.0)
            igst = float(item.igst or 0.0)
        else:
            sgst = 0.0
            cgst = 0.0
            igst = 0.0

        purchase_validation.validate_gst_type_is_exclusive(
            sgst,
            cgst,
            igst,
        )

        quantity = float(item.quantity or 0.0)
        price = float(item.price or 0.0)

        gross = quantity * price

        discount_amount = (
            gross * discount / 100
        )

        taxable = (
            gross - discount_amount
        )

        sgst_amount = (
            taxable * sgst / 100
        )

        cgst_amount = (
            taxable * cgst / 100
        )

        igst_amount = (
            taxable * igst / 100
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

        line_amounts.append(
            {
                "amount": round_half_up(amount, 2),
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
        net_total,
        0,
    )

    round_off = (
        grand_total - net_total
    )

    return (
        round_half_up(taxable_total, 2),
        round_half_up(sgst_total, 2),
        round_half_up(cgst_total, 2),
        round_half_up(igst_total, 2),
        round_half_up(round_off, 2),
        round_half_up(grand_total, 2),
        line_amounts,
    )


def _resolve_purchase_item(
    db: Session,
    item_data,
):

    # ---------------------------------------------------------
    # Existing item selected from Item Master
    # ---------------------------------------------------------
    if item_data.item_id is not None:
        return (
            purchase_validation
            .validate_and_get_active_item(
                db,
                item_data.item_id,
            )
        )

    item_name = item_data.item_name.strip()

    # ---------------------------------------------------------
    # Check if same item already exists
    # ---------------------------------------------------------
    existing_item = item_master_repo.get_item_by_name(
        db,
        item_name,
    )

    if existing_item:
        if not existing_item.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Item '{existing_item.name}' already exists "
                    "but is inactive."
                ),
            )

        return existing_item

    # ---------------------------------------------------------
    # Automatically create new ItemMaster item
    # ---------------------------------------------------------
    item_payload = {
        "name": item_name,
        "hsn_code": item_data.hsn_code.strip(),
        "unit": item_data.unit.strip(),

        # Start stock at zero.
        # Purchase quantity will be added afterward.
        "current_stock": 0.0,

        # Purchase price comes from current purchase row.
        "purchase_price": float(item_data.price or 0.0),

        # We don't know sale price/MRP yet.
        "sale_price": 0.0,
        "mrp": 0.0,

        # GST can come from Purchase row.
        "sgst": float(item_data.sgst or 0.0),
        "cgst": float(item_data.cgst or 0.0),

        "last_purchase_date": None,
        "is_active": True,
    }

    return item_master_repo.create_item(
        db,
        item_payload,
    )


# =============================================================================
# Helper: Attach Extra Purchase Response Fields
# =============================================================================
def _attach_purchase_fields(
    purchase: Purchase,
) -> Purchase:
    """
    Adds calculated/display-only fields used by PurchaseListResponse.
    """

    purchase.party_name = (
        purchase.party.name
        if purchase.party
        else "Unknown"
    )

    purchase.item_count = len(
        purchase.items
    )

    purchase.item_names = [
        row.item_name
        for row in purchase.items
    ]

    purchase.hsn_codes = [
        row.hsn_code
        for row in purchase.items
    ]

    purchase.purchase_prices = [
        float(row.price or 0.0)
        for row in purchase.items
    ]

    return purchase


# =============================================================================
# Helper: Group Purchase Quantities By Item
# =============================================================================
def _group_purchase_quantities(
    items,
) -> dict[int, Decimal]:
    """
    Groups quantities using item_id.

    Example:
        item_id 1 = 5 qty
        item_id 1 = 3 qty

    Result:
        {
            1: 8
        }

    This makes Purchase update stock calculation safe even if the
    same item appears multiple times in one purchase.
    """

    quantities = defaultdict(Decimal)

    for item in items:
        quantities[item.item_id] += Decimal(str(item.quantity))

    return dict(quantities)


# =============================================================================
# Create Purchase
# =============================================================================
def create_purchase(
    db: Session,
    purchase_data: PurchaseCreate,
) -> Purchase:

    # -------------------------------------------------------------------------
    # Validate Party
    # -------------------------------------------------------------------------
    validate_done_by_snapshot(db, purchase_data.done_by)

    party = (
        purchase_validation
        .validate_and_get_active_party(
            db,
            purchase_data.party_id,
        )
    )

    # -------------------------------------------------------------------------
    # Bill Number
    # -------------------------------------------------------------------------
    bill_no = (
        purchase_data.bill_no
        .strip()
        .upper()
    )

    purchase_validation.validate_bill_number_is_unique(
        db,
        bill_no,
    )

    # -------------------------------------------------------------------------
    # Order Number
    # -------------------------------------------------------------------------
    order_no = (
        purchase_data.order_no.strip()
        if purchase_data.order_no
        else None
    )

    # -------------------------------------------------------------------------
    # Due Date
    # -------------------------------------------------------------------------
    due_date = purchase_data.due_date

    if purchase_data.due_term is not None:
        due_date = (
            purchase_data.bill_date
            + timedelta(
                days=purchase_data.due_term
            )
        )

    # -------------------------------------------------------------------------
    # Calculate Purchase Totals
    # -------------------------------------------------------------------------
    (
        taxable_total,
        sgst_total,
        cgst_total,
        igst_total,
        round_off,
        grand_total,
        line_amounts,
    ) = _calculate_purchase_totals(
        purchase_data.items,
        is_gst=purchase_data.is_gst,
    )

    # -------------------------------------------------------------------------
    # Purchase Payload
    # -------------------------------------------------------------------------
    purchase_payload = {
        "bill_no": bill_no,
        "order_no": order_no,
        "bill_date": purchase_data.bill_date,
        "due_term": purchase_data.due_term,
        "due_date": due_date,
        "party_id": party.id,
        "is_gst": purchase_data.is_gst,
        "contact_person": purchase_data.contact_person,
        "contact_no": purchase_data.contact_no,
        "email": purchase_data.email,
        "done_by": purchase_data.done_by,
        "brokerage": purchase_data.brokerage or 0.0,
        "broker_remarks": purchase_data.broker_remarks,
        "taxable_amount": taxable_total,
        "sgst_total": sgst_total,
        "cgst_total": cgst_total,
        "igst_total": igst_total,
        "round_off": round_off,
        "grand_total": grand_total,
        "delivery_date": purchase_data.delivery_date,
        "transport": purchase_data.transport,
        "ship_to": purchase_data.ship_to,
        "ship_to_address": purchase_data.ship_to_address,
        "state": purchase_data.state,
        "reference": purchase_data.reference,
        "remarks": purchase_data.remarks,
        "show_shipping_address_on_bill": (
            purchase_data
            .show_shipping_address_on_bill
        ),
        "is_active": True,
    }

    try:
        purchase = purchase_repo.create_purchase(
            db,
            purchase_payload,
        )

        # -------------------------------------------------------------------------
        # Create Purchase Items + Add Stock
        # -------------------------------------------------------------------------
        for item_data, line in zip(
            purchase_data.items,
            line_amounts,
        ):

            item_master = _resolve_purchase_item(
                db,
                item_data,
            )

            hsn_code = (
                item_data.hsn_code.strip()
                if item_data.hsn_code
                else ""
            )

            purchase_validation.validate_hsn_code_present(
                hsn_code,
                item_master.name,
            )

            item_payload = {
                "purchase_id": purchase.id,
                "item_id": item_master.id,
                "item_name": item_master.name,
                "hsn_code": hsn_code,
                "quantity": item_data.quantity,
                "unit": item_master.unit,
                "price": item_data.price,
                "disc_percent": (
                    item_data.disc_percent or 0.0
                ),
                "sgst": line["sgst"],
                "cgst": line["cgst"],
                "igst": line["igst"],
                "amount": line["amount"],
            }

            purchase_repo.create_purchase_item(
                db,
                item_payload,
            )

            # Purchase always ADDS stock
            item_master.current_stock = float(
                Decimal(str(item_master.current_stock or 0)) + Decimal(str(item_data.quantity))
            )

            # Latest purchase price
            item_master.purchase_price = (
                item_data.price
            )

            # Latest purchase date
            item_master.last_purchase_date = (
                purchase_data.bill_date
            )

        # -------------------------------------------------------------------------
        # Supplier Running Balance
        # Purchase increases amount payable to supplier.
        # -------------------------------------------------------------------------
        apply_party_balance_delta(
            db,
            purchase.party_id,
            Decimal(str(purchase.grand_total)),
        )

        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(purchase)

    purchase.party_name = party.name

    return purchase

# =============================================================================
# Get Purchase By ID
# =============================================================================
def get_purchase_by_id(
    db: Session,
    purchase_id: int,
) -> Purchase:

    purchase = (
        purchase_validation
        .validate_and_get_active_purchase(
            db,
            purchase_id,
        )
    )

    purchase.party_name = (
        purchase.party.name
        if purchase.party
        else "Unknown"
    )

    return purchase


# =============================================================================
# Get All Purchases
# =============================================================================
def get_all_purchases(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Purchase] | int:

    purchases = purchase_repo.list_purchases(
        db,
        search=search,
        skip=skip,
        limit=limit,
        count_only=count_only,
    )

    if count_only:
        return purchases

    return [
        _attach_purchase_fields(
            purchase
        )
        for purchase in purchases
    ]


# =============================================================================
# Update Purchase
# =============================================================================
def update_purchase_by_id(
    db: Session,
    purchase_id: int,
    purchase_data: PurchaseUpdate,
) -> Purchase:

    purchase = (
        purchase_validation
        .validate_and_get_active_purchase(
            db,
            purchase_id,
        )
    )

    if "done_by" in purchase_data.model_fields_set:
        validate_done_by_snapshot(db, purchase_data.done_by, previous=purchase.done_by)

    # -------------------------------------------------------------------------
    # Capture OLD account values before SQLAlchemy object is mutated.
    # -------------------------------------------------------------------------
    old_party_id = purchase.party_id
    old_grand_total = Decimal(
        str(purchase.grand_total or 0)
    )

    try:
        provided = purchase_data.model_fields_set
        update_payload = {}

        if "is_active" in provided:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Purchase active status cannot be changed. "
                    "Purchase bills cannot be deleted."
                ),
            )

        # -------------------------------------------------------------------------
        # Effective Party
        # -------------------------------------------------------------------------
        party_id = (
            purchase_data.party_id
            if (
                "party_id" in provided
                and purchase_data.party_id is not None
            )
            else purchase.party_id
        )

        party = (
            purchase_validation
            .validate_and_get_active_party(
                db,
                party_id,
            )
        )

        update_payload["party_id"] = party.id

        # -------------------------------------------------------------------------
        # Bill Number
        # -------------------------------------------------------------------------
        bill_no = purchase.bill_no

        if (
            "bill_no" in provided
            and purchase_data.bill_no is not None
        ):
            bill_no = (
                purchase_data.bill_no
                .strip()
                .upper()
            )

            purchase_validation.validate_bill_number_is_unique(
                db,
                bill_no,
                exclude_purchase_id=purchase.id,
            )

        update_payload["bill_no"] = bill_no

        returned = _group_purchase_quantities(
            purchase_return_repo.get_active_return_quantities(db, purchase.bill_no.strip().upper())
        )
        if returned:
            if party_id != purchase.party_id:
                raise HTTPException(400, f"Cannot change the supplier on Purchase {purchase.bill_no} because active Purchase Returns reference this Purchase.")
            if bill_no != purchase.bill_no:
                raise HTTPException(400, f"Cannot change the number of Purchase {purchase.bill_no} because active Purchase Returns reference this Purchase.")

        # -------------------------------------------------------------------------
        # Effective GST
        # -------------------------------------------------------------------------
        effective_is_gst = (
            purchase_data.is_gst
            if (
                "is_gst" in provided
                and purchase_data.is_gst is not None
            )
            else purchase.is_gst
        )

        # -------------------------------------------------------------------------
        # Items Updated
        # -------------------------------------------------------------------------
        if (
            "items" in provided
            and purchase_data.items is not None
        ):
            old_quantities = _group_purchase_quantities(
                purchase.items
            )

            validated_new_items = {}

            for item_data in purchase_data.items:
                item_master = _resolve_purchase_item(
                    db,
                    item_data,
                )

                hsn_code = item_data.hsn_code.strip()

                purchase_validation.validate_hsn_code_present(
                    hsn_code,
                    item_master.name,
                )

                item_data.item_id = item_master.id

                validated_new_items[
                    item_master.id
                ] = item_master

            new_quantities = _group_purchase_quantities(
                purchase_data.items
            )

            names = {line.item_id: line.item_name for line in purchase.items}
            for item_id, returned_quantity in returned.items():
                proposed = new_quantities.get(item_id, Decimal(0))
                if proposed < returned_quantity:
                    name = names.get(item_id, f"Item {item_id}")
                    action = f"remove {name} from" if proposed == 0 else f"reduce {name} quantity to {proposed:f} on"
                    raise HTTPException(400, (
                        f"Cannot {action} Purchase {purchase.bill_no} because {returned_quantity:f} units "
                        "have already been returned against this Purchase."
                    ))

            all_item_ids = (
                set(old_quantities.keys())
                | set(new_quantities.keys())
            )

            stock_objects = {}
            resulting_stocks = {}

            # ---------------------------------------------------------------------
            # Validate resulting stock first
            # ---------------------------------------------------------------------
            for item_id in all_item_ids:
                item_master = (
                    item_master_repo
                    .get_item_by_id(
                        db,
                        item_id,
                        include_inactive=True,
                    )
                )

                if not item_master:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Item with ID {item_id} not found",
                    )

                resulting_stocks[item_id] = purchase_validation.validate_purchase_stock_adjustment(
                    db=db,
                    item_id=item_id,
                    item_name=item_master.name,
                    current_stock=item_master.current_stock or 0.0,
                    old_quantity=old_quantities.get(item_id, Decimal(0)),
                    new_quantity=new_quantities.get(item_id, Decimal(0)),
                )

                stock_objects[item_id] = item_master

            # ---------------------------------------------------------------------
            # Apply stock differences
            # ---------------------------------------------------------------------
            for item_id in all_item_ids:
                stock_objects[item_id].current_stock = resulting_stocks[item_id]

            # ---------------------------------------------------------------------
            # Recalculate Purchase Totals
            # ---------------------------------------------------------------------
            (
                taxable_total,
                sgst_total,
                cgst_total,
                igst_total,
                round_off,
                grand_total,
                line_amounts,
            ) = _calculate_purchase_totals(
                purchase_data.items,
                is_gst=effective_is_gst,
            )

            effective_bill_date = (
                purchase_data.bill_date
                if (
                    "bill_date" in provided
                    and purchase_data.bill_date is not None
                )
                else purchase.bill_date
            )

            # ---------------------------------------------------------------------
            # Replace Purchase Items
            # ---------------------------------------------------------------------
            for old_item in list(purchase.items):
                purchase_repo.delete_purchase_item(
                    db,
                    old_item,
                )

            for item_data, line in zip(
                purchase_data.items,
                line_amounts,
            ):
                item_master = validated_new_items[
                    item_data.item_id
                ]

                item_payload = {
                    "purchase_id": purchase.id,
                    "item_id": item_master.id,
                    "item_name": item_master.name,
                    "hsn_code": item_data.hsn_code.strip(),
                    "quantity": item_data.quantity,
                    "unit": item_master.unit,
                    "price": item_data.price,
                    "disc_percent": (
                        item_data.disc_percent or 0.0
                    ),
                    "sgst": line["sgst"],
                    "cgst": line["cgst"],
                    "igst": line["igst"],
                    "amount": line["amount"],
                }

                purchase_repo.create_purchase_item(
                    db,
                    item_payload,
                )

                item_master.purchase_price = (
                    item_data.price
                )

                item_master.last_purchase_date = (
                    effective_bill_date
                )

            update_payload.update(
                {
                    "taxable_amount": taxable_total,
                    "sgst_total": sgst_total,
                    "cgst_total": cgst_total,
                    "igst_total": igst_total,
                    "round_off": round_off,
                    "grand_total": grand_total,
                }
            )

        # -------------------------------------------------------------------------
        # GST Changed Without Items
        # -------------------------------------------------------------------------
        elif "is_gst" in provided:
            (
                taxable_total,
                sgst_total,
                cgst_total,
                igst_total,
                round_off,
                grand_total,
                _,
            ) = _calculate_purchase_totals(
                purchase.items,
                is_gst=effective_is_gst,
            )

            update_payload.update(
                {
                    "taxable_amount": taxable_total,
                    "sgst_total": sgst_total,
                    "cgst_total": cgst_total,
                    "igst_total": igst_total,
                    "round_off": round_off,
                    "grand_total": grand_total,
                }
            )

        # -------------------------------------------------------------------------
        # Simple Fields
        # -------------------------------------------------------------------------
        simple_fields = [
            "order_no",
            "bill_date",
            "due_term",
            "due_date",
            "is_gst",
            "contact_person",
            "contact_no",
            "email",
            "done_by",
            "brokerage",
            "broker_remarks",
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
            if field in provided:
                value = getattr(
                    purchase_data,
                    field,
                )

                if (
                    field == "order_no"
                    and value
                ):
                    value = value.strip()

                update_payload[field] = value

        # -------------------------------------------------------------------------
        # Due Date Recalculation
        # -------------------------------------------------------------------------
        effective_bill_date = (
            update_payload.get(
                "bill_date",
                purchase.bill_date,
            )
        )

        effective_due_term = (
            update_payload.get(
                "due_term",
                purchase.due_term,
            )
        )

        if "due_term" in provided:
            if purchase_data.due_term is None:
                update_payload["due_date"] = None
            else:
                update_payload["due_date"] = (
                    effective_bill_date
                    + timedelta(
                        days=purchase_data.due_term
                    )
                )

        elif (
            "bill_date" in provided
            and effective_due_term is not None
        ):
            update_payload["due_date"] = (
                effective_bill_date
                + timedelta(
                    days=effective_due_term
                )
            )

        # -------------------------------------------------------------------------
        # Update Purchase
        # -------------------------------------------------------------------------
        updated_purchase = (
            purchase_repo.update_purchase(
                db,
                purchase,
                update_payload,
            )
        )

        # -------------------------------------------------------------------------
        # Supplier Running Balance
        # -------------------------------------------------------------------------
        new_party_id = updated_purchase.party_id

        new_grand_total = Decimal(
            str(updated_purchase.grand_total or 0)
        )

        # Same supplier:
        # only apply difference between old and new purchase totals.
        if old_party_id == new_party_id:
            balance_delta = (
                new_grand_total
                - old_grand_total
            )

            if balance_delta != 0:
                apply_party_balance_delta(
                    db,
                    new_party_id,
                    balance_delta,
                )

        # Supplier changed:
        # reverse old supplier purchase,
        # then apply complete purchase to new supplier.
        else:
            # Consistent account lock order for opposite-direction switches.
            for party_id, delta in sorted(((old_party_id, -old_grand_total), (new_party_id, new_grand_total))):
                apply_party_balance_delta(db, party_id, delta)

        # -------------------------------------------------------------------------
        # One final transaction commit
        # -------------------------------------------------------------------------
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(updated_purchase)

    updated_purchase.party_name = party.name

    return updated_purchase
