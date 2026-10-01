"""
Data-access layer for DoneBy (the "handled by" person) records.

Same rules as repository/bank.py: no HTTPException, no commit/rollback,
no business rules — pure queries and staged writes only.
"""

from sqlalchemy.orm import Session

from api.model.done_by import DoneByModel


def get_done_by_by_id(db: Session, done_by_id: int) -> DoneByModel | None:
    return db.query(DoneByModel).filter(DoneByModel.id == done_by_id).first()


def get_active_done_by_by_id(db: Session, done_by_id: int) -> DoneByModel | None:
    return (
        db.query(DoneByModel)
        .filter(
            DoneByModel.id == done_by_id,
            DoneByModel.is_active == True,
        )
        .first()
    )


def get_done_by_by_name(db: Session, name: str) -> DoneByModel | None:
    return db.query(DoneByModel).filter(DoneByModel.name == name).first()


def list_active_done_by(db: Session) -> list[DoneByModel]:
    return db.query(DoneByModel).filter(DoneByModel.is_active == True).all()


def create_done_by(db: Session, data: dict) -> DoneByModel:
    person = DoneByModel(**data)
    db.add(person)
    db.flush()
    return person


def update_done_by(db: Session, person: DoneByModel, data: dict) -> DoneByModel:
    for field_name, field_value in data.items():
        setattr(person, field_name, field_value)
    db.flush()
    return person


def deactivate_done_by(db: Session, person: DoneByModel) -> DoneByModel:
    person.is_active = False
    db.flush()
    return person
