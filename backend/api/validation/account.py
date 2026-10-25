"""Business-rule validation layer for Account records."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.account import Account
from api.services.gstin_identity import validate_available


def validate_and_get_active_account(db: Session, account_id: int) -> Account:
    """Validate account exists and is active, returning instance with eager roles/ledgers."""
    from api.repository import account as account_repo
    account = account_repo.get_account_by_id(db, account_id=account_id)
    if not account or not account.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return account


def validate_account_code_is_unique(db: Session, account_code: str, exclude_id: int | None = None) -> None:
    """Ensure account_code is unique across all accounts."""
    if not account_code:
        return
    query = db.query(Account).filter(Account.account_code == account_code)
    if exclude_id is not None:
        query = query.filter(Account.id != exclude_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account code '{account_code}' already exists",
        )


def validate_gstin_is_unique(db: Session, gstin: str | None, exclude_id: int | None = None) -> None:
    """Ensure GSTIN is unique across accounts and legacy records."""
    if not gstin:
        return
    query = db.query(Account).filter(Account.gstin == gstin, Account.is_active == True)
    if exclude_id is not None:
        query = query.filter(Account.id != exclude_id)
    if query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GSTIN '{gstin}' is already registered with another account",
        )

