"""Service layer for unified Account business logic, settlement, and contra operations."""
from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.account import Account
from api.schema.account import (
    AccountCreate,
    AccountUpdate,
    AccountRoleInput,
    AccountContraOffsetRequest,
)
from api.schema.account_role import AccountRoleCode
from api.repository import account as account_repo
from api.validation import account as account_validation
from api.services.account_provisioning import (
    get_account_net_settlement,
    apply_contra_offset,
    _resolve_state_and_pan,
)


def create_account(db: Session, data: AccountCreate) -> Account:
    """Create a unified account with one or more roles and initial ledgers."""
    # 1. Resolve or auto-generate unique account code
    code = data.account_code.strip() if data.account_code and data.account_code.strip() else None
    if code:
        account_validation.validate_account_code_is_unique(db, code)
    else:
        code = account_repo.generate_account_code(db)

    # 2. Validate GSTIN uniqueness if provided
    if data.gstin:
        account_validation.validate_gstin_is_unique(db, data.gstin)

    # 3. Derive consistent state, state_code, and PAN
    state, state_code, pan = _resolve_state_and_pan(
        data.gstin, data.state, data.state_code, data.pan_card
    )

    # 4. Normalize roles (default to CUSTOMER role with ₹0.00 if omitted)
    roles_input = data.roles
    if not roles_input:
        roles_input = [AccountRoleInput(role=AccountRoleCode.CUSTOMER, opening_balance=Decimal("0.00"), balance_type=None)]

    account_payload = {
        "account_code": code,
        "account_name": data.account_name.strip(),
        "country_code": data.country_code or "+91",
        "mobile": data.mobile.strip() if data.mobile else None,
        "email": data.email,
        "address": data.address.strip() if data.address else None,
        "city": data.city.strip() if data.city else None,
        "state": state,
        "pincode": data.pincode.strip() if data.pincode else None,
        "state_code": state_code,
        "gstin": data.gstin,
        "gstin_pending": data.gstin_pending,
        "pan_card": pan,
        "remarks": data.remarks.strip() if data.remarks else None,
        "is_active": data.is_active,
    }

    roles_payload = [
        {
            "role": r.role,
            "opening_balance": r.opening_balance,
            "balance_type": r.balance_type,
            "opening_remark": r.opening_remark,
        }
        for r in roles_input
    ]

    account = account_repo.create_account(db, account_payload, roles_payload)
    db.commit()
    return account


def get_account_by_id(db: Session, account_id: int) -> Account:
    """Retrieve an active account by its primary key ID."""
    return account_validation.validate_and_get_active_account(db, account_id)


def get_all_accounts(
    db: Session,
    search: Optional[str] = None,
    role: Optional[AccountRoleCode | str] = None,
    skip: int = 0,
    limit: int = 10,
    count_only: bool = False,
) -> list[Account] | int:
    """List or search accounts across name, address, phone, GSTIN with pagination."""
    return account_repo.list_accounts(
        db,
        search=search,
        role=role,
        skip=skip,
        limit=limit,
        count_only=count_only,
    )


def update_account(db: Session, account_id: int, data: AccountUpdate) -> Account:
    """Update editable fields on an existing account, including role ledger balances."""
    account = account_validation.validate_and_get_active_account(db, account_id)
    update_data = data.model_dump(exclude_unset=True)

    # Extract roles before passing remaining fields to repo
    roles_data = update_data.pop("roles", None)

    if "account_name" in update_data and update_data["account_name"]:
        update_data["account_name"] = update_data["account_name"].strip()

    if "gstin" in update_data and update_data["gstin"] != account.gstin:
        account_validation.validate_gstin_is_unique(db, update_data["gstin"], exclude_id=account_id)

    # Recalculate derived state and PAN if tax fields changed
    if any(k in update_data for k in ("gstin", "state", "state_code", "pan_card")):
        state, state_code, pan = _resolve_state_and_pan(
            update_data.get("gstin", account.gstin),
            update_data.get("state", account.state),
            update_data.get("state_code", account.state_code),
            update_data.get("pan_card", account.pan_card),
        )
        update_data["state"] = state
        update_data["state_code"] = state_code
        update_data["pan_card"] = pan

    # Update profile fields
    if update_data:
        account_repo.update_account(db, account, update_data)

    # Update role ledger balances (or add new roles)
    if roles_data is not None:
        _update_account_roles(db, account, roles_data)

    db.commit()
    return account_repo.get_account_by_id(db, account.id)


