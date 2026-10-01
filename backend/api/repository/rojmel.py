from datetime import date
from decimal import Decimal
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from api.model.rojmel import Rojmel
from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.party import Party


def get_active_bank_by_id(db: Session, bank_id: int) -> BankModel | None:
    # Looks up a Cash/Bank account, only returning it if still active.
    return db.query(BankModel).filter(BankModel.id == bank_id, BankModel.is_active == True).first()


def get_active_done_by_by_id(db: Session, done_by_id: int) -> DoneByModel | None:
    # Looks up the "Done By" person, only returning them if still active.
    return db.query(DoneByModel).filter(DoneByModel.id == done_by_id, DoneByModel.is_active == True).first()


def get_party_by_id_any_status(db: Session, party_id: int) -> Party | None:
    # Looks up a party regardless of active status (a receipt against a
    # since-deactivated party should still be viewable/editable).
    return db.query(Party).filter(Party.id == party_id).first()


def get_last_receipt_matching_pattern(db: Session, pattern: str) -> Rojmel | None:
    # pattern is a SQL LIKE pattern, e.g. "AC/%/26-27". Used to work out
    # the next sequence number for a financial year.
    return db.query(Rojmel).filter(Rojmel.receipt_no.like(pattern)).order_by(Rojmel.id.desc()).first()


def get_rojmel_by_id(db: Session, rojmel_id: int) -> Rojmel | None:
    # Fetches a single receipt by id, or None if it doesn't exist.
    return db.query(Rojmel).filter(Rojmel.id == rojmel_id).first()


def _apply_rojmel_filters(query, search, start_date, end_date, party_id):
    # Shared by list_rojmels and get_totals_by_type so both always agree
    # on which rows count -- the totals must match what's on screen.
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Rojmel.receipt_no.ilike(like_pattern),
                Rojmel.payment_for.ilike(like_pattern),
                Rojmel.remarks.ilike(like_pattern),
                Rojmel.pay_mode.ilike(like_pattern),
                Rojmel.cheque_txn_no.ilike(like_pattern),
            )
        )

    if start_date:
        query = query.filter(Rojmel.effective_date >= start_date)

    if end_date:
        query = query.filter(Rojmel.effective_date <= end_date)

    if party_id:
        query = query.filter(Rojmel.party_id == party_id)

    return query


def list_rojmels(
    db: Session,
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    party_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Rojmel], int]:
    # Builds the filtered/searched query once, gets the total count for
    # pagination, then applies limit/offset for the requested page.
    # Returns (rows_for_this_page, total_matching_rows).
    query = _apply_rojmel_filters(db.query(Rojmel), search, start_date, end_date, party_id)

    total = query.count()

    rows = (
        query.order_by(Rojmel.effective_date.desc(), Rojmel.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return rows, total


def get_totals_by_type(
    db: Session,
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    party_id: int | None = None,
) -> dict[str, Decimal]:
    # Sums net_amount grouped by transaction_type across every matching
    # row (not just the current page) -- this is what "how much have I
    # earned so far" needs, since pagination alone can't answer that.
    query = _apply_rojmel_filters(db.query(Rojmel), search, start_date, end_date, party_id)

    rows = query.with_entities(Rojmel.transaction_type, func.sum(Rojmel.net_amount)).group_by(Rojmel.transaction_type).all()

    return {str(transaction_type.value): total or Decimal("0.00") for transaction_type, total in rows}


def create_rojmel(db: Session, data: dict) -> Rojmel:
    # Inserts a new receipt row and flushes so the caller gets back an id.
    rojmel = Rojmel(**data)
    db.add(rojmel)
    db.flush()
    return rojmel


def update_rojmel(db: Session, rojmel: Rojmel, data: dict) -> Rojmel:
    # Applies changed fields onto an already-fetched row.
    for field_name, field_value in data.items():
        setattr(rojmel, field_name, field_value)
    db.flush()
    return rojmel


def delete_rojmel(db: Session, rojmel: Rojmel) -> None:
    # Hard delete -- permanently removes the row from the table.
    db.delete(rojmel)
    db.flush()
