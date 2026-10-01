from sqlalchemy.orm import Session

from api.model.done_by import DoneByModel
from api.repository import done_by as done_by_repo
from api.schema.done_by import DoneByCreate, DoneByUpdate
from api.validation import done_by as done_by_validation


def create_done_by(db: Session, done_by_in: DoneByCreate) -> DoneByModel:
    done_by_validation.validate_done_by_name_is_unique(db, name=done_by_in.name)

    new_person = done_by_repo.create_done_by(db, data=done_by_in.model_dump())
    db.commit()
    db.refresh(new_person)
    return new_person


def get_done_by(db: Session, done_by_id: int) -> DoneByModel:
    return done_by_validation.validate_and_get_active_done_by(db, done_by_id=done_by_id)


def get_all_done_by(db: Session) -> list[DoneByModel]:
    return done_by_repo.list_active_done_by(db)


def update_done_by(
    db: Session, done_by_id: int, done_by_in: DoneByUpdate
) -> DoneByModel:
    person = done_by_validation.validate_and_get_active_done_by(db, done_by_id=done_by_id)

    update_data = done_by_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != person.name:
        done_by_validation.validate_done_by_name_is_unique(
            db, name=update_data["name"]
        )

    updated_person = done_by_repo.update_done_by(
        db, person=person, data=update_data
    )
    db.commit()
    db.refresh(updated_person)
    return updated_person


def delete_done_by(db: Session, done_by_id: int):
    person = done_by_validation.validate_and_get_active_done_by(db, done_by_id=done_by_id)

    done_by_repo.deactivate_done_by(db, person=person)
    db.commit()

    return {"message": "Person successfully deactivated."}