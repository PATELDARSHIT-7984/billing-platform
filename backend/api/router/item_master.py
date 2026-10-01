from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from api.dependencies.dependencies import get_db
from api.schema.item_master import ItemMasterCreate, ItemMasterUpdate, ItemMasterResponse
from api.services import item_master as item_master_service

# Prefix matches the frontend's itemService.js convention (used across
# Item Master, Purchase Entry, Sales Entry, Quotation, and both Return
# entry pages) -- fixing it here avoids touching eight consuming files.
router = APIRouter(prefix="/item-master", tags=["Item Master"])

@router.post("/", response_model=ItemMasterResponse, status_code=status.HTTP_201_CREATED)
def create_item(item_in: ItemMasterCreate, db: Session = Depends(get_db)):
    return item_master_service.create_item(db, item_in)

@router.get("/{item_id}", response_model=ItemMasterResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return item_master_service.get_item_by_id(db, item_id)

@router.get("/", response_model=List[ItemMasterResponse])
def get_all_items(
    db: Session = Depends(get_db),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return item_master_service.get_all_items(db, search=search, skip=skip, limit=limit)

# PATCH: update_item_by_id() uses exclude_unset=True -- genuine partial update.
@router.patch("/{item_id}", response_model=ItemMasterResponse)
def update_item(item_id: int, item_in: ItemMasterUpdate, db: Session = Depends(get_db)):
    return item_master_service.update_item_by_id(db, item_id, item_in)

@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    # Was calling the module itself, `item_master_service(db, item_id)`,
    # instead of a function on it -- always raised TypeError. Wired to the
    # actual soft-delete function; hard_delete_item_by_id exists separately
    # for a future "permanently delete" action if the UI ever adds one.
    return item_master_service.soft_delete_item_by_id(db, item_id)
