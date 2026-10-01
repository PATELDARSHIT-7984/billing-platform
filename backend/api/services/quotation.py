from api.validation.done_by import validate_done_by_snapshot
from api.utils.rounding import round_half_up
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from api.model.quotation import Quotation
from api.repository import quotation as quotation_repo
from api.schema.quotation import QuotationCreate, QuotationUpdate
from api.validation import quotation as quotation_validation


def _next_document_number(db: Session, column, prefix: str) -> str:
    last_value = quotation_repo.get_last_column_value(db, column)

    if not last_value:
        return f"{prefix}-0001"

    digits = "".join(
        character
        for character in str(last_value)
        if character.isdigit()
    )

    next_number = int(digits or 0) + 1

    return f"{prefix}-{next_number:04d}"


def _calculate_quotation_totals(
    items,
    is_gst: bool,
) -> tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    list[dict],
]:
    taxable_total = 0.0
    sgst_total = 0.0
    cgst_total = 0.0
    igst_total = 0.0
    lines = []

    for item in items:
        discount_rate = item.disc_percent or 0.0

        if is_gst:
            sgst_rate = item.sgst or 0.0
            cgst_rate = item.cgst or 0.0
            igst_rate = item.igst or 0.0

            quotation_validation.validate_gst_type_is_exclusive(
                sgst_rate,
                cgst_rate,
                igst_rate,
            )
        else:
            sgst_rate = 0.0
            cgst_rate = 0.0
            igst_rate = 0.0

        gross = item.quantity * item.price
        discount = gross * discount_rate / 100
        taxable = gross - discount

        sgst_amount = taxable * sgst_rate / 100
        cgst_amount = taxable * cgst_rate / 100
        igst_amount = taxable * igst_rate / 100

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

        lines.append({
            "amount": round_half_up(amount, 2),
        })

    net_total = (
        taxable_total
        + sgst_total
        + cgst_total
        + igst_total
    )

    grand_total = round_half_up(net_total, 0)
    round_off = grand_total - net_total

    return (
        round_half_up(taxable_total, 2),
        round_half_up(sgst_total, 2),
        round_half_up(cgst_total, 2),
        round_half_up(igst_total, 2),
        round_half_up(round_off, 2),
        round_half_up(grand_total, 2),
        lines,
    )


def _attach_history_fields(
    quotation: Quotation,
) -> Quotation:
    quotation.customer_name = (
        quotation.customer.customer_name
        if quotation.customer
        else "Unknown"
    )

    quotation.item_count = len(quotation.items)
    quotation.item_names = [
        item.item_name
        for item in quotation.items
    ]
    quotation.hsn_codes = [
        item.hsn_code
        for item in quotation.items
    ]
    quotation.total_boxes = sum(
        item.quantity
        for item in quotation.items
    )

    return quotation


def _build_quotation_item(
    db: Session,
    quotation_id: int,
    item_data,
    line: dict,
) -> dict:
    item_master = (
        quotation_validation
        .validate_and_get_active_item(
            db,
            item_data.item_id,
        )
    )

    return {
        "quotation_id": quotation_id,
        "item_id": item_master.id,
        "item_name": item_master.name,
        "hsn_code": item_master.hsn_code,
        "quantity": item_data.quantity,
        "unit": item_master.unit,
        "price": item_data.price,
        "disc_percent": item_data.disc_percent or 0.0,
        "sgst": item_data.sgst or 0.0,
        "cgst": item_data.cgst or 0.0,
        "igst": item_data.igst or 0.0,
        "amount": line["amount"],
    }


