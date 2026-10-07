"""
Data-access layer for Customer records.

Same rules as the other repository modules: no HTTPException,
no commit/rollback. GSTIN/PAN normalization and customer-code
formatting ("CUS-0004") stay in the service layer.

get_active_customer_by_id is the canonical "does this customer exist
and is it active" lookup -- reused by the bill, quotation, and
sales_return repository modules instead of each re-querying Customer
directly, so there is exactly one place that defines what an
"active customer" lookup means.
"""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from api.model.customer import Customer


def get_database_dialect_name(db: Session) -> str:
    return db.get_bind().dialect.name


def get_next_customer_code_sequence_value(db: Session) -> int:
    """PostgreSQL-only. Caller must confirm the dialect first."""
    return db.execute(text("SELECT nextval('customer_code_seq')")).scalar_one()


def get_max_customer_id(db: Session) -> int:
    """SQLite-test-database fallback. Returns 0 when the table is empty."""
    return db.query(func.max(Customer.id)).scalar() or 0


def get_active_customer_by_id(db: Session, customer_id: int) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            Customer.id == customer_id,
            Customer.is_active == True,
        )
        .first()
    )


def get_customer_by_id_any_status(db: Session, customer_id: int) -> Customer | None:
    return db.query(Customer).filter(Customer.id == customer_id).first()


def get_customer_for_balance_update(db: Session, customer_id: int) -> Customer | None:
    # NO KEY UPDATE serializes balance writers without conflicting with FK checks.
    # Refresh the identity map: validation may have loaded a stale account earlier.
    return (db.query(Customer).filter(Customer.id == customer_id)
            .populate_existing().with_for_update(key_share=True).first())


def get_customer_by_gstin(db: Session, gstin: str) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            Customer.gstin == gstin,
        )
        .first()
    )


def get_customer_by_pan(db: Session, pan_card: str) -> Customer | None:
    return (
        db.query(Customer)
        .filter(
            Customer.pan_card == pan_card,
        )
        .first()
    )


def list_customers(
    db: Session,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
) -> list[Customer] | int:
    query = db.query(Customer).filter(Customer.is_active == True)

    if search:
        query = query.filter(
            (Customer.customer_name.ilike(f"%{search}%"))
            | (Customer.customer_code.ilike(f"%{search}%"))
            | (Customer.mobile.ilike(f"%{search}%"))
        )

    if count_only:
        return query.count()

    return (
        query.order_by(Customer.customer_name.asc(), Customer.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_customer(db: Session, data: dict) -> Customer:
    customer = Customer(**data)
    db.add(customer)
    db.flush()
    return customer


def update_customer(db: Session, customer: Customer, data: dict) -> Customer:
    for field_name, field_value in data.items():
        setattr(customer, field_name, field_value)
    db.flush()
    return customer


def deactivate_customer(db: Session, customer: Customer) -> Customer:
    customer.is_active = False
    db.flush()
    return customer
