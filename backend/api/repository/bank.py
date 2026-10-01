"""
Data-access layer for Bank records.

Rules for this module:
- No HTTPException here. Every lookup returns the ORM object or None.
- No db.commit() / db.rollback() here. Callers (service layer) own the
  transaction boundary. We only db.add() / db.flush() so the caller can
  see generated IDs before deciding to commit.
- No business rules here (uniqueness decisions, defaults, formatting).
  This module only knows how to talk to the `banks` table.
"""

from sqlalchemy.orm import Session

from api.model.bank import BankModel


def get_bank_by_id(db: Session, bank_id: int) -> BankModel | None:
    return db.query(BankModel).filter(BankModel.id == bank_id).first()


def get_active_bank_by_id(db: Session, bank_id: int) -> BankModel | None:
    return (
        db.query(BankModel)
        .filter(
            BankModel.id == bank_id,
            BankModel.is_active == True,
        )
        .first()
    )


def get_bank_by_name(db: Session, name: str) -> BankModel | None:
    return db.query(BankModel).filter(BankModel.name == name).first()


def list_active_banks(db: Session) -> list[BankModel]:
    return db.query(BankModel).filter(BankModel.is_active == True).all()


def create_bank(db: Session, data: dict) -> BankModel:
    bank = BankModel(**data)
    db.add(bank)
    db.flush()
    return bank


def update_bank(db: Session, bank: BankModel, data: dict) -> BankModel:
    for field_name, field_value in data.items():
        setattr(bank, field_name, field_value)
    db.flush()
    return bank


def deactivate_bank(db: Session, bank: BankModel) -> BankModel:
    bank.is_active = False
    db.flush()
    return bank
