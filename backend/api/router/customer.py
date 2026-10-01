from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from api.dependencies.dependencies import get_db
from api.schema.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from api.services import customer as customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer_in: CustomerCreate, db: Session = Depends(get_db)):
    return customer_service.create_customer(db, customer_in)

@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    return customer_service.get_customer_by_id(db, customer_id)

@router.get("/", response_model=List[CustomerResponse])
def get_all_customers(
    db: Session = Depends(get_db),
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    return customer_service.get_all_customers(db, search=search, skip=skip, limit=limit)

# PUT, not PATCH: update_customer() in the service overwrites every field,
# so this is a full-replace semantic, not a partial patch.
@router.put("/{customer_id}", response_model=CustomerResponse)
def update_customer(customer_id: int, customer_in: CustomerUpdate, db: Session = Depends(get_db)):
    return customer_service.update_customer(db, customer_id, customer_in)

@router.delete("/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    return customer_service.delete_customer(db, customer_id)
