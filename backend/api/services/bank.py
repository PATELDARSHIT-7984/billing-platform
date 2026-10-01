from sqlalchemy.orm import Session

from api.repository import bank as bank_repo
from api.schema.bank import BankCreate, BankUpdate
from api.validation import bank as bank_validation


def create_bank(db: Session, bank_in: BankCreate):
    bank_validation.validate_bank_name_is_unique(db, name=bank_in.name)

    new_bank = bank_repo.create_bank(db, data=bank_in.model_dump())
    db.commit()
    db.refresh(new_bank)
    return new_bank


def get_bank(db: Session, bank_id: int):
    return bank_validation.validate_and_get_active_bank(db, bank_id=bank_id)


def get_all_banks(db: Session):
    return bank_repo.list_active_banks(db)


def update_bank(db: Session, bank_id: int, bank_in: BankUpdate):
    bank = bank_validation.validate_and_get_active_bank(db, bank_id=bank_id)

    update_data = bank_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != bank.name:
        bank_validation.validate_bank_name_is_unique(
            db, name=update_data["name"]
        )

    updated_bank = bank_repo.update_bank(db, bank=bank, data=update_data)
    db.commit()
    db.refresh(updated_bank)
    return updated_bank


def delete_bank(db: Session, bank_id: int):
    bank = bank_validation.validate_and_get_active_bank(db, bank_id=bank_id)

    bank_repo.deactivate_bank(db, bank=bank)
    db.commit()
    return {"message": "Bank successfully deactivated."}