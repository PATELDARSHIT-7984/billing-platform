from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.model.customer import Customer
from api.model.quotation import Quotation, QuotationItem

from api.repository import customer as customer_repository
from api.repository import item_master as item_master_repository


def get_active_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return customer_repository.get_active_customer_by_id(db, customer_id)


def get_active_item_by_id(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(
        db,
        item_id,
        include_inactive=False,
    )


def get_quotation_by_id(
    db: Session,
    quotation_id: int,
    include_inactive: bool = False,
) -> Quotation | None:
    query = db.query(Quotation).filter(Quotation.id == quotation_id)

    if not include_inactive:
        query = query.filter(Quotation.is_active == True)

    return query.first()


def get_quotation_by_quotation_no(
    db: Session,
    quotation_no: str,
    exclude_id: Optional[int] = None,
) -> Quotation | None:
    query = db.query(Quotation).filter(
        func.upper(Quotation.quotation_no) == quotation_no
    )

    if exclude_id is not None:
        query = query.filter(Quotation.id != exclude_id)

    return query.first()


def get_last_column_value(db: Session, column):
    return db.query(column).order_by(Quotation.id.desc()).limit(1).scalar()


def list_quotations(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Quotation] | int:
    query = (
        db.query(Quotation)
        .join(Customer, Quotation.customer_id == Customer.id)
        .filter(Quotation.is_active == True)
    )

    if search:
        search_value = search.strip()
        query = query.filter(
            or_(
                Quotation.quotation_no.ilike(f"%{search_value}%"),
                Quotation.order_no.ilike(f"%{search_value}%"),
                Customer.customer_name.ilike(f"%{search_value}%"),
            )
        )

    if count_only:
        return query.count()

    return query.order_by(Quotation.id.desc()).offset(skip).limit(limit).all()


def create_quotation(db: Session, data: dict) -> Quotation:
    quotation = Quotation(**data)
    db.add(quotation)
    db.flush()
    return quotation


def update_quotation(db: Session, quotation: Quotation, data: dict) -> Quotation:
    for field_name, field_value in data.items():
        setattr(quotation, field_name, field_value)
    db.flush()
    return quotation


def create_quotation_item(db: Session, data: dict) -> QuotationItem:
    item = QuotationItem(**data)
    db.add(item)
    db.flush()
    return item


def update_quotation_item(
    db: Session,
    item: QuotationItem,
    data: dict,
) -> QuotationItem:
    for field_name, field_value in data.items():
        setattr(item, field_name, field_value)
    db.flush()
    return item


def delete_quotation_item(db: Session, item: QuotationItem) -> None:
    db.delete(item)
    db.flush()


def delete_quotation(db: Session, quotation: Quotation) -> None:
    db.delete(quotation)
    db.flush()
