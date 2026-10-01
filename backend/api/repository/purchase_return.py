"""
Data-access layer for PurchaseReturn / PurchaseReturnItem records.

Same rules as the other repository modules: no HTTPException,
no commit/rollback. Return/order-number formatting, stock-sufficiency
checks, and tax/total math stay in the service layer -- this module
only exposes the raw last-value lookups those calculations need.

Party and ItemMaster existence checks are delegated to the
repository.party and repository.item_master modules.
"""

from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.model.party import Party
from api.model.purchase_return import PurchaseReturn, PurchaseReturnItem

from api.repository import item_master as item_master_repository
from api.repository import party as party_repository


def get_active_party_by_id(db: Session, party_id: int) -> Party | None:
    return party_repository.get_party_by_id(db, party_id)


def get_active_item_by_id(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id)


def get_item_by_id_any_status(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id, include_inactive=True)


def get_active_return_quantities(db: Session, original_bill_no: str, exclude_id: int | None = None):
    """Only quantity columns; the service aggregates them without float SUM drift."""
    query = db.query(PurchaseReturnItem.item_id, PurchaseReturnItem.quantity).join(
        PurchaseReturn, PurchaseReturn.id == PurchaseReturnItem.purchase_return_id,
    ).filter(
        PurchaseReturn.is_active == True,
        func.upper(func.trim(PurchaseReturn.original_bill_no)) == original_bill_no.upper(),
    )
    if exclude_id is not None:
        query = query.filter(PurchaseReturn.id != exclude_id)
    return query.yield_per(200)


def get_purchase_return_by_id(
    db: Session,
    record_id: int,
    include_inactive: bool = False,
) -> PurchaseReturn | None:
    query = db.query(PurchaseReturn).filter(PurchaseReturn.id == record_id)

    if not include_inactive:
        query = query.filter(PurchaseReturn.is_active == True)

    return query.first()


def get_purchase_return_by_return_no(
    db: Session,
    return_no: str,
    exclude_id: Optional[int] = None,
) -> PurchaseReturn | None:
    query = db.query(PurchaseReturn).filter(
        func.upper(PurchaseReturn.return_no) == return_no
    )

    if exclude_id is not None:
        query = query.filter(PurchaseReturn.id != exclude_id)

    return query.first()


def get_last_column_value(db: Session, column):
    """
    Returns the most recent value of the given PurchaseReturn column
    (e.g. PurchaseReturn.return_no or PurchaseReturn.order_no),
    ordered by id descending. Used by the service layer to derive the
    next sequence number.
    """
    return db.query(column).order_by(PurchaseReturn.id.desc()).limit(1).scalar()


def list_purchase_returns(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[PurchaseReturn] | int:
    query = (
        db.query(PurchaseReturn)
        .join(Party, PurchaseReturn.party_id == Party.id)
        .filter(PurchaseReturn.is_active == True)
    )

    if search:
        value = search.strip()
        query = query.filter(
            or_(
                PurchaseReturn.return_no.ilike(f"%{value}%"),
                PurchaseReturn.original_bill_no.ilike(f"%{value}%"),
                Party.name.ilike(f"%{value}%"),
            )
        )

    if count_only:
        return query.count()

    return query.order_by(PurchaseReturn.id.desc()).offset(skip).limit(limit).all()

def deactivate_purchase_return(
    db: Session,
    record: PurchaseReturn,
) -> PurchaseReturn:
    record.is_active = False
    db.flush()
    return record

def create_purchase_return(db: Session, data: dict) -> PurchaseReturn:
    record = PurchaseReturn(**data)
    db.add(record)
    db.flush()
    return record


def update_purchase_return(
    db: Session,
    record: PurchaseReturn,
    data: dict,
) -> PurchaseReturn:
    for field_name, field_value in data.items():
        setattr(record, field_name, field_value)
    db.flush()
    return record


def create_purchase_return_item(db: Session, data: dict) -> PurchaseReturnItem:
    item = PurchaseReturnItem(**data)
    db.add(item)
    db.flush()
    return item


def delete_purchase_return_item(db: Session, item: PurchaseReturnItem) -> None:
    db.delete(item)
    db.flush()
