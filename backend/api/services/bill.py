from api.validation.done_by import validate_done_by_snapshot
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.repository import bill as bill_repo
from api.repository import sales_return as sales_return_repo
from api.validation import bill as bill_validation


# =============================================================================
# NUMBER TO WORDS HELPERS
# =============================================================================

_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]

_TENS = [
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
]


def _two_digit_words(number: int) -> str:
    """
    Converts a two-digit number into words.
    """

    if number < 20:
        return _ONES[number]

    tens, ones = divmod(
        number,
        10,
    )

    return (
        _TENS[tens]
        + (
            " " + _ONES[ones]
            if ones
            else ""
        )
    ).strip()


def _three_digit_words(number: int) -> str:
    """
    Converts a number up to three digits into words.
    """

    if number >= 100:

        hundreds, remaining = divmod(
            number,
            100,
        )

        return (
            _ONES[hundreds]
            + " Hundred"
            + (
                " " + _two_digit_words(remaining)
                if remaining
                else ""
            )
        )

    return _two_digit_words(number)


def _number_to_words_indian(
    number: int,
) -> str:
    """
    Converts integer value using Indian numbering format.

    Example:
        Crore
        Lakh
        Thousand
        Hundred
    """

    if number == 0:
        return "Zero"

    crore, number = divmod(
        number,
        10000000,
    )

    lakh, number = divmod(
        number,
        100000,
    )

    thousand, number = divmod(
        number,
        1000,
    )

    remaining = number

    parts = []

    if crore:
        parts.append(
            _three_digit_words(crore)
            + " Crore"
        )

    if lakh:
        parts.append(
            _three_digit_words(lakh)
            + " Lakh"
        )

    if thousand:
        parts.append(
            _three_digit_words(thousand)
            + " Thousand"
        )

    if remaining:
        parts.append(
            _three_digit_words(remaining)
        )

    return " ".join(parts)


def _amount_in_words(
    grand_total: float,
) -> str:
    """
    Converts grand total into Rupees / Paise words.
    """

    rupees = int(grand_total)

    paise = round(
        (grand_total - rupees)
        * 100
    )

    words = (
        f"{_number_to_words_indian(rupees)} Rupees"
    )

    if paise:
        words += (
            f" and "
            f"{_number_to_words_indian(paise)} "
            f"Paise"
        )

    return words + " Only"


# =============================================================================
# INVOICE NUMBER
# =============================================================================

def _generate_invoice_no(
    db: Session,
) -> str:
    """
    Generates next numeric Sales invoice number.
    """

    existing_invoices = (
        bill_repo.get_all_invoice_numbers(
            db
        )
    )

    numeric_numbers = [
        int(invoice)
        for invoice in existing_invoices
        if invoice.isdigit()
    ]

    next_number = (
        max(
            numeric_numbers,
            default=0,
        )
        + 1
    )

    while bill_repo.invoice_no_exists(
        db,
        str(next_number),
    ):
        next_number += 1

    return str(next_number)

# =============================================================================
# ITEM / GST CALCULATION
# =============================================================================
def _money(value):
    # Sales only: round each persisted monetary component to paise.
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _saved_discount_percent(line):
    gross = float(line.rate) * float(line.quantity)
    return float(line.discount_amount or 0) * 100 / gross if gross else 0.0


