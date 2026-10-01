from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.pagination import HistoryPage
from api.schema.quotation import (
    QuotationCreate,
    QuotationListResponse,
    QuotationResponse,
    QuotationUpdate,
)
from api.services.quotation import (
    create_quotation,
    delete_quotation_by_id,
    get_all_quotations,
    get_quotation_by_id,
    update_quotation_by_id,
)


router = APIRouter(
    prefix="/quotations",
    tags=["Quotations"],
)


@router.get(
    "/",
    response_model=list[QuotationListResponse] | HistoryPage[QuotationListResponse],
)
def list_quotations(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    page: int | None = Query(None, ge=1, description="Opt into history metadata; overrides skip/limit."),
    page_size: int = Query(20, ge=1, le=200),
):
    if page is not None:
        total = get_all_quotations(db, search=search, count_only=True)
        items = get_all_quotations(db, search=search, skip=(page - 1) * page_size, limit=page_size)
        return HistoryPage(items=items, total=total, page=page, page_size=page_size)
    return get_all_quotations(
        db=db,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{quotation_id}",
    response_model=QuotationResponse,
)
def get_single_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
):
    return get_quotation_by_id(
        db=db,
        quotation_id=quotation_id,
    )


@router.post(
    "/",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_quotation(
    quotation: QuotationCreate,
    db: Session = Depends(get_db),
):
    return create_quotation(
        db=db,
        quotation_data=quotation,
    )


@router.put(
    "/{quotation_id}",
    response_model=QuotationResponse,
)
def update_quotation(
    quotation_id: int,
    quotation: QuotationUpdate,
    db: Session = Depends(get_db),
):
    return update_quotation_by_id(
        db=db,
        quotation_id=quotation_id,
        quotation_data=quotation,
    )


@router.delete(
    "/{quotation_id}",
    status_code=status.HTTP_200_OK,
)
def delete_quotation(
    quotation_id: int,
    db: Session = Depends(get_db),
):
    return delete_quotation_by_id(
        db=db,
        quotation_id=quotation_id,
    )