def _update_account_roles(db: Session, account: Account, roles_data: list[dict]) -> None:
    """Upsert role ledgers: update opening balance on existing, create new roles."""
    from api.model.account import AccountRole, AccountLedger
    from api.services.account_provisioning import (
        signed_ledger_balance,
        ledger_balance_after_delta,
        _sync_legacy_from_ledger,
    )

    existing_role_map = {}
    for r in account.roles:
        role_key = r.role.value if hasattr(r.role, "value") else str(r.role)
        existing_role_map[role_key] = r

    for rd in roles_data:
        role_key = rd["role"].value if hasattr(rd["role"], "value") else str(rd["role"])
        new_open_bal = Decimal(str(rd.get("opening_balance") or 0))
        new_open_dir = rd.get("balance_type") if new_open_bal > 0 else None
        new_remark = rd.get("opening_remark")

        if role_key in existing_role_map:
            role_obj = existing_role_map[role_key]
            ledger = role_obj.ledger
            if not ledger:
                continue

            from sqlalchemy import text

            # Check if this ledger has any posted transactions
            has_transactions = db.execute(
                text(
                    "SELECT (EXISTS(SELECT 1 FROM bill WHERE account_ledger_id = :lid) "
                    "OR EXISTS(SELECT 1 FROM purchases WHERE account_ledger_id = :lid) "
                    "OR EXISTS(SELECT 1 FROM sales_returns WHERE account_ledger_id = :lid) "
                    "OR EXISTS(SELECT 1 FROM purchase_returns WHERE account_ledger_id = :lid) "
                    "OR EXISTS(SELECT 1 FROM rojmel WHERE account_ledger_id = :lid))"
                ),
                {"lid": ledger.id},
            ).scalar()

            if not has_transactions:
                tx_movements = Decimal("0.00")
            else:
                old_signed_open = signed_ledger_balance(ledger.opening_balance, ledger.balance_type)
                old_signed_curr = signed_ledger_balance(ledger.current_balance, ledger.current_balance_type)
                tx_movements = old_signed_curr - old_signed_open

            # Update opening balance
            ledger.opening_balance = new_open_bal
            ledger.balance_type = new_open_dir
            ledger.opening_remark = new_remark

            # Recompute current balance = new opening + preserved transaction movements
            new_signed_curr = signed_ledger_balance(new_open_bal, new_open_dir) + tx_movements
            if new_signed_curr == 0:
                ledger.current_balance = Decimal("0.00")
                ledger.current_balance_type = None
            else:
                ledger.current_balance = abs(new_signed_curr).quantize(Decimal("0.01"))
                ledger.current_balance_type = "Debit" if new_signed_curr < 0 else "Credit"

            _sync_legacy_from_ledger(db, ledger)
        else:
            # New role — create it
            account_repo.add_role_to_account(
                db,
                account_id=account.id,
                role_code=rd["role"],
                opening_balance=new_open_bal,
                balance_type=new_open_dir,
                opening_remark=new_remark,
            )

    db.flush()


def delete_account(db: Session, account_id: int) -> dict:
    """Soft-delete an active account and its roles."""
    account = account_validation.validate_and_get_active_account(db, account_id)
    account_repo.deactivate_account(db, account)
    db.commit()
    return {"message": f"Account '{account.account_name}' deleted successfully"}


def get_account_settlement(db: Session, account_id: int) -> dict:
    """Calculate consolidated full & final net settlement for all roles."""
    account_validation.validate_and_get_active_account(db, account_id)
    return get_account_net_settlement(db, account_id)


def execute_contra_offset(
    db: Session,
    account_id: int,
    request: AccountContraOffsetRequest,
) -> dict:
    """Atomically offset balances between two roles belonging to this account."""
    account_validation.validate_and_get_active_account(db, account_id)
    result = apply_contra_offset(
        db,
        account_id=account_id,
        receivable_role=request.receivable_role,
        payable_role=request.payable_role,
        amount=request.amount,
        remark=request.remark,
    )
    db.commit()
    return result


def add_role_to_account(
    db: Session,
    account_id: int,
    role_input: AccountRoleInput,
) -> Account:
    """Add a new role and ledger to an existing account."""
    account = account_validation.validate_and_get_active_account(db, account_id)
    existing_roles = {r.role for r in account.roles if r.is_active}
    if role_input.role in existing_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account already has active role '{role_input.role.value}'",
        )

    account_repo.add_role_to_account(
        db,
        account_id=account.id,
        role_code=role_input.role,
        opening_balance=role_input.opening_balance,
        balance_type=role_input.balance_type,
        opening_remark=role_input.opening_remark,
    )
    db.commit()
    db.expire_all()
    return account_repo.get_account_by_id(db, account.id)
