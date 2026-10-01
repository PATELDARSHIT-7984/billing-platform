from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from api.dependencies.dependencies import get_db
from api.schema.done_by import DoneByCreate, DoneByUpdate, DoneByResponse
from api.services import done_by as done_by_service

router = APIRouter(prefix="/done-by", tags=["Done By"])

@router.post("/", response_model=DoneByResponse, status_code=status.HTTP_201_CREATED)
def create_done_by(done_by_in: DoneByCreate, db: Session = Depends(get_db)):
    return done_by_service.create_done_by(db, done_by_in)

@router.get("/{done_by_id}", response_model=DoneByResponse)
def get_done_by(done_by_id: int, db: Session = Depends(get_db)):
    return done_by_service.get_done_by(db, done_by_id)

@router.get("/", response_model=List[DoneByResponse])
def get_all_done_by(db: Session = Depends(get_db)):
    return done_by_service.get_all_done_by(db)

# PATCH: update_done_by() uses exclude_unset=True -- genuine partial update.
@router.patch("/{done_by_id}", response_model=DoneByResponse)
def update_done_by(done_by_id: int, done_by_in: DoneByUpdate, db: Session = Depends(get_db)):
    return done_by_service.update_done_by(db, done_by_id, done_by_in)

@router.delete("/{done_by_id}")
def delete_done_by(done_by_id: int, db: Session = Depends(get_db)):
    return done_by_service.delete_done_by(db, done_by_id)
