from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.pagination import HistoryPage
from api.schema.bill import BillCreate, BillDetailResponse, BillUpdate, BillResponse
from api.services import bill as bill_service

router = APIRouter(prefix="/bills", tags=["Bills"])

@router.post("/", response_model=BillResponse, status_code=status.HTTP_201_CREATED)
def create_bill(bill_in: BillCreate, db: Session = Depends(get_db)):
    return bill_service.create_bill(db, bill_in)

@router.get("/{bill_id}", response_model=BillDetailResponse)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return bill_service.get_bill_by_id(db, bill_id)

@router.get("/", response_model=list[BillResponse] | HistoryPage[BillResponse])
def get_all_bills(
    db: Session = Depends(get_db),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    page: int | None = Query(None, ge=1, description="Opt into history metadata; overrides skip/limit."),
    page_size: int = Query(20, ge=1, le=200),
):
    if page is not None:
        total = bill_service.get_all_bills(db, search=search, count_only=True)
        items = bill_service.get_all_bills(db, search=search, skip=(page - 1) * page_size, limit=page_size)
        return HistoryPage(items=items, total=total, page=page, page_size=page_size)
    return bill_service.get_all_bills(db, search=search, skip=skip, limit=limit)

@router.put("/{bill_id}", response_model=BillDetailResponse)
def update_bill(bill_id: int, bill_in: BillUpdate, db: Session = Depends(get_db)):
    return bill_service.update_bill(db, bill_id, bill_in)

@router.delete("/{bill_id}")
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    return bill_service.delete_bill(db, bill_id)
