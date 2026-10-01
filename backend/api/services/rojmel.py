from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from api.model.rojmel import Rojmel
from api.services.party import apply_party_balance_delta
from api.repository import rojmel as rojmel_repo
from api.schema.rojmel import RojmelCreate, RojmelUpdate
from api.validation import rojmel as rojmel_validation


def _get_financial_year(dt: date) -> str:
    # Returns the Indian financial year (April to March) as "YY-YY".
    if dt.month >= 4:
        return f"{str(dt.year)[-2:]}-{str(dt.year + 1)[-2:]}"
    return f"{str(dt.year - 1)[-2:]}-{str(dt.year)[-2:]}"


def _generate_receipt_no(db: Session, effective_date: date) -> str:
    # Auto-generates the next receipt number for the entry's financial
    # year, formatted as AC/0001/YY-YY.
    fy = _get_financial_year(effective_date)
    pattern = f"AC/%/{fy}"
    last_receipt = rojmel_repo.get_last_receipt_matching_pattern(db, pattern)

    if last_receipt:
        try:
            new_seq = int(last_receipt.receipt_no.split('/')[1]) + 1
        except (IndexError, ValueError):
            new_seq = 1
    else:
        new_seq = 1

    return f"AC/{new_seq:04d}/{fy}"


def _calculate_net_amount(amount: Decimal, sgst: Decimal, cgst: Decimal, igst: Decimal) -> Decimal:
    # Applies SGST + CGST + IGST percentages on top of the base amount.
    total_tax_percent = sgst + cgst + igst
    tax_amount = (amount * total_tax_percent) / Decimal('100.00')
    return round(amount + tax_amount, 2)


def _validate_relations(db: Session, cash_bank_id: int, done_by_id: int, party_id: Optional[int]):
    # Confirms every foreign key on a receipt (bank, done-by, party) is valid.
    rojmel_validation.validate_and_get_active_bank(db, cash_bank_id)
    rojmel_validation.validate_and_get_active_done_by(db, done_by_id)
    if party_id is not None:
        rojmel_validation.validate_party_exists(db, party_id)


def create_rojmel(db: Session, rojmel_in: RojmelCreate) -> Rojmel:
    try:
        _validate_relations(db, cash_bank_id=rojmel_in.cash_bank_id, done_by_id=rojmel_in.done_by_id, party_id=rojmel_in.party_id)
        supplier = rojmel_validation.validate_and_get_supplier_payment_party(
            db, rojmel_in.transaction_type, rojmel_in.party_id, require_active=True,
        )
        rojmel_validation.validate_gst_type_is_exclusive(rojmel_in.sgst_percent, rojmel_in.cgst_percent, rojmel_in.igst_percent)
        rojmel_payload = rojmel_in.model_dump(exclude={"receipt_no", "net_amount"})
        rojmel_payload["receipt_no"] = _generate_receipt_no(db, rojmel_in.effective_date)
        rojmel_payload["net_amount"] = _calculate_net_amount(
            rojmel_in.amount, rojmel_in.sgst_percent, rojmel_in.cgst_percent, rojmel_in.igst_percent,
        )
        new_rojmel = rojmel_repo.create_rojmel(db, data=rojmel_payload)
        if supplier is not None:
            apply_party_balance_delta(db, supplier.id, -new_rojmel.net_amount)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(new_rojmel)
    return new_rojmel


def get_rojmel(db: Session, rojmel_id: int) -> Rojmel:
    # Fetches a single receipt by id (404s if missing).
    return rojmel_validation.validate_and_get_rojmel(db, rojmel_id)


def get_all_rojmels(
    db: Session,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    party_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Rojmel], int]:
    # Returns one page of the ledger matching the given filters, plus the
    # total row count so the caller can build pagination info.
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    return rojmel_repo.list_rojmels(
        db,
        search=search,
        start_date=start_date,
        end_date=end_date,
        party_id=party_id,
        page=page,
        page_size=page_size,
    )


