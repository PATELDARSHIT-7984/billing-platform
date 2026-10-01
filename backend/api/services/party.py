from decimal import Decimal
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.model.party import Party
from api.repository import party as party_repo
from api.schema.party import PartyCreate, PartyUpdate
from api.validation import party as party_validation


# ============================================================================
# HELPER & NORMALIZATION FUNCTIONS
# ============================================================================

def _generate_party_code(db: Session) -> str:
    """Generates the next sequential party identifier code."""
    dialect_name = party_repo.get_database_dialect_name(db)

    if dialect_name == "postgresql":
        sequence_val = party_repo.get_next_party_code_sequence_value(db)
        return f"PTY-{int(sequence_val):04d}"

    highest_id = party_repo.get_max_party_id(db)
    return f"PTY-{int(highest_id) + 1:04d}"


def _clean_text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalize_gstin(value) -> str | None:
    return value.strip().upper() if value else None


def _normalize_pan(value) -> str | None:
    return value.strip().upper() if value else None


def _pan_from_gstin(gstin: str | None) -> str | None:
    clean_gstin = _normalize_gstin(gstin)
    return clean_gstin[2:12] if clean_gstin and len(clean_gstin) >= 12 else None


# ============================================================================
# SERVICE CRUD FUNCTIONS
# ============================================================================

def apply_party_balance_delta(
    db: Session,
    party_id: int,
    amount_delta: Decimal | int | float,
) -> Party:
    """Apply a signed payable delta; the caller owns commit and rollback."""
    party = party_repo.get_party_by_id_any_status(db, party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    signed_balance = Decimal(str(party.current_balance))
    if party.current_balance_type == "Debit":
        signed_balance = -signed_balance

    new_balance = signed_balance + Decimal(str(amount_delta))
    return party_repo.set_party_current_balance(
        db,
        party,
        abs(new_balance),
        "Debit" if new_balance < 0 else "Credit",
    )


def create_party(db: Session, data: PartyCreate) -> Party:
    gstin = _normalize_gstin(data.gstin)
    pan_card = _normalize_pan(data.pan_card)

    if gstin and not pan_card:
        pan_card = _pan_from_gstin(gstin)

    if gstin:
        party_validation.validate_gstin_is_unique(db, gstin=gstin)

    party_code = _generate_party_code(db)

    party_payload = {
        "name": data.name.strip() if data.name else None,
        "party_code": party_code,
        "party_type": data.party_type,
        "country_code": data.country_code or "+91",
        "mobile": _clean_text(data.mobile),
        "address": _clean_text(data.address),
        "city": _clean_text(data.city),
        "state": _clean_text(data.state),
        "gstin": gstin,
        "pan_card": pan_card,
        "opening_balance": data.opening_balance,
        "balance_type": data.balance_type,
        "current_balance": data.opening_balance,
        "current_balance_type": data.balance_type if data.opening_balance else "Credit",
        "opening_remark": _clean_text(data.opening_remark),
        "is_active": True,
    }

    new_party = party_repo.create_party(db, data=party_payload)
    db.commit()
    db.refresh(new_party)
    return new_party


def get_parties(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
) -> list[Party]:
    return party_repo.list_parties(db, skip=skip, limit=limit, search=search)


def get_party_by_id(db: Session, party_id: int) -> Party:
    return party_validation.validate_and_get_active_party(db, party_id=party_id)


def update_party_by_id(
    db: Session, party_id: int, party_data: PartyUpdate
) -> Party:
    party = party_validation.validate_and_get_active_party(db, party_id=party_id)
    update_data = party_data.model_dump(exclude_unset=True)

    if "gstin" in update_data:
        update_data["gstin"] = _normalize_gstin(update_data.get("gstin"))
        if update_data["gstin"]:
            party_validation.validate_gstin_is_unique(
                db, gstin=update_data["gstin"], exclude_id=party_id
            )

    if "pan_card" in update_data:
        update_data["pan_card"] = _normalize_pan(update_data.get("pan_card"))
    elif "gstin" in update_data and update_data.get("gstin"):
        update_data["pan_card"] = _pan_from_gstin(update_data["gstin"])

    for text_field in ["mobile", "address", "city", "state", "opening_remark"]:
        if text_field in update_data:
            update_data[text_field] = _clean_text(update_data[text_field])

    if "country_code" in update_data and not update_data["country_code"]:
        update_data["country_code"] = "+91"

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    new_opening = update_data.get("opening_balance", party.opening_balance)
    new_type = update_data.get("balance_type", party.balance_type)
    if new_opening is None or new_type is None:
        raise HTTPException(status_code=422, detail="Opening balance and balance type cannot be null")
    if (new_opening, new_type) != (party.opening_balance, party.balance_type):
        old_signed = party.opening_balance if party.balance_type == "Credit" else -party.opening_balance
        new_signed = new_opening if new_type == "Credit" else -new_opening
        apply_party_balance_delta(db, party_id, new_signed - old_signed)

    updated_party = party_repo.update_party(db, party=party, data=update_data)
    db.commit()
    db.refresh(updated_party)
    return updated_party


def delete_party_by_id(db: Session, party_id: int):
    party = party_validation.validate_and_get_active_party(db, party_id=party_id)

    party_repo.deactivate_party(db, party=party)
    db.commit()

    return {"message": f"Party '{party.name}' deleted successfully."}