def _compute_item_taxes(item, quantity, is_interstate, inputs, is_gst=True, saved=None):
    rate = inputs.rate if inputs.rate is not None else (saved.rate if saved else item.sale_price or 0)
    discount = inputs.disc_percent if inputs.disc_percent is not None else (_saved_discount_percent(saved) if saved else 0)
    if inputs.cgst is not None:
        cgst, sgst, igst = inputs.cgst, inputs.sgst, inputs.igst
    elif saved is not None:
        cgst, sgst, igst = saved.cgst_percent, saved.sgst_percent, saved.igst_percent
    elif is_interstate:
        cgst, sgst, igst = 0, 0, (item.cgst or 0) + (item.sgst or 0)
    else:
        cgst, sgst, igst = item.cgst or 0, item.sgst or 0, 0
    if is_gst is False:
        cgst, sgst, igst = 0, 0, 0
    values = [rate, discount, cgst, sgst, igst]
    if not all(isfinite(float(value)) and value >= 0 for value in values) or any(value > 100 for value in values[1:]):
        raise HTTPException(400, "Invalid sales rate, discount or GST percentage")
    if igst > 0 and (cgst > 0 or sgst > 0):
        raise HTTPException(400, "IGST cannot be combined with CGST or SGST")
    result = dict(item=item, quantity=quantity, rate=float(rate), gst_percent=cgst + sgst + igst,
                  cgst_percent=cgst, sgst_percent=sgst, igst_percent=igst)
    # Preserve already-booked amounts on an unchanged line, including legacy rounding.
    if saved is not None and quantity == saved.quantity and rate == saved.rate and abs(discount - _saved_discount_percent(saved)) < 1e-10 and (cgst, sgst, igst) == (saved.cgst_percent, saved.sgst_percent, saved.igst_percent):
        result.update({key: float(getattr(saved, key) or 0) for key in
                       ("discount_amount", "taxable_amount", "cgst_amount", "sgst_amount", "igst_amount", "line_total")})
        result["gross_amount"] = _money(result["taxable_amount"] + result["discount_amount"])
        result["saved_line_id"] = saved.bill_item_id
        return result
    gross = _money(Decimal(str(rate)) * Decimal(str(quantity)))
    discount_amount = _money(Decimal(str(gross)) * Decimal(str(discount)) / 100)
    taxable = _money(Decimal(str(gross)) - Decimal(str(discount_amount)))
    taxes = [_money(Decimal(str(taxable)) * Decimal(str(percent)) / 100) for percent in (cgst, sgst, igst)]
    result.update(gross_amount=gross, discount_amount=discount_amount, taxable_amount=taxable,
                  cgst_amount=taxes[0], sgst_amount=taxes[1], igst_amount=taxes[2],
                  line_total=_money(Decimal(str(taxable)) + sum(Decimal(str(tax)) for tax in taxes)))
    return result


# =============================================================================
# BILL TOTALS
# =============================================================================

def _calculate_bill_totals(resolved_items, saved_bill=None):
    # A metadata-only edit must not change a historical invoice's rounding.
    if saved_bill is not None and sorted(row.get("saved_line_id", -1) for row in resolved_items) == sorted(row.bill_item_id for row in saved_bill.bill_items):
        return dict(subtotal=saved_bill.subtotal, discount_amount=saved_bill.discount_amount,
                    taxable_amount=saved_bill.taxable_amount, cgst_total=saved_bill.cgst_amount,
                    sgst_total=saved_bill.sgst_amount, igst_total=saved_bill.igst_amount,
                    grand_total=saved_bill.grand_total, total_boxes=saved_bill.total_boxes,
                    amount_in_words=saved_bill.amount_in_words)
    def total(field):
        return _money(sum(Decimal(str(row[field])) for row in resolved_items))
    grand_total = total("line_total")
    return dict(subtotal=total("gross_amount"), discount_amount=total("discount_amount"),
                taxable_amount=total("taxable_amount"), cgst_total=total("cgst_amount"),
                sgst_total=total("sgst_amount"), igst_total=total("igst_amount"),
                grand_total=grand_total, total_boxes=int(sum(row["quantity"] for row in resolved_items)),
                amount_in_words=_amount_in_words(grand_total))


# =============================================================================
# GROUP QUANTITY BY ITEM
# =============================================================================

def _group_item_quantities(
    items,
) -> dict[int, int]:
    """
    Groups quantities by item_id.

    This is important when the same item appears more
    than once in the same bill.

    Example:

        Item 5 = 4 qty
        Item 5 = 3 qty

    Result:

        {
            5: 7
        }
    """

    quantities = defaultdict(
        int
    )

    for item in items:

        quantities[
            item.item_id
        ] += int(
            item.quantity
            or 0
        )

    return dict(
        quantities
    )


