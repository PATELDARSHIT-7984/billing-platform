from typing import Optional
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from api.utils.account_balance import signed_balance, balance_after_delta
from sqlalchemy.orm import Session

from api.repository import customer as customer_repo
from api.validation import customer as customer_validation


# ============================================================================
# HELPER & CODE GENERATION FUNCTIONS
# ============================================================================

def _generate_customer_code(db: Session) -> str:
    """Generates the next sequential customer identifier code."""
    dialect_name = customer_repo.get_database_dialect_name(db)

    if dialect_name == "postgresql":
        sequence_val = customer_repo.get_next_customer_code_sequence_value(db)
        return f"CUS-{int(sequence_val):04d}"

    highest_id = customer_repo.get_max_customer_id(db)
    return f"CUS-{int(highest_id) + 1:04d}"


def _normalize_and_extract_pan(gstin: str | None, pan_card: str | None) -> tuple[str | None, str | None]:
    """Cleans GSTIN and PAN strings and derives PAN from GSTIN if missing."""
    clean_gstin = gstin.strip().upper() if gstin else None
    clean_pan = pan_card.strip().upper() if pan_card else None

    if clean_gstin and not clean_pan and len(clean_gstin) == 15:
        clean_pan = clean_gstin[2:12]

    return clean_gstin, clean_pan


# ============================================================================
# SERVICE CRUD FUNCTIONS
# ============================================================================

def create_customer(db: Session, customer_data):
    gstin, pan_card = _normalize_and_extract_pan(
        customer_data.gstin, customer_data.pan_card
    )

    # Validate uniqueness constraints
    if gstin:
        customer_validation.validate_gstin_is_unique(db, gstin=gstin)

    if pan_card:
        customer_validation.validate_pan_is_unique(db, pan_card=pan_card)

    customer_code = _generate_customer_code(db)

    customer_payload = {
        "opening_balance": customer_data.opening_balance,
        "balance_type": customer_data.balance_type,
        "current_balance": customer_data.opening_balance,
        "current_balance_type": customer_data.balance_type if customer_data.opening_balance else "Credit",
        "customer_code": customer_code,
        "customer_name": customer_data.customer_name.strip(),
        "mobile": customer_data.mobile,
        "email": customer_data.email,
        "address": customer_data.address.strip() if customer_data.address else "",
        "city": customer_data.city.strip() if customer_data.city else "",
        "state": customer_data.state.strip() if customer_data.state else "",
        "pincode": customer_data.pincode,
        "gstin": gstin,
        "pan_card": pan_card,
        "state_code": customer_data.state_code,
        "remarks": customer_data.remarks,
        "is_active": True,
    }

    new_customer = customer_repo.create_customer(db, data=customer_payload)
    db.commit()
    db.refresh(new_customer)
    return new_customer


def get_all_customers(
    db: Session,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    count_only: bool = False,
):
    return customer_repo.list_customers(db, search=search, skip=skip, limit=limit, count_only=count_only)


def get_customer_by_id(db: Session, customer_id: int):
    return customer_validation.validate_and_get_active_customer(db, customer_id=customer_id)


def update_customer(db: Session, customer_id: int, customer_data):
    customer = customer_repo.get_customer_for_balance_update(db, customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(404, "Customer not found")

    gstin, pan_card = _normalize_and_extract_pan(
        customer_data.gstin, customer_data.pan_card
    )

    customer_validation.validate_gstin_is_unique(db, gstin=gstin, exclude_id=customer_id)
    customer_validation.validate_pan_is_unique(db, pan_card=pan_card, exclude_id=customer_id)

    update_payload = {
        "customer_name": customer_data.customer_name.strip() if customer_data.customer_name else customer.customer_name,
        "mobile": customer_data.mobile,
        "email": customer_data.email,
        "address": customer_data.address.strip(),
        "city": customer_data.city.strip(),
        "state": customer_data.state.strip(),
        "pincode": customer_data.pincode,
        "gstin": gstin,
        "pan_card": pan_card,
        "state_code": customer_data.state_code,
        "remarks": customer_data.remarks,
    }

    # Old clients omit these newly introduced fields: keep the booked opening.
    balance_edits = customer_data.model_dump(include={"opening_balance", "balance_type"}, exclude_unset=True)
    new_opening = balance_edits.get("opening_balance", customer.opening_balance)
    new_type = balance_edits.get("balance_type", customer.balance_type)
    if (new_opening, new_type) != (customer.opening_balance, customer.balance_type):
        delta = signed_balance(new_opening, new_type) - signed_balance(customer.opening_balance, customer.balance_type)
        amount, direction = balance_after_delta(customer.current_balance, customer.current_balance_type, delta)
        update_payload.update(current_balance=amount, current_balance_type=direction)
    update_payload.update(balance_edits)

    if customer_data.is_active is not None:
        update_payload["is_active"] = customer_data.is_active

    updated_customer = customer_repo.update_customer(db, customer=customer, data=update_payload)
    db.commit()
    db.refresh(updated_customer)
    return updated_customer


def delete_customer(db: Session, customer_id: int):
    customer = customer_validation.validate_and_get_active_customer(db, customer_id=customer_id)

    customer_repo.deactivate_customer(db, customer=customer)
    db.commit()

    return {"message": f"Customer '{customer.customer_name}' deleted successfully"}


def apply_customer_balance_delta(db, customer_id, delta):
    """Caller owns commit/rollback; historical reversals allow inactive Customers."""
    customer = customer_repo.get_customer_for_balance_update(db, customer_id)
    if customer is None:
        raise HTTPException(404, "Customer not found")
    amount, direction = balance_after_delta(customer.current_balance, customer.current_balance_type, delta)
    return customer_repo.update_customer(db, customer, {
        "current_balance": amount, "current_balance_type": direction,
    })


def replace_customer_effect(db, old_id=None, old_effect=0, new_id=None, new_effect=0):
    """Replace one document's signed effect, including account reassignment."""
    changes = {}
    for customer_id, effect, sign in ((old_id, old_effect, -1), (new_id, new_effect, 1)):
        if customer_id is not None:
            # Match NUMERIC(18,2) conversion used by the PostgreSQL cutover.
            booked = Decimal(str(effect)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            changes[customer_id] = changes.get(customer_id, Decimal(0)) + sign * booked
    # Every multi-account posting acquires Customer locks in ascending ID order.
    for customer_id, delta in sorted(changes.items()):
        if delta:
            apply_customer_balance_delta(db, customer_id, delta)
