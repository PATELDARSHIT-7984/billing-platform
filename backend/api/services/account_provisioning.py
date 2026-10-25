"""Automatic account provisioning and legacy identity synchronization.

Maintains unified Account, AccountRole, AccountLedger, and LegacyAccountMap
records atomically alongside legacy Customer and Party transactions.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.model.account import Account, AccountRole, AccountLedger
from api.model.legacy_account_map import LegacyAccountMap
from api.schema.account_role import AccountRoleCode
from api.schema.party_type import PartyType
from api.utils.gst_state import GST_STATES, state_code_from_name


def _normalize_money(val: Any) -> Decimal:
    return Decimal(str(val or 0))


def _resolve_state_and_pan(
    gstin: str | None,
    raw_state: str | None,
    raw_state_code: str | None,
    raw_pan: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Derive consistent state, state_code, and pan_card adhering to Account constraints."""
    if gstin:
        state_code = gstin[:2]
        state = GST_STATES.get(state_code, raw_state)
        pan = gstin[2:12]
        return state, state_code, pan

    state_code = raw_state_code if raw_state_code in GST_STATES else None
    if not state_code and raw_state:
        try:
            code = state_code_from_name(raw_state)
            if code in GST_STATES:
                state_code = code
        except ValueError:
            state_code = None

    state = GST_STATES.get(state_code, raw_state)
    return state, state_code, raw_pan


def _resolve_role(source: str, legacy: Any) -> AccountRoleCode:
    if source == "customer":
        return AccountRoleCode.CUSTOMER
    if getattr(legacy, "party_type", None) == PartyType.PURCHASE_VENDOR:
        return AccountRoleCode.PURCHASE_VENDOR
    return AccountRoleCode.SUPPLIER


def _build_snapshot(source: str, legacy: Any) -> dict:
    if source == "customer":
        return {
            "id": legacy.id,
            "customer_code": legacy.customer_code,
            "customer_name": legacy.customer_name,
            "mobile": legacy.mobile,
            "email": legacy.email,
            "address": legacy.address,
            "city": legacy.city,
            "state": legacy.state,
            "pincode": legacy.pincode,
            "gstin": legacy.gstin,
            "pan_card": legacy.pan_card,
            "state_code": legacy.state_code,
            "opening_balance": str(legacy.opening_balance),
            "balance_type": legacy.balance_type,
            "current_balance": str(legacy.current_balance),
            "current_balance_type": legacy.current_balance_type,
            "remarks": legacy.remarks,
            "is_active": legacy.is_active,
        }
    return {
        "id": legacy.id,
        "party_code": legacy.party_code,
        "name": legacy.name,
        "party_type": str(legacy.party_type),
        "country_code": getattr(legacy, "country_code", None),
        "mobile": legacy.mobile,
        "address": legacy.address,
        "city": legacy.city,
        "state": legacy.state,
        "gstin": legacy.gstin,
        "pan_card": legacy.pan_card,
        "opening_balance": str(legacy.opening_balance),
        "balance_type": legacy.balance_type,
        "opening_remark": getattr(legacy, "opening_remark", None),
        "current_balance": str(legacy.current_balance),
        "current_balance_type": legacy.current_balance_type,
        "is_active": legacy.is_active,
    }


