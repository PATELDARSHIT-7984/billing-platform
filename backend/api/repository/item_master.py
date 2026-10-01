from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.model.item_master import ItemMaster


def get_item_by_id(
    db: Session,
    item_id: int,
    include_inactive: bool = False,
) -> ItemMaster | None:
    query = db.query(ItemMaster).filter(ItemMaster.id == item_id)

    if not include_inactive:
        query = query.filter(ItemMaster.is_active == True)

    return query.first()


def get_item_by_name(
    db: Session,
    name: str,
    exclude_id: int | None = None,
) -> ItemMaster | None:
    query = db.query(ItemMaster).filter(ItemMaster.name.ilike(name))

    if exclude_id is not None:
        query = query.filter(ItemMaster.id != exclude_id)

    return query.first()


def get_item_by_code(
    db: Session,
    code: str,
    exclude_id: int | None = None,
) -> ItemMaster | None:
    query = db.query(ItemMaster).filter(ItemMaster.code == code)

    if exclude_id is not None:
        query = query.filter(ItemMaster.id != exclude_id)

    return query.first()


def list_items(
    db: Session,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
) -> list[ItemMaster]:
    query = db.query(ItemMaster)

    if not include_inactive:
        query = query.filter(ItemMaster.is_active == True)

    if search:
        search_value = search.strip()
        query = query.filter(
            or_(
                ItemMaster.name.ilike(f"%{search_value}%"),
                ItemMaster.code.ilike(f"%{search_value}%"),
                ItemMaster.hsn_code.ilike(f"%{search_value}%"),
                ItemMaster.category.ilike(f"%{search_value}%"),
                ItemMaster.brand.ilike(f"%{search_value}%"),
            )
        )

    return query.order_by(ItemMaster.name.asc()).offset(skip).limit(limit).all()


def create_item(db: Session, data: dict) -> ItemMaster:
    item = ItemMaster(**data)
    db.add(item)
    db.flush()
    return item


def update_item(db: Session, item: ItemMaster, data: dict) -> ItemMaster:
    for field_name, field_value in data.items():
        setattr(item, field_name, field_value)
    db.flush()
    return item


def deactivate_item(db: Session, item: ItemMaster) -> ItemMaster:
    item.is_active = False
    db.flush()
    return item


def activate_item(db: Session, item: ItemMaster) -> ItemMaster:
    item.is_active = True
    db.flush()
    return item


def delete_item(db: Session, item: ItemMaster) -> None:
    """
    Hard delete. Raises sqlalchemy.exc.IntegrityError to the caller
    if the item is referenced by any transaction row -- the service
    layer decides how to translate that into a user-facing message.
    """
    db.delete(item)
    db.flush()


def adjust_item_stock(db: Session, item: ItemMaster, delta: float) -> ItemMaster:
    """
    Adds delta to current_stock (pass a negative delta to subtract).
    Does not clamp at zero -- callers that need a floor (e.g. "never
    go below 0 when reversing a return") apply that in the service
    layer before calling this.
    """
    item.current_stock = (item.current_stock or 0.0) + delta
    db.flush()
    return item
