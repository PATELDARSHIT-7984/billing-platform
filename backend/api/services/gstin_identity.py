"""One indexed identity namespace; account services own the account transaction."""
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from api.model.account_gstin import AccountGSTIN
from api.services.account_provisioning import sync_or_provision_account
from api.utils.gstin import normalize_gstin

DUPLICATE_GSTIN = "GSTIN is already used by another account."


def validate_available(db, gstin, source, account_id=None):
    gstin = normalize_gstin(gstin)
    if gstin:
        owner = db.query(AccountGSTIN).filter_by(normalized_gstin=gstin).first()
        if owner and (owner.account_source, owner.account_id) != (source, account_id):
            raise HTTPException(400, DUPLICATE_GSTIN)


def save_account(db, source, write):
    """Flush the account to obtain its ID, reserve identity, then commit both.

    A flush is not a commit: failed reservation also rolls back the account.
    Updates already hold the existing account row lock until this commit.
    """
    try:
        account = write()
        gstin = normalize_gstin(account.gstin)
        owner = db.get(AccountGSTIN, (source, account.id))
        if gstin:
            if owner:
                owner.normalized_gstin = gstin
            else:
                db.add(AccountGSTIN(account_source=source, account_id=account.id,
                                    normalized_gstin=gstin))
        elif owner:
            db.delete(owner)
        sync_or_provision_account(db, source, account)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        # Retain existing domain indexes; a same-domain race can hit them first.
        if constraint in {"uq_account_gstin", "uq_accounts_gstin", "customers_gstin_key", "ix_parties_gstin"} or any(
            marker in str(error.orig) for marker in (
                "UNIQUE constraint failed: account_gstin_registry.normalized_gstin",
                "UNIQUE constraint failed: customers.gstin",
                "UNIQUE constraint failed: parties.gstin",
                "UNIQUE constraint failed: accounts.gstin",
            )
        ):
            raise HTTPException(400, DUPLICATE_GSTIN) from None
        raise HTTPException(400, "Account conflicts with an existing record.") from None
    except Exception:
        db.rollback()
        raise
    db.refresh(account)
    return account