def provision_legacy_account(
    db: Session,
    source: str,
    legacy: Any,
) -> tuple[Account, AccountRole, AccountLedger, LegacyAccountMap]:
    """Atomically provision Account, AccountRole, AccountLedger, and LegacyAccountMap for a new legacy entity."""
    legacy_code = getattr(legacy, "customer_code", None) or getattr(legacy, "party_code", None)
    if not legacy_code or not str(legacy_code).strip():
        prefix = "CUS" if source == "customer" else "PTY"
        candidate = f"{prefix}-{legacy.id:04d}"
        if db.query(Account).filter_by(account_code=candidate).first():
            candidate = f"{prefix}-{legacy.id:04d}-{legacy.id}"
        legacy_code = candidate
        if source == "customer" and not getattr(legacy, "customer_code", None):
            legacy.customer_code = legacy_code
        elif source == "party" and not getattr(legacy, "party_code", None):
            legacy.party_code = legacy_code

    name = getattr(legacy, "customer_name", None) or getattr(legacy, "name", None) or legacy_code
    role_code = _resolve_role(source, legacy)
    state, state_code, pan = _resolve_state_and_pan(
        legacy.gstin,
        getattr(legacy, "state", None),
        getattr(legacy, "state_code", None),
        getattr(legacy, "pan_card", None),
    )

    open_bal = _normalize_money(legacy.opening_balance)
    open_type = legacy.balance_type if open_bal > 0 else None
    curr_bal = _normalize_money(legacy.current_balance)
    curr_type = legacy.current_balance_type if curr_bal > 0 else None

    account = Account(
        account_code=legacy_code,
        account_name=name,
        country_code=getattr(legacy, "country_code", "+91") or "+91",
        mobile=legacy.mobile,
        email=getattr(legacy, "email", None),
        address=legacy.address,
        city=legacy.city,
        state=state,
        pincode=getattr(legacy, "pincode", None),
        state_code=state_code,
        gstin=legacy.gstin,
        gstin_pending=False,
        pan_card=pan,
        remarks=getattr(legacy, "remarks", None) or getattr(legacy, "opening_remark", None),
        is_active=legacy.is_active if legacy.is_active is not None else True,
    )
    db.add(account)
    db.flush()

    role = AccountRole(
        account_id=account.id,
        role=role_code,
        is_active=account.is_active,
    )
    db.add(role)

    ledger = AccountLedger(
        account_id=account.id,
        role=role_code,
        opening_balance=open_bal,
        balance_type=open_type,
        current_balance=curr_bal,
        current_balance_type=curr_type,
        opening_remark=getattr(legacy, "opening_remark", None),
    )
    db.add(ledger)
    db.flush()

    mapping = LegacyAccountMap(
        legacy_source=source,
        legacy_id=legacy.id,
        account_id=account.id,
        account_role=role_code.value,
        account_ledger_id=ledger.id,
        legacy_code=legacy_code,
        migration_revision="runtime",
        source_snapshot=_build_snapshot(source, legacy),
    )
    db.add(mapping)
    db.flush()

    return account, role, ledger, mapping


def sync_legacy_account_update(db: Session, source: str, legacy: Any) -> None:
    """Synchronize updates from a legacy entity into linked Account and AccountLedger."""
    mapping = db.get(LegacyAccountMap, (source, legacy.id))
    if not mapping:
        provision_legacy_account(db, source, legacy)
        return

    account = db.get(Account, mapping.account_id)
    if not account:
        return

    name = getattr(legacy, "customer_name", None) or getattr(legacy, "name", None)
    if name:
        account.account_name = name
    if hasattr(legacy, "mobile"):
        account.mobile = legacy.mobile
    if hasattr(legacy, "email"):
        account.email = legacy.email
    if hasattr(legacy, "address"):
        account.address = legacy.address
    if hasattr(legacy, "city"):
        account.city = legacy.city
    if hasattr(legacy, "pincode"):
        account.pincode = legacy.pincode

    state, state_code, pan = _resolve_state_and_pan(
        legacy.gstin,
        getattr(legacy, "state", None),
        getattr(legacy, "state_code", None),
        getattr(legacy, "pan_card", None),
    )
    account.gstin = legacy.gstin
    account.state = state
    account.state_code = state_code
    account.pan_card = pan
    account.gstin_pending = False

    remarks = getattr(legacy, "remarks", None) or getattr(legacy, "opening_remark", None)
    if remarks is not None:
        account.remarks = remarks

    if legacy.is_active is not None:
        account.is_active = legacy.is_active
        role = db.query(AccountRole).filter_by(account_id=account.id, role=mapping.account_role).first()
        if role:
            role.is_active = legacy.is_active

    ledger = db.get(AccountLedger, mapping.account_ledger_id)
    if ledger:
        open_bal = _normalize_money(legacy.opening_balance)
        curr_bal = _normalize_money(legacy.current_balance)
        ledger.opening_balance = open_bal
        ledger.balance_type = legacy.balance_type if open_bal > 0 else None
        ledger.current_balance = curr_bal
        ledger.current_balance_type = legacy.current_balance_type if curr_bal > 0 else None
        if hasattr(legacy, "opening_remark"):
            ledger.opening_remark = legacy.opening_remark

    mapping.source_snapshot = _build_snapshot(source, legacy)
    db.flush()


