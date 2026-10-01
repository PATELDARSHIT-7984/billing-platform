from fastapi import HTTPException, status

from api.repository import party as party_repository


def validate_and_get_active_party(db, party_id: int):
    party = party_repository.get_party_by_id(db, party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")
    return party


def validate_gstin_is_unique(db, gstin: str, exclude_id: int | None = None) -> None:
    if not gstin:
        return

    existing_gstin = party_repository.get_party_by_gstin(db, gstin, exclude_id=exclude_id)
    if existing_gstin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GSTIN already exists")
