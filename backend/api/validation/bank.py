"""
Business-rule validation layer for Bank records.

Rules for this module (mirrors repository/bank.py):
- This is the ONLY layer allowed to raise HTTPException for bank rules.
- No db.commit() / db.rollback() here -- read-only, via the repository.
- No direct ORM/Session queries here -- all lookups go through
  repository.bank so there is exactly one place that knows how a
  bank row is fetched.
- Functions that the service needs the row back from (e.g. to update
  or deactivate it) are named `validate_and_get_...` and return the
  ORM object. Pure uniqueness checks return None and only raise.
"""

from fastapi import HTTPException, status

from api.repository import bank as bank_repository


def validate_bank_name_is_unique(db, name: str) -> None:
    existing_bank = bank_repository.get_bank_by_name(db, name)
    if existing_bank:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A bank with this name already exists.",
        )


def validate_and_get_active_bank(db, bank_id: int):
    bank = bank_repository.get_active_bank_by_id(db, bank_id)
    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank not found or is inactive.",
        )
    return bank