def deactivate_legacy_account(db: Session, source: str, legacy_id: int) -> None:
    """Deactivate linked Account and AccountRole upon legacy entity deactivation."""
    mapping = db.get(LegacyAccountMap, (source, legacy_id))
    if not mapping:
        return
    account = db.get(Account, mapping.account_id)
    if account:
        account.is_active = False
    role = db.query(AccountRole).filter_by(account_id=mapping.account_id, role=mapping.account_role).first()
    if role:
        role.is_active = False
    db.flush()


def sync_or_provision_account(db: Session, source: str, legacy: Any) -> None:
    """Entry point for save_account to either sync existing mapping or provision a new account."""
    mapping = db.get(LegacyAccountMap, (source, legacy.id))
    if mapping:
        sync_legacy_account_update(db, source, legacy)
    else:
        provision_legacy_account(db, source, legacy)


def resolve_ledger_reference(db: Session, source: str, legacy_id: int | None) -> tuple[int | None, str | None]:
    """Resolve (account_ledger_id, account_role) for a legacy customer or party ID.

    If unmapped, automatically provisions the account atomically.
    Returns (None, None) if legacy_id is None.
    """
    if not legacy_id:
        return None, None
    mapping = db.get(LegacyAccountMap, (source, legacy_id))
    if mapping:
        return mapping.account_ledger_id, mapping.account_role

    from api.model.customer import Customer
    from api.model.party import Party
    legacy_row = db.get(Customer if source == "customer" else Party, legacy_id)
    if legacy_row:
        _, role, ledger, _ = provision_legacy_account(db, source, legacy_row)
        return ledger.id, role.role.value

    # Direct Account.id support
    target_role = AccountRoleCode.CUSTOMER if source == "customer" else AccountRoleCode.SUPPLIER
    ledger = db.query(AccountLedger).filter(
        AccountLedger.account_id == legacy_id,
        AccountLedger.role == target_role,
    ).first()
    if not ledger and source == "party":
        ledger = db.query(AccountLedger).filter(
            AccountLedger.account_id == legacy_id,
            AccountLedger.role == AccountRoleCode.PURCHASE_VENDOR,
        ).first()
    if ledger:
        return ledger.id, ledger.role.value if hasattr(ledger.role, "value") else str(ledger.role)

    return None, None


def resolve_account_reference(db: Session, source: str, legacy_id: int | None) -> int | None:
    """Resolve account_id for a legacy customer or party ID (e.g. for Quotation)."""
    if not legacy_id:
        return None
    mapping = db.get(LegacyAccountMap, (source, legacy_id))
    if mapping:
        return mapping.account_id

    from api.model.customer import Customer
    from api.model.party import Party
    legacy_row = db.get(Customer if source == "customer" else Party, legacy_id)
    if legacy_row:
        account, _, _, _ = provision_legacy_account(db, source, legacy_row)
        return account.id

    acc = db.get(Account, legacy_id)
    if acc:
        return acc.id

    return None


# ============================================================================
# LEDGER BALANCE POSTING & FULL-SETTLEMENT ENGINE
# ============================================================================

def signed_ledger_balance(amount: Any, direction: str | None) -> Decimal:
    """Return signed ledger balance (Debit = negative, Credit = positive)."""
    if not amount:
        return Decimal("0.00")
    amt = Decimal(str(amount))
    return -amt if direction == "Debit" else amt