# =============================================================================
# RESOLVE SALES ITEMS
# =============================================================================

def _resolve_bill_items(db, items_data, is_interstate, is_gst=True, saved_items=()):
    resolved_items = []
    item_cache = {}
    saved_by_id = {row.bill_item_id: row for row in saved_items}
    saved_by_item = defaultdict(list)
    for row in saved_items:
        saved_by_item[row.item_id].append(row)
    for inputs in items_data:
        saved = None
        if inputs.bill_item_id is not None:
            saved = saved_by_id.get(inputs.bill_item_id)
            if saved is None or saved.item_id != inputs.item_id:
                raise HTTPException(400, "Bill item does not belong to this invoice/item")
        elif len(saved_by_item[inputs.item_id]) == 1:
            saved = saved_by_item[inputs.item_id][0]
        elif saved_by_item[inputs.item_id] and any(value is None for value in (inputs.rate, inputs.disc_percent, inputs.cgst)):
            raise HTTPException(400, "Specify bill_item_id to preserve duplicate invoice line inputs")
        if inputs.item_id not in item_cache:
            # Existing invoice items can be reversed/edited after deactivation.
            if saved_by_item[inputs.item_id]:
                item = bill_repo.get_item_by_id_any_status(db, inputs.item_id)
                if item is None:
                    raise HTTPException(404, f"Item with ID {inputs.item_id} not found")
                item_cache[inputs.item_id] = item
            else:
                item_cache[inputs.item_id] = bill_validation.validate_and_get_active_item(db, inputs.item_id)
        resolved_items.append(_compute_item_taxes(item_cache[inputs.item_id], inputs.quantity,
                              is_interstate, inputs, is_gst, saved))
    return resolved_items


# =============================================================================
# CREATE STOCK VALIDATION
# =============================================================================

def _validate_create_stock(
    db: Session,
    items_data,
) -> None:
    """
    Validate total Sales quantity against ItemMaster stock.

    Quantities are grouped first so duplicate lines cannot
    bypass stock validation.
    """

    quantities = (
        _group_item_quantities(
            items_data
        )
    )

    for item_id, requested_quantity in quantities.items():

        item = (
            bill_validation
            .validate_and_get_active_item(
                db,
                item_id,
            )
        )

        bill_validation.validate_sufficient_stock(item, requested_quantity)


# =============================================================================
# SALES UPDATE STOCK VALIDATION
# =============================================================================

