from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.pagination import HistoryPage
from api.schema.purchase_return import (
    PurchaseReturnCreate,
    PurchaseReturnListResponse,
    PurchaseReturnResponse,
    PurchaseReturnUpdate,
)
from api.services.purchase_return import (
    create_purchase_return,
    delete_purchase_return_by_id,
    get_all_purchase_returns,
    get_next_purchase_return_numbers,
    get_purchase_return_by_id,
    update_purchase_return_by_id,
)


router = APIRouter(
    prefix="/purchase-returns",
    tags=["Purchase Returns"],
)


@router.get("/next-numbers")
def next_purchase_return_numbers(
    db: Session = Depends(get_db),
):
    return get_next_purchase_return_numbers(db)


@router.get(
    "/",
    response_model=list[PurchaseReturnListResponse] | HistoryPage[PurchaseReturnListResponse],
)
def list_purchase_returns(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    page: int | None = Query(None, ge=1, description="Opt into history metadata; overrides skip/limit."),
    page_size: int = Query(20, ge=1, le=200),
):
    if page is not None:
        total = get_all_purchase_returns(db, search=search, count_only=True)
        items = get_all_purchase_returns(db, search=search, skip=(page - 1) * page_size, limit=page_size)
        return HistoryPage(items=items, total=total, page=page, page_size=page_size)
    return get_all_purchase_returns(
        db=db,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{record_id}",
    response_model=PurchaseReturnResponse,
)
def get_single_purchase_return(
    record_id: int,
    db: Session = Depends(get_db),
):
    return get_purchase_return_by_id(
        db=db,
        record_id=record_id,
    )


@router.post(
    "/",
    response_model=PurchaseReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_purchase_return(
    purchase_return: PurchaseReturnCreate,
    db: Session = Depends(get_db),
):
    return create_purchase_return(
        db=db,
        data=purchase_return,
    )


@router.put(
    "/{record_id}",
    response_model=PurchaseReturnResponse,
)
def update_purchase_return(
    record_id: int,
    purchase_return: PurchaseReturnUpdate,
    db: Session = Depends(get_db),
):
    return update_purchase_return_by_id(
        db=db,
        record_id=record_id,
        data=purchase_return,
    )

@router.delete(
    "/{record_id}",
    status_code=status.HTTP_200_OK,
)
def delete_purchase_return(
    record_id: int,
    db: Session = Depends(get_db),
):
    return delete_purchase_return_by_id(
        db=db,
        record_id=record_id,
    )