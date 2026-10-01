from fastapi import HTTPException, status

from api.repository import item_master as item_master_repository


def validate_item_name_is_unique(db, name: str, exclude_id: int | None = None) -> None:
    existing_name = item_master_repository.get_item_by_name(db, name, exclude_id=exclude_id)
    if existing_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item name already exists")


def validate_item_code_is_unique(db, code: str, exclude_id: int | None = None) -> None:
    if not code:
        return

    existing_code = item_master_repository.get_item_by_code(db, code, exclude_id=exclude_id)
    if existing_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item code already exists")


def validate_and_get_item(db, item_id: int, include_inactive: bool = False):
    item = item_master_repository.get_item_by_id(db, item_id, include_inactive=include_inactive)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


def validate_item_is_active(item) -> None:
    """Used before soft-deleting -- an item that's already inactive can't be deactivated again."""
    if not item.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item is already inactive")


def validate_item_is_inactive(item) -> None:
    """Used before restoring -- an item that's already active can't be restored again."""
    if item.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item is already active")


def raise_item_referenced_error() -> None:
    """
    Call this from the service's `except IntegrityError:` block around
    the hard-delete call, instead of letting IntegrityError bubble up.
    Mirrors the try/except in the commented-out version of
    hard_delete_item_by_id -- kept here (rather than done as a
    pre-check query) because the database is the only reliable source
    of truth for "is this item referenced anywhere".
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "This item is used in existing transactions (Bills/Purchases/etc) "
            "and cannot be permanently deleted. Please deactivate it instead."
        ),
    )
