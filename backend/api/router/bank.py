from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from api.dependencies.dependencies import get_db
from api.schema.bank import BankCreate, BankUpdate, BankResponse
from api.services import bank as bank_service

router = APIRouter(prefix="/banks", tags=["Banks"])

@router.post("/", response_model=BankResponse, status_code=status.HTTP_201_CREATED)
def create_bank(bank_in: BankCreate, db: Session = Depends(get_db)):
    return bank_service.create_bank(db, bank_in)

@router.get("/{bank_id}", response_model=BankResponse)
def get_bank(bank_id: int, db: Session = Depends(get_db)):
    return bank_service.get_bank(db, bank_id)

@router.get("/", response_model=List[BankResponse])
def get_all_banks(db: Session = Depends(get_db)):
    return bank_service.get_all_banks(db)

# PATCH: update_bank() uses exclude_unset=True -- genuine partial update.
@router.patch("/{bank_id}", response_model=BankResponse)
def update_bank(bank_id: int, bank_in: BankUpdate, db: Session = Depends(get_db)):
    return bank_service.update_bank(db, bank_id, bank_in)

@router.delete("/{bank_id}")
def delete_bank(bank_id: int, db: Session = Depends(get_db)):
    return bank_service.delete_bank(db, bank_id)
