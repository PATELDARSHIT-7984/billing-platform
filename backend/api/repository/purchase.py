from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from api.model.party import Party
from api.model.purchase import Purchase, PurchaseItem

from api.repository import item_master as item_master_repository
from api.repository import party as party_repository


def get_active_party_by_id(db: Session, party_id: int) -> Party | None:
    return party_repository.get_party_by_id(db, party_id)


def get_active_item_by_id(db: Session, item_id: int):
    return item_master_repository.get_item_by_id(db, item_id)


def get_purchase_by_id(
    db: Session,
    purchase_id: int,
    include_inactive: bool = False,
) -> Purchase | None:
    query = db.query(Purchase).filter(Purchase.id == purchase_id)

    if not include_inactive:
        query = query.filter(Purchase.is_active == True)

    return query.first()


def get_purchase_by_bill_no(
    db: Session,
    bill_no: str,
    exclude_id: int | None = None,
) -> Purchase | None:
    query = db.query(Purchase).filter(func.upper(Purchase.bill_no) == bill_no)

    if exclude_id is not None:
        query = query.filter(Purchase.id != exclude_id)

    return query.first()


def list_purchases(
    db: Session,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Purchase] | int:
    query = (
        db.query(Purchase)
        .join(Party, Purchase.party_id == Party.id)
        .filter(Purchase.is_active == True)
    )

    if search:
        value = search.strip()
        query = query.filter(
            or_(
                Purchase.bill_no.ilike(f"%{value}%"),
                Purchase.order_no.ilike(f"%{value}%"),
                Party.name.ilike(f"%{value}%"),
            )
        )

    if count_only:
        return query.count()

    return query.order_by(Purchase.id.desc()).offset(skip).limit(limit).all()


def create_purchase(db: Session, data: dict) -> Purchase:
    purchase = Purchase(**data)
    db.add(purchase)
    db.flush()
    return purchase


def update_purchase(db: Session, purchase: Purchase, data: dict) -> Purchase:
    for field_name, field_value in data.items():
        setattr(purchase, field_name, field_value)
    db.flush()
    return purchase


def create_purchase_item(db: Session, data: dict) -> PurchaseItem:
    purchase_item = PurchaseItem(**data)
    db.add(purchase_item)
    db.flush()
    return purchase_item


def delete_purchase_item(db: Session, purchase_item: PurchaseItem) -> None:
    db.delete(purchase_item)
    db.flush()