def update_rojmel(db: Session, rojmel_id: int, rojmel_in: RojmelUpdate) -> Rojmel:
    try:
        rojmel = rojmel_validation.validate_and_get_rojmel(db, rojmel_id)
        old_supplier = rojmel_validation.validate_and_get_supplier_payment_party(
            db, rojmel.transaction_type, rojmel.party_id,
        )
        old_supplier_id = old_supplier.id if old_supplier is not None else None
        old_net_amount = rojmel.net_amount

        bank_id = rojmel_in.cash_bank_id if rojmel_in.cash_bank_id is not None else rojmel.cash_bank_id
        done_by_id = rojmel_in.done_by_id if rojmel_in.done_by_id is not None else rojmel.done_by_id
        party_id = rojmel_in.party_id if rojmel_in.party_id is not None else rojmel.party_id
        if rojmel_in.cash_bank_id or rojmel_in.done_by_id or rojmel_in.party_id:
            _validate_relations(db, cash_bank_id=bank_id, done_by_id=done_by_id, party_id=party_id)

        # Keep accepting the existing payload shape, but never persist client net totals.
        update_payload = rojmel_in.model_dump(exclude_unset=True, exclude={"receipt_no", "net_amount"})
        for key, value in update_payload.items():
            setattr(rojmel, key, value)

        new_supplier = rojmel_validation.validate_and_get_supplier_payment_party(
            db, rojmel.transaction_type, rojmel.party_id,
            require_active=old_supplier_id is None or rojmel.party_id != old_supplier_id,
        )
        new_supplier_id = new_supplier.id if new_supplier is not None else None
        rojmel_validation.validate_gst_type_is_exclusive(rojmel.sgst_percent, rojmel.cgst_percent, rojmel.igst_percent)
        rojmel.net_amount = _calculate_net_amount(
            rojmel.amount, rojmel.sgst_percent, rojmel.cgst_percent, rojmel.igst_percent,
        )
        updated_rojmel = rojmel_repo.update_rojmel(db, rojmel=rojmel, data={})
        if old_supplier_id == new_supplier_id:
            if new_supplier_id is not None:
                delta = old_net_amount - updated_rojmel.net_amount
                if delta:
                    apply_party_balance_delta(db, new_supplier_id, delta)
        else:
            if old_supplier_id is not None:
                apply_party_balance_delta(db, old_supplier_id, old_net_amount)
            if new_supplier_id is not None:
                apply_party_balance_delta(db, new_supplier_id, -updated_rojmel.net_amount)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(updated_rojmel)
    return updated_rojmel


def delete_rojmel(db: Session, rojmel_id: int) -> dict:
    try:
        rojmel = rojmel_validation.validate_and_get_rojmel(db, rojmel_id)
        supplier = rojmel_validation.validate_and_get_supplier_payment_party(
            db, rojmel.transaction_type, rojmel.party_id,
        )
        old_net_amount = rojmel.net_amount
        receipt_no = rojmel.receipt_no
        rojmel_repo.delete_rojmel(db, rojmel=rojmel)
        if supplier is not None:
            apply_party_balance_delta(db, supplier.id, old_net_amount)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": f"Receipt {receipt_no} has been permanently deleted."}


def get_rojmel_summary(
    db: Session,
    search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    party_id: Optional[int] = None,
) -> dict:
    # "Cr Pay" is money received, "Dr Pay" is money paid out -- net earning
    # is the difference. Cash/Bank transfers and JV adjustments are shown
    # for reference but don't count as earning either way. Totals cover
    # every matching row (not just the current page), same filters as the
    # list view, so this always matches what's on screen.
    totals_by_type = rojmel_repo.get_totals_by_type(db, search=search, start_date=start_date, end_date=end_date, party_id=party_id)

    total_received = totals_by_type.get("Cr Pay", Decimal("0.00"))
    total_paid = totals_by_type.get("Dr Pay", Decimal("0.00"))

    return {
        "total_received": total_received,
        "total_paid": total_paid,
        "total_cash_bank": totals_by_type.get("Cash/Bank", Decimal("0.00")),
        "total_jv": totals_by_type.get("JV", Decimal("0.00")),
        "net_earning": total_received - total_paid,
    }