def ledger_balance_after_delta(
    amount: Any,
    direction: str | None,
    delta: Decimal | int | float,
) -> tuple[Decimal, str | None]:
    """Compute new ledger balance and direction enforcing ck_account_ledgers_current_direction.

    When new balance is 0.00, direction is None.
    When new balance < 0, direction is 'Debit'.
    When new balance > 0, direction is 'Credit'.
    """
    val = signed_ledger_balance(amount, direction) + Decimal(str(delta))
    if val == 0:
        return Decimal("0.00"), None
    amt = abs(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amt, ("Debit" if val < 0 else "Credit")


def get_ledger_for_balance_update(db: Session, ledger_id: int) -> AccountLedger | None:
    """Fetch AccountLedger row with exclusive row lock for balance updates."""
    return (
        db.query(AccountLedger)
        .filter(AccountLedger.id == ledger_id)
        .populate_existing()
        .with_for_update()
        .first()
    )


def _sync_legacy_from_ledger(db: Session, ledger: AccountLedger) -> None:
    """Reflect updated ledger balance back to mapped legacy Customer or Party."""
    mapping = db.query(LegacyAccountMap).filter_by(account_ledger_id=ledger.id).first()
    if not mapping:
        return
    if mapping.legacy_source == "customer":
        from api.model.customer import Customer
        cust = db.get(Customer, mapping.legacy_id)
        if cust:
            cust.current_balance = ledger.current_balance
            cust.current_balance_type = ledger.current_balance_type or "Credit"
    elif mapping.legacy_source == "party":
        from api.model.party import Party
        pty = db.get(Party, mapping.legacy_id)
        if pty:
            pty.current_balance = ledger.current_balance
            pty.current_balance_type = ledger.current_balance_type or "Credit"


def apply_account_ledger_delta(
    db: Session,
    account_ledger_id: int,
    delta: Decimal | int | float,
    sync_legacy: bool = False,
) -> AccountLedger:
    """Apply signed delta to AccountLedger. Caller owns commit and rollback."""
    ledger = get_ledger_for_balance_update(db, account_ledger_id)
    if not ledger:
        raise HTTPException(status_code=404, detail="Account ledger not found")

    new_amount, new_direction = ledger_balance_after_delta(
        ledger.current_balance, ledger.current_balance_type, delta
    )
    ledger.current_balance = new_amount
    ledger.current_balance_type = new_direction
    if sync_legacy:
        _sync_legacy_from_ledger(db, ledger)
    db.flush()
    return ledger


def get_account_net_settlement(db: Session, account_id: int) -> dict:
    """Calculate consolidated full & final net settlement across all roles of an account.

    Formula:
    Net Balance = Total Credit (Payable) - Total Debit (Receivable)
    - If Net Balance < 0: Net direction is 'Debit' (Party owes company). Status = 'RECEIVABLE'.
    - If Net Balance > 0: Net direction is 'Credit' (Company owes party). Status = 'PAYABLE'.
    - If Net Balance == 0: Net direction is None (Fully settled). Status = 'SETTLED'.
    """
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    ledgers = db.query(AccountLedger).filter_by(account_id=account_id).all()
    roles_breakdown = []
    total_debit = Decimal("0.00")   # Receivable from party
    total_credit = Decimal("0.00")  # Payable to party

    for ledger in ledgers:
        curr_bal = Decimal(str(ledger.current_balance or 0)).quantize(Decimal("0.01"))
        curr_type = ledger.current_balance_type
        if curr_type == "Debit":
            total_debit += curr_bal
            direction_role = "RECEIVABLE"
        elif curr_type == "Credit":
            total_credit += curr_bal
            direction_role = "PAYABLE"
        else:
            direction_role = "SETTLED"

        roles_breakdown.append({
            "account_ledger_id": ledger.id,
            "role": ledger.role.value if hasattr(ledger.role, "value") else str(ledger.role),
            "opening_balance": Decimal(str(ledger.opening_balance or 0)).quantize(Decimal("0.01")),
            "balance_type": ledger.balance_type,
            "current_balance": curr_bal,
            "current_balance_type": curr_type,
            "balance": curr_bal,
            "direction_role": direction_role,
            "opening_remark": ledger.opening_remark,
        })

    net_signed = total_credit - total_debit
    if net_signed == 0:
        net_amount = Decimal("0.00")
        net_direction = None
        status = "SETTLED"
        summary_text = "Account is fully settled (₹0.00 balance)."
    elif net_signed < 0:
        net_amount = abs(net_signed).quantize(Decimal("0.01"))
        net_direction = "Debit"
        status = "RECEIVABLE"
        summary_text = f"This party owes you ₹{net_amount:,.2f}."
    else:
        net_amount = net_signed.quantize(Decimal("0.01"))
        net_direction = "Credit"
        status = "PAYABLE"
        summary_text = f"You need to pay ₹{net_amount:,.2f} to this party."

    return {
        "account_id": account.id,
        "account_code": account.account_code,
        "account_name": account.account_name,
        "net_amount": net_amount,
        "net_direction": net_direction,
        "settlement_status": status,
        "summary_text": summary_text,
        "total_receivable": total_debit,
        "total_payable": total_credit,
        "roles": roles_breakdown,
    }


def apply_contra_offset(
    db: Session,
    account_id: int,
    receivable_role: AccountRoleCode | str,
    payable_role: AccountRoleCode | str,
    amount: Decimal | int | float,
    remark: str | None = None,
) -> dict:
    """Atomically offset balances between two opposing roles of the same account.

    Locks both ledgers in strictly ascending numerical ID order to prevent deadlocks.
    Reduces the receivable role's Debit balance (delta = +amount) and reduces
    the payable role's Credit balance (delta = -amount).
    """
    offset_amt = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if offset_amt <= 0:
        raise HTTPException(status_code=400, detail="Contra offset amount must be greater than zero")

    rec_role_str = receivable_role.value if hasattr(receivable_role, "value") else str(receivable_role)
    pay_role_str = payable_role.value if hasattr(payable_role, "value") else str(payable_role)
    if rec_role_str == pay_role_str:
        raise HTTPException(status_code=400, detail="Cannot perform contra offset on the same role")

    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    ledger_rec = db.query(AccountLedger).filter_by(account_id=account_id, role=rec_role_str).first()
    ledger_pay = db.query(AccountLedger).filter_by(account_id=account_id, role=pay_role_str).first()
    if not ledger_rec or not ledger_pay:
        raise HTTPException(status_code=404, detail="Both roles must exist for this account")

    # Lock both ledgers in strictly ascending numerical ID order to prevent deadlocks
    first_id, second_id = sorted([ledger_rec.id, ledger_pay.id])
    db.query(AccountLedger).filter(AccountLedger.id == first_id).populate_existing().with_for_update().first()
    db.query(AccountLedger).filter(AccountLedger.id == second_id).populate_existing().with_for_update().first()

    # Re-read fresh instances
    ledger_rec = db.get(AccountLedger, ledger_rec.id)
    ledger_pay = db.get(AccountLedger, ledger_pay.id)

    # Auto-align roles by direction: ledger_rec MUST be the Debit role, ledger_pay MUST be the Credit role
    if ledger_rec.current_balance_type == "Credit" and ledger_pay.current_balance_type == "Debit":
        ledger_rec, ledger_pay = ledger_pay, ledger_rec

    if ledger_rec.current_balance_type != "Debit" or ledger_pay.current_balance_type != "Credit":
        raise HTTPException(
            status_code=400,
            detail="Contra offset requires one role with Debit (Receivable) balance and one role with Credit (Payable) balance.",
        )

    max_allowable = min(Decimal(str(ledger_rec.current_balance or 0)), Decimal(str(ledger_pay.current_balance or 0)))
    if offset_amt > max_allowable:
        raise HTTPException(
            status_code=400,
            detail=f"Contra offset amount ₹{offset_amt:,.2f} exceeds maximum allowable ₹{max_allowable:,.2f}.",
        )

    # Receivable (Dr) reduced by adding credit delta (+offset_amt)
    new_rec_amt, new_rec_dir = ledger_balance_after_delta(
        ledger_rec.current_balance, ledger_rec.current_balance_type, offset_amt
    )
    # Payable (Cr) reduced by adding debit delta (-offset_amt)
    new_pay_amt, new_pay_dir = ledger_balance_after_delta(
        ledger_pay.current_balance, ledger_pay.current_balance_type, -offset_amt
    )

    ledger_rec.current_balance = new_rec_amt
    ledger_rec.current_balance_type = new_rec_dir
    ledger_pay.current_balance = new_pay_amt
    ledger_pay.current_balance_type = new_pay_dir

    _sync_legacy_from_ledger(db, ledger_rec)
    _sync_legacy_from_ledger(db, ledger_pay)

    db.flush()
    return get_account_net_settlement(db, account_id)


