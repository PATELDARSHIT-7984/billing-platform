from typing import Optional
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
):
    return customer_repo.list_customers(db, search=search, skip=skip, limit=limit)


def get_customer_by_id(db: Session, customer_id: int):
    return customer_validation.validate_and_get_active_customer(db, customer_id=customer_id)


def update_customer(db: Session, customer_id: int, customer_data):
    customer = customer_validation.validate_and_get_active_customer(db, customer_id=customer_id)

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