def _validate_update_stock(
    db: Session,
    old_quantities: dict[int, int],
    new_quantities: dict[int, int],
) -> dict:
    """
    Validates stock for Sales update.

    Sales removes stock.

    Therefore:

        resulting_stock
            = current_stock
            + old_sold_quantity
            - new_sold_quantity

    Example:

        Original Sale = 10
        Current stock = 5
        New Sale      = 13

        resulting_stock =
            5 + 10 - 13
            = 2

        Valid.
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

        item = (
            bill_repo
            .get_item_by_id_any_status(
                db,
                item_id,
            )
        )

        if not item:

            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    f"Item with ID "
                    f"{item_id} not found"
                ),
            )

        additional_required = new_quantities.get(item_id, 0) - old_quantities.get(item_id, 0)
        bill_validation.validate_sufficient_stock(item, additional_required, additional=True)

        item_objects[
            item_id
        ] = item

    return item_objects


# =============================================================================
# CREATE SALES BILL
# =============================================================================

def create_bill(
    db: Session,
    bill_data,
):
    """
    Create Sales bill.

    Stock behavior:
        SALES CREATE -> DEDUCT STOCK
    """

    # -------------------------------------------------------------------------
    # Customer
    # -------------------------------------------------------------------------

    validate_done_by_snapshot(db, bill_data.done_by)

    customer = (
        bill_validation
        .validate_and_get_active_customer(
            db,
            bill_data.customer_id,
        )
    )

    # -------------------------------------------------------------------------
    # Validate stock BEFORE creating anything
    # -------------------------------------------------------------------------

    _validate_create_stock(
        db,
        bill_data.items,
    )

    # -------------------------------------------------------------------------
    # Resolve items / tax calculation
    # -------------------------------------------------------------------------

    resolved_items = (
        _resolve_bill_items(
            db,
            bill_data.items,
            bill_data.is_interstate,
            is_gst=bill_data.is_gst,
        )
    )

    totals = (
        _calculate_bill_totals(
            resolved_items
        )
    )

    # -------------------------------------------------------------------------
    # Parent Bill
    # -------------------------------------------------------------------------

    bill_payload = {
        "invoice_no": (
            _generate_invoice_no(
                db
            )
        ),

        "customer_id": (
            customer.id
        ),

        "bill_date": (
            bill_data.bill_date
        ),

        "due_term": (
            bill_data.due_term
        ),

        "due_date": (
            bill_data.due_date
        ),

        "is_interstate": any(row["igst_percent"] > 0 for row in resolved_items),

        # Buyer snapshot
        "customer_name": (
            customer.customer_name
        ),

        "mobile": (
            customer.mobile
        ),

        "email": (
            customer.email
        ),

        "address": (
            customer.address
        ),

        "city": (
            customer.city
        ),

        "state": (
            customer.state
        ),

        "pincode": (
            customer.pincode
        ),

        "buyer_gstin": (
            customer.gstin
        ),

        "buyer_pan": (
            customer.pan_card
        ),

        "buyer_state_code": (
            customer.state_code
        ),

        "done_by": (
            bill_data.done_by
        ),

        "brokerage": (
            bill_data.brokerage
            or 0.0
        ),

        "broker_remarks": (
            bill_data.broker_remarks
        ),

        "total_boxes": (
            totals["total_boxes"]
        ),

        "subtotal": (
            totals["subtotal"]
        ),

        "discount_amount": totals["discount_amount"],

        "taxable_amount": (
            totals[
                "taxable_amount"
            ]
        ),

        "cgst_amount": (
            totals["cgst_total"]
        ),

        "sgst_amount": (
            totals["sgst_total"]
        ),

        "igst_amount": (
            totals["igst_total"]
        ),

        "grand_total": (
            totals["grand_total"]
        ),

        "amount_in_words": (
            totals[
                "amount_in_words"
            ]
        ),

        "delivery_date": (
            bill_data.delivery_date
        ),

        "ship_to": (
            bill_data.ship_to
        ),

        "ship_to_address": (
            bill_data.ship_to_address
        ),

        "shipping_state": (
            bill_data.shipping_state
        ),

        "transport": (
            bill_data.transport
        ),

        "reference": (
            bill_data.reference
        ),

        "remarks": (
            bill_data.remarks
        ),

        "show_shipping_address_on_bill": (
            bill_data
            .show_shipping_address_on_bill
        ),

        "is_active": True,
    }

    try:
        bill = (
            bill_repo.create_bill(
                db,
                bill_payload,
            )
        )

        # -------------------------------------------------------------------------
        # Create lines + deduct stock
        # -------------------------------------------------------------------------

        for item_data in resolved_items:

            item = item_data[
                "item"
            ]

            bill_item_payload = {
                "bill_id": bill.bill_id,
                "item_id": item.id,
                "item_name": item.name,
                "brand_name": item.brand,
                "hsn_code": (
                    item.hsn_code
                    or ""
                ),
                "unit": item.unit,
                "quantity": (
                    item_data["quantity"]
                ),
                "rate": (
                    item_data["rate"]
                ),
                "discount_amount": item_data["discount_amount"],
                "taxable_amount": (
                    item_data[
                        "taxable_amount"
                    ]
                ),
                "gst_percent": (
                    item_data[
                        "gst_percent"
                    ]
                ),
                "cgst_percent": (
                    item_data[
                        "cgst_percent"
                    ]
                ),
                "sgst_percent": (
                    item_data[
                        "sgst_percent"
                    ]
                ),
                "igst_percent": (
                    item_data[
                        "igst_percent"
                    ]
                ),
                "cgst_amount": (
                    item_data[
                        "cgst_amount"
                    ]
                ),
                "sgst_amount": (
                    item_data[
                        "sgst_amount"
                    ]
                ),
                "igst_amount": (
                    item_data[
                        "igst_amount"
                    ]
                ),
                "line_total": (
                    item_data[
                        "line_total"
                    ]
                ),
                "is_active": True,
            }

            bill_repo.create_bill_item(
                db,
                bill_item_payload,
            )

            # =====================================================================
            # SALES CREATE -> DEDUCT STOCK
            # =====================================================================

            item.current_stock = (
                float(
                    item.current_stock
                    or 0.0
                )
                - float(
                    item_data[
                        "quantity"
                    ]
                )
            )

            item.last_sale_date = (
                bill_data.bill_date
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(bill)

    return bill


# =============================================================================
# GET ALL SALES BILLS
# =============================================================================

def get_all_bills(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
):
    return bill_repo.list_bills(
        db,
        search=search,
        skip=skip,
        limit=limit,
        count_only=count_only,
    )


# =============================================================================
# GET SALES BILL
# =============================================================================

def get_bill_by_id(
    db: Session,
    bill_id: int,
):
    """
    Returns Bill + BillItems.

    Router should use BillDetailResponse.
    """

    bill = (
        bill_validation
        .validate_and_get_active_bill(
            db,
            bill_id,
        )
    )

    return {
        "bill": bill,
        "items": bill.bill_items,
    }


# =============================================================================
# UPDATE SALES BILL
# =============================================================================

def update_bill(
    db: Session,
    bill_id: int,
    bill_data,
):
    """
    Update Sales bill.

    Stock behavior:

        old sale effect must be replaced
        by new sale effect.

    Formula:

        current_stock
        + old_sold_quantity
        - new_sold_quantity
    """

    # -------------------------------------------------------------------------
    # Existing Bill
    # -------------------------------------------------------------------------

    bill = (
        bill_validation
        .validate_and_get_active_bill(
            db,
            bill_id,
        )
    )

    if "done_by" in bill_data.model_fields_set:
        validate_done_by_snapshot(db, bill_data.done_by, previous=bill.done_by)
    effective_done_by = bill_data.done_by if "done_by" in bill_data.model_fields_set else bill.done_by

    # -------------------------------------------------------------------------
    # Customer
    # -------------------------------------------------------------------------

    customer = (
        bill_validation
        .validate_and_get_active_customer(
            db,
            bill_data.customer_id,
        )
    )

    # -------------------------------------------------------------------------
    # OLD quantities
    # -------------------------------------------------------------------------

    old_quantities = (
        _group_item_quantities(
            bill.bill_items
        )
    )

    # -------------------------------------------------------------------------
    # NEW quantities
    # -------------------------------------------------------------------------

    new_quantities = (
        _group_item_quantities(
            bill_data.items
        )
    )

    returned = defaultdict(Decimal)
    for row in sales_return_repo.get_active_return_quantities(db, bill.invoice_no.strip().upper()):
        returned[row.item_id] += Decimal(str(row.quantity))
    if returned and bill_data.customer_id != bill.customer_id:
        raise HTTPException(400, f"Cannot change the customer on invoice {bill.invoice_no} because active Sales Returns reference this invoice.")
    names = {line.item_id: line.item_name for line in bill.bill_items}
    for item_id, returned_quantity in returned.items():
        proposed = new_quantities.get(item_id, 0)
        if proposed < returned_quantity:
            name = names.get(item_id, f"Item {item_id}")
            action = f"remove {name} from" if proposed == 0 else f"reduce {name} quantity to {proposed} on"
            raise HTTPException(400, (
                f"Cannot {action} invoice {bill.invoice_no} because {returned_quantity:f} units "
                "have already been returned against this invoice."
            ))

    # -------------------------------------------------------------------------
    # Validate complete resulting stock BEFORE changing anything
    # -------------------------------------------------------------------------

    stock_items = (
        _validate_update_stock(
            db,
            old_quantities,
            new_quantities,
        )
    )

    # -------------------------------------------------------------------------
    # Validate new ItemMaster rows and calculate taxes
    # -------------------------------------------------------------------------

    resolved_items = (
        _resolve_bill_items(
            db,
            bill_data.items,
            bill_data.is_interstate,
            is_gst=bill_data.is_gst,
            saved_items=bill.bill_items,
        )
    )

    totals = (
        _calculate_bill_totals(
            resolved_items, saved_bill=bill
        )
    )

    # -------------------------------------------------------------------------
    # Apply Sales stock differences
    # -------------------------------------------------------------------------

    try:
        all_item_ids = (
            set(
                old_quantities.keys()
            )
            | set(
                new_quantities.keys()
            )
        )

        for item_id in all_item_ids:

            item = (
                stock_items[
                    item_id
                ]
            )

            # Restore reductions; deduct only the additional aggregate quantity.
            stock_difference = old_quantities.get(item_id, 0) - new_quantities.get(item_id, 0)
            item.current_stock = float(item.current_stock or 0.0) + stock_difference

        # -------------------------------------------------------------------------
        # Remove old BillItem records
        #
        # This does NOT delete the Bill.
        # -------------------------------------------------------------------------

        for old_item in list(
            bill.bill_items
        ):

            bill_repo.delete_bill_item(
                db,
                old_item,
            )

        # -------------------------------------------------------------------------
        # Create new BillItem records
        # -------------------------------------------------------------------------

        for item_data in resolved_items:

            item = item_data[
                "item"
            ]

            bill_item_payload = {
                "bill_id": bill.bill_id,
                "item_id": item.id,
                "item_name": item.name,
                "brand_name": item.brand,
                "hsn_code": (
                    item.hsn_code
                    or ""
                ),
                "unit": item.unit,
                "quantity": (
                    item_data["quantity"]
                ),
                "rate": (
                    item_data["rate"]
                ),
                "discount_amount": item_data["discount_amount"],
                "taxable_amount": (
                    item_data[
                        "taxable_amount"
                    ]
                ),
                "gst_percent": (
                    item_data[
                        "gst_percent"
                    ]
                ),
                "cgst_percent": (
                    item_data[
                        "cgst_percent"
                    ]
                ),
                "sgst_percent": (
                    item_data[
                        "sgst_percent"
                    ]
                ),
                "igst_percent": (
                    item_data[
                        "igst_percent"
                    ]
                ),
                "cgst_amount": (
                    item_data[
                        "cgst_amount"
                    ]
                ),
                "sgst_amount": (
                    item_data[
                        "sgst_amount"
                    ]
                ),
                "igst_amount": (
                    item_data[
                        "igst_amount"
                    ]
                ),
                "line_total": (
                    item_data[
                        "line_total"
                    ]
                ),
                "is_active": True,
            }

            bill_repo.create_bill_item(
                db,
                bill_item_payload,
            )

            # Latest Sales date
            item.last_sale_date = (
                bill_data.bill_date
            )

        # -------------------------------------------------------------------------
        # Parent Sales Bill
        # -------------------------------------------------------------------------

        update_payload = {
            "customer_id": (
                customer.id
            ),

            "bill_date": (
                bill_data.bill_date
            ),

            "due_term": (
                bill_data.due_term
            ),

            "due_date": (
                bill_data.due_date
            ),

            "is_interstate": any(row["igst_percent"] > 0 for row in resolved_items),

            # Refresh customer snapshot
            "customer_name": (
                customer.customer_name
            ),

            "mobile": (
                customer.mobile
            ),

            "email": (
                customer.email
            ),

            "address": (
                customer.address
            ),

            "city": (
                customer.city
            ),

            "state": (
                customer.state
            ),

            "pincode": (
                customer.pincode
            ),

            "buyer_gstin": (
                customer.gstin
            ),

            "buyer_pan": (
                customer.pan_card
            ),

            "buyer_state_code": (
                customer.state_code
            ),

            "done_by": effective_done_by,

            "brokerage": (
                bill_data.brokerage
                or 0.0
            ),

            "broker_remarks": (
                bill_data.broker_remarks
            ),

            "total_boxes": (
                totals[
                    "total_boxes"
                ]
            ),

            "subtotal": (
                totals[
                    "subtotal"
                ]
            ),

            "discount_amount": totals["discount_amount"],

            "taxable_amount": (
                totals[
                    "taxable_amount"
                ]
            ),

            "cgst_amount": (
                totals[
                    "cgst_total"
                ]
            ),

            "sgst_amount": (
                totals[
                    "sgst_total"
                ]
            ),

            "igst_amount": (
                totals[
                    "igst_total"
                ]
            ),

            "grand_total": (
                totals[
                    "grand_total"
                ]
            ),

            "amount_in_words": (
                totals[
                    "amount_in_words"
                ]
            ),

            "delivery_date": (
                bill_data.delivery_date
            ),

            "ship_to": (
                bill_data.ship_to
            ),

            "ship_to_address": (
                bill_data.ship_to_address
            ),

            "shipping_state": (
                bill_data.shipping_state
            ),

            "transport": (
                bill_data.transport
            ),

            "reference": (
                bill_data.reference
            ),

            "remarks": (
                bill_data.remarks
            ),

            "show_shipping_address_on_bill": (
                bill_data
                .show_shipping_address_on_bill
            ),
        }

        updated_bill = (
            bill_repo.update_bill(
                db,
                bill,
                update_payload,
            )
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(
        updated_bill
    )

    return get_bill_by_id(db, updated_bill.bill_id)


# =============================================================================
# DELETE SALES BILL
# =============================================================================

def delete_bill(
    db: Session,
    bill_id: int,
):
    """
    Delete/Deactivate Sales bill.

    SALES DELETE -> RESTORE STOCK

    We retain the bill in the database using is_active=False,
    while restoring the inventory consumed by the Sale.
    """

    bill = (
        bill_validation
        .validate_and_get_active_bill(
            db,
            bill_id,
        )
    )

    # -------------------------------------------------------------------------
    # Restore sold quantities
    # -------------------------------------------------------------------------

    if sales_return_repo.get_active_return_quantities(db, bill.invoice_no.strip().upper()).first() is not None:
        raise HTTPException(400, (
            f"Cannot delete invoice {bill.invoice_no} because active Sales Returns reference this invoice. "
            "Delete or correct those Sales Returns first."
        ))

    try:
        for bill_item in bill.bill_items:

            item_master = (
                bill_repo
                .get_item_by_id_any_status(
                    db,
                    bill_item.item_id,
                )
            )

            if not item_master:

                raise HTTPException(
                    status_code=(
                        status.HTTP_404_NOT_FOUND
                    ),
                    detail=(
                        f"Item with ID "
                        f"{bill_item.item_id} "
                        f"not found."
                    ),
                )

            # =====================================================================
            # SALES DELETE -> ADD STOCK BACK
            # =====================================================================

            item_master.current_stock = (
                float(
                    item_master.current_stock
                    or 0.0
                )
                + float(
                    bill_item.quantity
                )
            )

        # Soft-delete Sales Bill
        bill_repo.deactivate_bill(
            db,
            bill,
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": (
            f"Bill '{bill.invoice_no}' "
            f"deleted successfully"
        )
    }