def create_quotation(
    db: Session,
    quotation_data: QuotationCreate,
) -> Quotation:
    validate_done_by_snapshot(db, quotation_data.done_by)

    customer = (
        quotation_validation
        .validate_and_get_active_customer(
            db,
            quotation_data.customer_id,
        )
    )

    quotation_no = (
        quotation_data.quotation_no.strip().upper()
        if quotation_data.quotation_no
        else _next_document_number(
            db,
            Quotation.quotation_no,
            "QTN",
        )
    )

    quotation_validation.validate_quotation_number_is_unique(
        db,
        quotation_no,
    )

    order_no = (
        quotation_data.order_no.strip()
        if quotation_data.order_no
        else _next_document_number(
            db,
            Quotation.order_no,
            "QO",
        )
    )

    due_date = quotation_data.due_date

    if quotation_data.due_term is not None:
        due_date = (
            quotation_data.quotation_date
            + timedelta(days=quotation_data.due_term)
        )

    quotation_validation.validate_shipping_details(
        quotation_data.show_shipping_address_on_bill,
        quotation_data.ship_to,
        quotation_data.ship_to_address,
        quotation_data.shipping_state,
    )

    (
        taxable_total,
        sgst_total,
        cgst_total,
        igst_total,
        round_off,
        grand_total,
        lines,
    ) = _calculate_quotation_totals(
        quotation_data.items,
        quotation_data.is_gst,
    )

    quotation_payload = {
        "quotation_no": quotation_no,
        "order_no": order_no,
        "quotation_date": quotation_data.quotation_date,
        "due_term": quotation_data.due_term,
        "due_date": due_date,
        "customer_id": customer.id,
        "is_gst": quotation_data.is_gst,
        "address": quotation_data.address,
        "city": quotation_data.city,
        "state": quotation_data.state,
        "contact_no": quotation_data.contact_no,
        "email": quotation_data.email,
        "done_by": quotation_data.done_by,
        "brokerage": quotation_data.brokerage or 0.0,
        "broker_remarks": quotation_data.broker_remarks,
        "taxable_amount": taxable_total,
        "sgst_total": sgst_total,
        "cgst_total": cgst_total,
        "igst_total": igst_total,
        "round_off": round_off,
        "grand_total": grand_total,
        "delivery_date": quotation_data.delivery_date,
        "ship_to": quotation_data.ship_to,
        "ship_to_address": quotation_data.ship_to_address,
        "shipping_state": quotation_data.shipping_state,
        "transport": quotation_data.transport,
        "reference": quotation_data.reference,
        "remarks": quotation_data.remarks,
        "show_shipping_address_on_bill":
            quotation_data.show_shipping_address_on_bill,
        "is_active": True,
    }

    quotation = quotation_repo.create_quotation(
        db,
        quotation_payload,
    )

    for item_data, line in zip(
        quotation_data.items,
        lines,
    ):
        item_payload = _build_quotation_item(
            db,
            quotation.id,
            item_data,
            line,
        )

        quotation_repo.create_quotation_item(
            db,
            item_payload,
        )

    db.commit()
    db.refresh(quotation)

    return _attach_history_fields(quotation)


def get_quotation_by_id(
    db: Session,
    quotation_id: int,
) -> Quotation:
    quotation = (
        quotation_validation
        .validate_and_get_quotation(
            db,
            quotation_id,
        )
    )

    return _attach_history_fields(quotation)


def get_all_quotations(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Quotation] | int:
    quotations = quotation_repo.list_quotations(
        db,
        search=search,
        skip=skip,
        limit=limit,
        count_only=count_only,
    )

    if count_only:
        return quotations

    return [
        _attach_history_fields(quotation)
        for quotation in quotations
    ]


