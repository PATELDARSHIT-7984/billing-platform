from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from api.dependencies.dependencies import get_db
from api.schema.rojmel import RojmelCreate, RojmelUpdate, RojmelResponse, RojmelSummary
from api.services import rojmel as rojmel_service
from api.utils.response import success

router = APIRouter(prefix="/rojmel", tags=["Rojmel"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_rojmel(rojmel_in: RojmelCreate, db: Session = Depends(get_db)):
    # Creates a new ledger receipt; receipt_no and net_amount are computed server-side.
    new_rojmel = rojmel_service.create_rojmel(db, rojmel_in)
    return success(data=RojmelResponse.model_validate(new_rojmel), message="Rojmel receipt created successfully", status_code=status.HTTP_201_CREATED)


@router.get("/summary")
def get_rojmel_summary(
    search: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    party_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    # Total received vs. paid across every matching receipt (not just the
    # current page) -- gives the owner an at-a-glance earnings figure.
    # Declared before /{rojmel_id} so "summary" isn't swallowed as an id.
    summary = rojmel_service.get_rojmel_summary(db=db, search=search, start_date=start_date, end_date=end_date, party_id=party_id)
    return success(data=RojmelSummary(**summary), message="Rojmel summary retrieved successfully")


@router.get("/{rojmel_id}")
def get_rojmel(rojmel_id: int, db: Session = Depends(get_db)):
    # Returns a single receipt by id.
    rojmel = rojmel_service.get_rojmel(db, rojmel_id)
    return success(data=RojmelResponse.model_validate(rojmel), message="Rojmel receipt retrieved successfully")


@router.get("/")
def get_all_rojmels(
    search: Optional[str] = Query(None, description="Matches receipt no, payment for, remarks, pay mode, or cheque/txn no."),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    party_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    # Returns one page of the ledger, filtered/searched as requested.
    rows, total = rojmel_service.get_all_rojmels(
        db=db,
        search=search,
        start_date=start_date,
        end_date=end_date,
        party_id=party_id,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    page_data = {
        "items": [RojmelResponse.model_validate(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
    return success(data=page_data, message="Rojmel ledger retrieved successfully")


@router.patch("/{rojmel_id}")
def update_rojmel(rojmel_id: int, rojmel_in: RojmelUpdate, db: Session = Depends(get_db)):
    # Partially updates a receipt (only fields present in the payload are changed).
    updated_rojmel = rojmel_service.update_rojmel(db, rojmel_id, rojmel_in)
    return success(data=RojmelResponse.model_validate(updated_rojmel), message="Rojmel receipt updated successfully")


@router.delete("/{rojmel_id}")
def delete_rojmel(rojmel_id: int, db: Session = Depends(get_db)):
    # Hard-deletes a receipt permanently -- there is no undo.
    result = rojmel_service.delete_rojmel(db, rojmel_id)
    return success(data=None, message=result["message"])
