"""
Business-rule validation layer for DoneBy records.

Same conventions as validation/bank.py: raises HTTPException, never
touches the ORM directly, delegates all lookups to repository.done_by.
"""

from fastapi import HTTPException, status

from api.repository import done_by as done_by_repository


def validate_done_by_snapshot(db, name: str | None, *, previous: str | None = None) -> None:
    """Optional snapshots may be retained historically; new selections must be active."""
    if name is None or name == previous:
        return
    person = done_by_repository.get_done_by_by_name(db, name)
    if person is None or not person.is_active:
        raise HTTPException(400, "Select an active person from Done By Management.")


def validate_done_by_name_is_unique(db, name: str) -> None:
    existing_person = done_by_repository.get_done_by_by_name(db, name)
    if existing_person:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This name already exists in the system.",
        )


def validate_and_get_active_done_by(db, done_by_id: int):
    person = done_by_repository.get_active_done_by_by_id(db, done_by_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found or is inactive.",
        )
    return person