def update_quotation_by_id(
    db: Session,
    quotation_id: int,
    quotation_data: QuotationUpdate,
) -> Quotation:
    quotation = (
        quotation_validation
        .validate_and_get_quotation(
            db,
            quotation_id,
            include_inactive=True,
        )
    )

    if "done_by" in quotation_data.model_fields_set:
        validate_done_by_snapshot(db, quotation_data.done_by, previous=quotation.done_by)

    fields = quotation_data.model_fields_set
    update_payload = {}

    if (
        "customer_id" in fields
        and quotation_data.customer_id is not None
    ):
        customer = (
            quotation_validation
            .validate_and_get_active_customer(
                db,
                quotation_data.customer_id,
            )
        )

        update_payload["customer_id"] = customer.id

    if (
        "quotation_no" in fields
        and quotation_data.quotation_no is not None
    ):
        quotation_no = (
            quotation_data.quotation_no
            .strip()
            .upper()
        )

        quotation_validation.validate_quotation_number_is_unique(
            db,
            quotation_no,
            exclude_id=quotation.id,
        )

        update_payload["quotation_no"] = quotation_no

    if "order_no" in fields:
        update_payload["order_no"] = (
            quotation_data.order_no.strip()
            if quotation_data.order_no
            else None
        )

    if (
        "quotation_date" in fields
        and quotation_data.quotation_date is not None
    ):
        update_payload["quotation_date"] = (
            quotation_data.quotation_date
        )

    if "due_term" in fields:
        update_payload["due_term"] = quotation_data.due_term

    effective_date = update_payload.get(
        "quotation_date",
        quotation.quotation_date,
    )

    effective_term = update_payload.get(
        "due_term",
        quotation.due_term,
    )

    if (
        "due_term" in fields
        or "quotation_date" in fields
    ):
        if (
            effective_term is not None
            and effective_date
        ):
            update_payload["due_date"] = (
                effective_date
                + timedelta(days=effective_term)
            )
        else:
            update_payload["due_date"] = None

    elif "due_date" in fields:
        update_payload["due_date"] = (
            quotation_data.due_date
        )

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
        "delivery_date",
        "ship_to",
        "ship_to_address",
        "shipping_state",
        "transport",
        "reference",
        "remarks",
        "show_shipping_address_on_bill",
        "is_active",
    ]

    for field in simple_fields:
        if field in fields:
            update_payload[field] = getattr(
                quotation_data,
                field,
            )

    effective_show_shipping = update_payload.get(
        "show_shipping_address_on_bill",
        quotation.show_shipping_address_on_bill,
    )

    effective_ship_to = update_payload.get(
        "ship_to",
        quotation.ship_to,
    )

    effective_ship_to_address = update_payload.get(
        "ship_to_address",
        quotation.ship_to_address,
    )

    effective_shipping_state = update_payload.get(
        "shipping_state",
        quotation.shipping_state,
    )

    quotation_validation.validate_shipping_details(
        effective_show_shipping,
        effective_ship_to,
        effective_ship_to_address,
        effective_shipping_state,
    )

    effective_is_gst = update_payload.get(
        "is_gst",
        quotation.is_gst,
    )

    if (
        "items" in fields
        and quotation_data.items is not None
    ):
        (
            taxable_total,
            sgst_total,
            cgst_total,
            igst_total,
            round_off,
            grand_total,
            lines,
        ) = _calculate_quotation_totals(
            quotation_data.items,
            effective_is_gst,
        )

        new_item_payloads = []

        for item_data, line in zip(
            quotation_data.items,
            lines,
        ):
            new_item_payloads.append(
                _build_quotation_item(
                    db,
                    quotation.id,
                    item_data,
                    line,
                )
            )

        for old_item in list(quotation.items):
            quotation_repo.delete_quotation_item(
                db,
                old_item,
            )

        for item_payload in new_item_payloads:
            quotation_repo.create_quotation_item(
                db,
                item_payload,
            )

        update_payload.update({
            "taxable_amount": taxable_total,
            "sgst_total": sgst_total,
            "cgst_total": cgst_total,
            "igst_total": igst_total,
            "round_off": round_off,
            "grand_total": grand_total,
        })

    elif "is_gst" in fields:
        existing_items = list(quotation.items)

        (
            taxable_total,
            sgst_total,
            cgst_total,
            igst_total,
            round_off,
            grand_total,
            lines,
        ) = _calculate_quotation_totals(
            existing_items,
            effective_is_gst,
        )

        for item, line in zip(
            existing_items,
            lines,
        ):
            quotation_repo.update_quotation_item(
                db,
                item,
                {
                    "amount": line["amount"],
                },
            )

        update_payload.update({
            "taxable_amount": taxable_total,
            "sgst_total": sgst_total,
            "cgst_total": cgst_total,
            "igst_total": igst_total,
            "round_off": round_off,
            "grand_total": grand_total,
        })

    updated_quotation = quotation_repo.update_quotation(
        db,
        quotation,
        update_payload,
    )

    db.commit()
    db.refresh(updated_quotation)

    return _attach_history_fields(updated_quotation)


def delete_quotation_by_id(
    db: Session,
    quotation_id: int,
):
    quotation = (
        quotation_validation
        .validate_and_get_quotation(
            db,
            quotation_id,
            include_inactive=True,
        )
    )

    quotation_repo.delete_quotation(
        db,
        quotation,
    )

    db.commit()

    return {
        "message": "Quotation deleted successfully",
    }
