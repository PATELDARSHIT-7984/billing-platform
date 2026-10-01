from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.pagination import HistoryPage
from api.schema.sales_return import (
    SalesReturnCreate,
    SalesReturnListResponse,
    SalesReturnResponse,
    SalesReturnUpdate,
)
from api.services.sales_return import (
    create_sales_return,
    delete_sales_return_by_id,
    get_all_sales_returns,
    get_next_sales_return_numbers,
    get_sales_return_by_id,
    update_sales_return_by_id,
)

router = APIRouter(
    prefix="/sales-returns",
    tags=["Sales Returns"],
)


@router.get("/next-numbers")
def next_sales_return_numbers(
    db: Session = Depends(get_db),
):
    return get_next_sales_return_numbers(db)


@router.get(
    "/",
    response_model=list[SalesReturnListResponse] | HistoryPage[SalesReturnListResponse],
)
def list_sales_returns(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    page: int | None = Query(None, ge=1, description="Opt into history metadata; overrides skip/limit."),
    page_size: int = Query(20, ge=1, le=200),
):
    if page is not None:
        total = get_all_sales_returns(db, search=search, count_only=True)
        items = get_all_sales_returns(db, search=search, skip=(page - 1) * page_size, limit=page_size)
        return HistoryPage(items=items, total=total, page=page, page_size=page_size)
    return get_all_sales_returns(
        db=db,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{sales_return_id}",
    response_model=SalesReturnResponse,
)
def get_single_sales_return(
    sales_return_id: int,
    db: Session = Depends(get_db),
):
    return get_sales_return_by_id(
        db=db,
        sales_return_id=sales_return_id,
    )


@router.post(
    "/",
    response_model=SalesReturnResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_sales_return(
    sales_return: SalesReturnCreate,
    db: Session = Depends(get_db),
):
    return create_sales_return(
        db=db,
        sales_return_data=sales_return,
    )


@router.put(
    "/{sales_return_id}",
    response_model=SalesReturnResponse,
)
def update_sales_return(
    sales_return_id: int,
    sales_return: SalesReturnUpdate,
    db: Session = Depends(get_db),
):
    return update_sales_return_by_id(
        db=db,
        sales_return_id=sales_return_id,
        sales_return_data=sales_return,
    )

@router.delete(
    "/{sales_return_id}",
    status_code=status.HTTP_200_OK,
)
def delete_sales_return(
    sales_return_id: int,
    db: Session = Depends(get_db),
):
    return delete_sales_return_by_id(
        db=db,
        sales_return_id=sales_return_id,
    )