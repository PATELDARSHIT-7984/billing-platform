"""Repository layer for unified Account, AccountRole, and AccountLedger persistence."""
from decimal import Decimal
from typing import Optional
from sqlalchemy import or_, func, text
from sqlalchemy.orm import Session, joinedload

from api.model.account import Account, AccountRole, AccountLedger
from api.schema.account_role import AccountRoleCode


def get_database_dialect_name(db: Session) -> str:
    """Return database dialect name ('postgresql' or 'sqlite')."""
    return db.bind.dialect.name if db.bind else "sqlite"


def get_next_account_code_sequence_value(db: Session) -> int:
    """Get next sequence value from PostgreSQL sequence if present."""
    return db.execute(text("SELECT nextval('account_code_seq')")).scalar()


def get_max_account_id(db: Session) -> int:
    """Return highest account id currently in database."""
    highest_id = db.query(func.max(Account.id)).scalar()
    return int(highest_id) if highest_id is not None else 0


def generate_account_code(db: Session) -> str:
    """Generate sequential account code identifier e.g. ACC-0001."""
    dialect_name = get_database_dialect_name(db)
    if dialect_name == "postgresql":
        try:
            seq_exists = db.execute(text("SELECT to_regclass('public.account_code_seq')")).scalar()
            if seq_exists:
                val = get_next_account_code_sequence_value(db)
                return f"ACC-{int(val):04d}"
        except Exception:
            pass

    highest_id = get_max_account_id(db)
    candidate = f"ACC-{int(highest_id) + 1:04d}"
    while db.query(Account).filter_by(account_code=candidate).first():
        highest_id += 1
        candidate = f"ACC-{int(highest_id) + 1:04d}"
    return candidate


def get_account_by_id(
    db: Session,
    account_id: int,
    include_inactive: bool = False,
) -> Account | None:
    """Retrieve account with eager-loaded roles and ledgers."""
    query = (
        db.query(Account)
        .options(joinedload(Account.roles).joinedload(AccountRole.ledger))
        .filter(Account.id == account_id)
    )
    if not include_inactive:
        query = query.filter(Account.is_active == True)
    return query.first()


def get_account_by_code(db: Session, account_code: str) -> Account | None:
    """Retrieve account by exact account code."""
    return db.query(Account).filter(Account.account_code == account_code).first()


def list_accounts(
    db: Session,
    search: str | None = None,
    role: AccountRoleCode | str | None = None,
    skip: int = 0,
    limit: int = 10,
    count_only: bool = False,
) -> list[Account] | int:
    """Global search across accounts by name, address, city, code, mobile, and GSTIN with pagination."""
    query = db.query(Account).filter(Account.is_active == True)

    if role:
        role_val = role.value if hasattr(role, "value") else str(role)
        query = query.join(AccountRole, AccountRole.account_id == Account.id).filter(
            AccountRole.role == role_val,
            AccountRole.is_active == True,
        )

    if search and isinstance(search, str) and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Account.account_name.ilike(term),
                Account.address.ilike(term),
                Account.city.ilike(term),
                Account.state.ilike(term),
                Account.account_code.ilike(term),
                Account.mobile.ilike(term),
                Account.gstin.ilike(term),
            )
        )

    if count_only:
        return query.distinct(Account.id).count() if role else query.count()

    return (
        query.options(joinedload(Account.roles).joinedload(AccountRole.ledger))
        .order_by(Account.account_name.asc(), Account.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_account(
    db: Session,
    account_data: dict,
    roles_data: list[dict],
) -> Account:
    """Atomically create Account with its associated AccountRole and AccountLedger entries."""
    account = Account(**account_data)
    db.add(account)
    db.flush()

    for r_data in roles_data:
        role_code = r_data["role"]
        open_bal = Decimal(str(r_data.get("opening_balance") or 0))
        open_dir = r_data.get("balance_type") if open_bal > 0 else None

        role = AccountRole(account_id=account.id, role=role_code, is_active=True)
        db.add(role)

        ledger = AccountLedger(
            account_id=account.id,
            role=role_code,
            opening_balance=open_bal,
            balance_type=open_dir,
            current_balance=open_bal,
            current_balance_type=open_dir,
            opening_remark=r_data.get("opening_remark"),
        )
        db.add(ledger)

    db.flush()
    # Refresh to load roles and ledgers relationship
    return get_account_by_id(db, account.id)


def update_account(
    db: Session,
    account: Account,
    update_fields: dict,
) -> Account:
    """Update fields on an existing Account instance."""
    for field, value in update_fields.items():
        if hasattr(account, field):
            setattr(account, field, value)
    db.flush()
    return get_account_by_id(db, account.id)


def deactivate_account(db: Session, account: Account) -> None:
    """Soft-deactivate an account and all its active roles."""
    account.is_active = False
    for role in account.roles:
        role.is_active = False
    db.flush()


def add_role_to_account(
    db: Session,
    account_id: int,
    role_code: AccountRoleCode | str,
    opening_balance: Decimal = Decimal("0.00"),
    balance_type: str | None = None,
    opening_remark: str | None = None,
) -> AccountRole:
    """Add a new role and ledger to an existing account."""
    open_bal = Decimal(str(opening_balance or 0))
    open_dir = balance_type if open_bal > 0 else None

    role = AccountRole(account_id=account_id, role=role_code, is_active=True)
    db.add(role)

    ledger = AccountLedger(
        account_id=account_id,
        role=role_code,
        opening_balance=open_bal,
        balance_type=open_dir,
        current_balance=open_bal,
        current_balance_type=open_dir,
        opening_remark=opening_remark,
    )
    db.add(ledger)
    db.flush()
    return role

