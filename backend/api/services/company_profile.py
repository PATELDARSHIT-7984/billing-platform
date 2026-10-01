from sqlalchemy.orm import Session

from api.model.company_profile import CompanyProfile
from api.repository import company_profile as company_profile_repo
from api.schema.company_profile import CompanyProfileUpdate
from api.validation import company_profile as company_profile_validation


# ============================================================================
# HELPER & DATA TRANSFORMATION FUNCTIONS
# ============================================================================

def _extract_pan_from_gstin(gstin: str | None) -> str | None:
    """Extracts the 10-character PAN segment from a 15-character GSTIN string."""
    if gstin and len(gstin) == 15:
        return gstin[2:12].upper()
    return None


def _apply_default_company_terms(profile_data: dict) -> dict:
    """Sets standard jurisdiction and MSME invoice terms if not explicitly provided."""
    if not profile_data.get("terms_and_conditions"):
        profile_data["terms_and_conditions"] = [
            "Payments to MSMEs should be made within the applicable statutory period.",
            "Goods once sold will not be taken back or exchanged.",
        ]

    if not profile_data.get("jurisdiction_note"):
        profile_data["jurisdiction_note"] = "Subject to Ahmedabad jurisdiction."

    return profile_data


# ============================================================================
# SERVICE CRUD FUNCTIONS
# ============================================================================

def create_company_profile(db: Session, profile_in) -> CompanyProfile:
    # 1. Validate business rules
    if profile_in.gstin:
        company_profile_validation.validate_gstin_is_unique(db, gstin=profile_in.gstin)

    # 2. Extract PAN if GSTIN is present
    extracted_pan = _extract_pan_from_gstin(profile_in.gstin)
    if extracted_pan:
        profile_in.pan_card = extracted_pan

    # 3. Apply default profile settings and create record
    profile_data = profile_in.model_dump()
    profile_data = _apply_default_company_terms(profile_data)

    new_profile = company_profile_repo.create_company_profile(db, data=profile_data)
    db.commit()
    db.refresh(new_profile)
    return new_profile


def get_company_profile(db: Session, profile_id: int) -> CompanyProfile:
    return company_profile_validation.validate_and_get_company_profile(db, profile_id=profile_id)


def get_all_company_profiles(db: Session) -> list[CompanyProfile]:
    return company_profile_repo.list_company_profiles(db)


def get_or_create_singleton_profile(db: Session) -> CompanyProfile:
    """
    The frontend treats the company profile as a single settings record
    (no id in the URL) rather than a list a user picks from. This backs
    that assumption: return the first profile row if one exists, or
    silently create a blank default one on first run so Company Settings
    always has something to load and PUT to.
    """
    existing_profiles = company_profile_repo.list_company_profiles(db)
    if existing_profiles:
        return existing_profiles[0]

    profile_data = _apply_default_company_terms({"company_name": "Your Company Name"})
    new_profile = company_profile_repo.create_company_profile(db, data=profile_data)
    db.commit()
    db.refresh(new_profile)
    return new_profile


def update_singleton_profile(db: Session, data: CompanyProfileUpdate) -> CompanyProfile:
    """Update-path counterpart to get_or_create_singleton_profile -- resolves
    the one profile row first, then delegates to the normal id-based update."""
    profile = get_or_create_singleton_profile(db)
    return update_company_profile(db, profile.id, data)


def update_company_profile(
    db: Session, profile_id: int, data: CompanyProfileUpdate
) -> CompanyProfile:
    profile = company_profile_validation.validate_and_get_company_profile(db, profile_id=profile_id)

    update_data = data.model_dump(exclude_unset=True)

    # Validate GSTIN uniqueness excluding the current profile ID
    if "gstin" in update_data and update_data["gstin"]:
        company_profile_validation.validate_gstin_is_unique(
            db, gstin=update_data["gstin"], exclude_id=profile_id
        )
        extracted_pan = _extract_pan_from_gstin(update_data["gstin"])
        if extracted_pan:
            update_data["pan_card"] = extracted_pan

    updated_profile = company_profile_repo.update_company_profile(
        db, profile=profile, data=update_data
    )
    db.commit()
    db.refresh(updated_profile)
    return updated_profile


def delete_company_profile(db: Session, profile_id: int):
    profile = company_profile_validation.validate_and_get_company_profile(db, profile_id=profile_id)

    company_profile_repo.delete_company_profile(db, profile=profile)
    db.commit()

    return {"message": f"Company profile '{profile.company_name}' successfully deleted."}