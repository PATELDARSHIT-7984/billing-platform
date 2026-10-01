"""
Data-access layer for Bill / BillItem records.

Same rules as the other repository modules: no HTTPException,
no commit/rollback. Invoice-number generation strategy, GST math,
amount-in-words conversion, and stock-sufficiency checks stay in the
service layer -- this module only exposes the raw rows those
calculations need.

Customer and ItemMaster existence checks are delegated to the
repository.customer and repository.item_master modules.

Note the primary key on Bill is `bill_id`, not `id` -- this mirrors
the original model exactly.
"""

from typing import Optional

from sqlalchemy.orm import Session

from api.model.bill import Bill
from api.model.bill_item import BillItem
from api.model.customer import Customer

from api.repository import customer as customer_repository
from api.repository import item_master as item_master_repository


def get_active_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return customer_repository.get_active_customer_by_id(db, customer_id)


def get_active_item_by_id(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id)


def get_item_by_id_any_status(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id, include_inactive=True)


def get_all_invoice_numbers(db: Session) -> list[str]:
    """
    Returns every non-null invoice_no currently stored. Used by the
    service layer's invoice-number generator to find the highest
    existing numeric invoice number.
    """
    rows = db.query(Bill.invoice_no).filter(Bill.invoice_no.isnot(None)).all()
    return [str(row[0]).strip() for row in rows]


def invoice_no_exists(db: Session, invoice_no: str) -> bool:
    return db.query(Bill).filter(Bill.invoice_no == invoice_no).first() is not None


def get_active_invoice_references_for_item(db: Session, item_id: int) -> tuple[list[str], int]:
    """Bounded context only: no allocation between Purchase and Sales stock."""
    query = db.query(Bill).filter(
        Bill.is_active == True,
        Bill.bill_items.any((BillItem.item_id == item_id) & (BillItem.is_active == True)),
    )
    total = query.count()
    rows = query.with_entities(Bill.invoice_no).order_by(Bill.bill_date.desc(), Bill.bill_id.desc()).limit(5).all()
    return [row.invoice_no for row in rows], max(0, total - len(rows))


def get_bill_by_id(
    db: Session,
    bill_id: int,
    include_inactive: bool = False,
) -> Bill | None:
    query = db.query(Bill).filter(Bill.bill_id == bill_id)

    if not include_inactive:
        query = query.filter(Bill.is_active == True)

    return query.first()


def list_bills(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Bill] | int:
    query = db.query(Bill).filter(Bill.is_active == True)

    if search:
        query = query.filter(
            Bill.invoice_no.ilike(f"%{search}%")
            | Bill.customer_name.ilike(f"%{search}%")
        )

    if count_only:
        return query.count()

    return query.order_by(Bill.bill_id.desc()).offset(skip).limit(limit).all()


def create_bill(db: Session, data: dict) -> Bill:
    bill = Bill(**data)
    db.add(bill)
    db.flush()
    return bill


def update_bill(db: Session, bill: Bill, data: dict) -> Bill:
    for field_name, field_value in data.items():
        setattr(bill, field_name, field_value)
    db.flush()
    return bill


def deactivate_bill(db: Session, bill: Bill) -> Bill:
    bill.is_active = False
    db.flush()
    return bill


def create_bill_item(db: Session, data: dict) -> BillItem:
    bill_item = BillItem(**data)
    db.add(bill_item)
    db.flush()
    return bill_item


def delete_bill_item(db: Session, bill_item: BillItem) -> None:
    db.delete(bill_item)
    db.flush()
