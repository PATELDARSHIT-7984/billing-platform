from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.party import PartyCreate, PartyResponse, PartyUpdate
from api.services.party import (
    create_party,
    delete_party_by_id,
    get_parties,
    get_party_by_id,
    update_party_by_id,
)

router = APIRouter(prefix="/parties", tags=["Parties"])


@router.post("/", response_model=PartyResponse, status_code=201)
def add_party(party: PartyCreate, db: Session = Depends(get_db)):
    return create_party(db, party)


@router.get("/", response_model=list[PartyResponse])
def list_parties(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = Query(None, description="Search by Name, Mobile, City, State, GSTIN or PAN"),
):
    return get_parties(db, skip, limit, search)


@router.get("/{party_id}", response_model=PartyResponse)
def get_single_party(party_id: int, db: Session = Depends(get_db)):
    return get_party_by_id(db, party_id)


@router.put("/{party_id}", response_model=PartyResponse)
def update_party(party_id: int, party_data: PartyUpdate, db: Session = Depends(get_db)):
    return update_party_by_id(db, party_id, party_data)


@router.delete("/{party_id}")
def delete_party(party_id: int, db: Session = Depends(get_db)):
    return delete_party_by_id(db, party_id)
