from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.model.customer import Customer
from api.model.bill import Bill
from api.model.sales_return import SalesReturn, SalesReturnItem

from api.repository import customer as customer_repository
from api.repository import item_master as item_master_repository


def get_active_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return customer_repository.get_active_customer_by_id(db, customer_id)


def get_active_item_by_id(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id)


def get_item_by_id_any_status(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id, include_inactive=True)


def get_active_bill_by_invoice_no(db: Session, invoice_no: str):
    return db.query(Bill).filter(
        Bill.is_active == True, func.upper(func.trim(Bill.invoice_no)) == invoice_no.upper(),
    ).first()


def get_active_return_quantities(db: Session, invoice_no: str, exclude_id: int | None = None):
    """Stream matching quantity columns for decimal aggregation in the service."""
    query = db.query(SalesReturnItem.item_id, SalesReturnItem.quantity).join(
        SalesReturn, SalesReturn.id == SalesReturnItem.sales_return_id,
    ).filter(
        SalesReturn.is_active == True,
        func.upper(func.trim(SalesReturn.original_invoice_no)) == invoice_no.upper(),
    )
    if exclude_id is not None:
        query = query.filter(SalesReturn.id != exclude_id)
    return query.yield_per(200)


def get_sales_return_by_id(
    db: Session,
    sales_return_id: int,
    include_inactive: bool = False,
) -> SalesReturn | None:
    query = db.query(SalesReturn).filter(SalesReturn.id == sales_return_id)

    if not include_inactive:
        query = query.filter(SalesReturn.is_active == True)

    return query.first()


def get_sales_return_by_return_no(
    db: Session,
    return_no: str,
    exclude_id: Optional[int] = None,
) -> SalesReturn | None:
    query = db.query(SalesReturn).filter(
        func.upper(SalesReturn.return_no) == return_no
    )

    if exclude_id is not None:
        query = query.filter(SalesReturn.id != exclude_id)

    return query.first()


def get_last_column_value(db: Session, column):
    """
    Returns the most recent value of the given SalesReturn column
    (e.g. SalesReturn.return_no or SalesReturn.order_no), ordered by
    id descending. Used by the service layer to derive the next
    sequence number.
    """
    return db.query(column).order_by(SalesReturn.id.desc()).limit(1).scalar()


def list_sales_returns(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[SalesReturn] | int:
    query = (
        db.query(SalesReturn)
        .join(Customer, SalesReturn.customer_id == Customer.id)
        .filter(SalesReturn.is_active == True)
    )

    if search:
        value = search.strip()
        query = query.filter(
            or_(
                SalesReturn.return_no.ilike(f"%{value}%"),
                SalesReturn.order_no.ilike(f"%{value}%"),
                SalesReturn.original_invoice_no.ilike(f"%{value}%"),
                Customer.customer_name.ilike(f"%{value}%"),
            )
        )

    if count_only:
        return query.count()

    return query.order_by(SalesReturn.id.desc()).offset(skip).limit(limit).all()


def create_sales_return(db: Session, data: dict) -> SalesReturn:
    record = SalesReturn(**data)
    db.add(record)
    db.flush()
    return record


def update_sales_return(db: Session, record: SalesReturn, data: dict) -> SalesReturn:
    for field_name, field_value in data.items():
        setattr(record, field_name, field_value)
    db.flush()
    return record


def create_sales_return_item(db: Session, data: dict) -> SalesReturnItem:
    item = SalesReturnItem(**data)
    db.add(item)
    db.flush()
    return item


def deactivate_sales_return(
    db: Session,
    record: SalesReturn,
) -> SalesReturn:
    record.is_active = False
    db.flush()
    return record


def delete_sales_return_item(db: Session, item: SalesReturnItem) -> None:
    db.delete(item)
    db.flush()
