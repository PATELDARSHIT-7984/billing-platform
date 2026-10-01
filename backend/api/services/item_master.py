from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.model.item_master import ItemMaster
from api.repository import item_master as item_repo
from api.schema.item_master import ItemMasterCreate, ItemMasterUpdate
from api.validation import item_master as item_validation


def get_item_by_id(
    db: Session, item_id: int, include_inactive: bool = False
) -> ItemMaster:
    return item_validation.validate_and_get_item(
        db, item_id=item_id, include_inactive=include_inactive
    )


def create_item(db: Session, item_data: ItemMasterCreate) -> ItemMaster:
    # 1. Enforce unique name and code
    item_validation.validate_item_name_is_unique(db, name=item_data.name)
    if item_data.code:
        item_validation.validate_item_code_is_unique(db, code=item_data.code)

    # 2. Persist record
    new_item = item_repo.create_item(db, data=item_data.model_dump())
    db.commit()
    db.refresh(new_item)
    return new_item


def get_all_items(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
) -> list[ItemMaster]:
    return item_repo.list_items(
        db,
        search=search,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )


def update_item_by_id(
    db: Session,
    item_id: int,
    item_data: ItemMasterUpdate,
) -> ItemMaster:
    item = item_validation.validate_and_get_item(
        db,
        item_id=item_id,
        include_inactive=True,
    )

    update_dict = item_data.model_dump(
        exclude_unset=True,
    )

    update_dict.pop("current_stock", None)

    if "name" in update_dict and update_dict["name"]:
        item_validation.validate_item_name_is_unique(
            db,
            name=update_dict["name"],
            exclude_id=item_id,
        )

    if "code" in update_dict and update_dict["code"]:
        item_validation.validate_item_code_is_unique(
            db,
            code=update_dict["code"],
            exclude_id=item_id,
        )

    updated_item = item_repo.update_item(
        db,
        item=item,
        data=update_dict,
    )

    db.commit()
    db.refresh(updated_item)

    return updated_item


def soft_delete_item_by_id(db: Session, item_id: int):
    item = item_validation.validate_and_get_item(
        db, item_id=item_id, include_inactive=True
    )
    item_validation.validate_item_is_active(item)

    item_repo.deactivate_item(db, item=item)
    db.commit()

    return {"message": f"Item '{item.name}' deactivated successfully"}


def restore_item_by_id(db: Session, item_id: int) -> ItemMaster:
    item = item_validation.validate_and_get_item(
        db, item_id=item_id, include_inactive=True
    )
    item_validation.validate_item_is_inactive(item)

    item_repo.activate_item(db, item=item)
    db.commit()
    db.refresh(item)
    return item


def hard_delete_item_by_id(db: Session, item_id: int):
    item = item_validation.validate_and_get_item(
        db, item_id=item_id, include_inactive=True
    )

    try:
        item_repo.delete_item(db, item=item)
        db.commit()
        return {"message": f"Item '{item.name}' permanently deleted"}

    except IntegrityError:
        db.rollback()
        item_validation.raise_item_referenced_error()