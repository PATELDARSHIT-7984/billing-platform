"""
Data-access layer for CompanyProfile records.

Same rules as the other repository modules: no HTTPException,
no commit/rollback, no business rules (GSTIN-derived PAN extraction,
default terms-and-conditions text, etc. stay in the service layer).
"""

from sqlalchemy.orm import Session

from api.model.company_profile import CompanyProfile


def get_company_profile_by_id(db: Session, profile_id: int) -> CompanyProfile | None:
    return db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()


def get_company_profile_by_gstin(
    db: Session,
    gstin: str,
    exclude_id: int | None = None,
) -> CompanyProfile | None:
    query = db.query(CompanyProfile).filter(CompanyProfile.gstin == gstin)

    if exclude_id is not None:
        query = query.filter(CompanyProfile.id != exclude_id)

    return query.first()


def list_company_profiles(db: Session) -> list[CompanyProfile]:
    return db.query(CompanyProfile).order_by(CompanyProfile.id.asc()).all()


def create_company_profile(db: Session, data: dict) -> CompanyProfile:
    profile = CompanyProfile(**data)
    db.add(profile)
    db.flush()
    return profile


def update_company_profile(
    db: Session,
    profile: CompanyProfile,
    data: dict,
) -> CompanyProfile:
    for field_name, field_value in data.items():
        setattr(profile, field_name, field_value)
    db.flush()
    return profile


def delete_company_profile(db: Session, profile: CompanyProfile) -> None:
    db.delete(profile)
    db.flush()
