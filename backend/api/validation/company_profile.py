"""
Business-rule validation layer for CompanyProfile records.

Same conventions as validation/bank.py. GSTIN->PAN extraction and the
default terms-and-conditions text are data transformations, not
validation, so they stay in the service layer -- this module only
enforces the GSTIN-uniqueness rule and the "does this profile exist"
check.
"""

from fastapi import HTTPException, status

from api.repository import company_profile as company_profile_repository


def validate_gstin_is_unique(db, gstin: str, exclude_id: int | None = None) -> None:
    if not gstin:
        return

    duplicate = company_profile_repository.get_company_profile_by_gstin(
        db, gstin, exclude_id=exclude_id
    )
    if duplicate:
        detail = (
            "Another company with this GSTIN already exists."
            if exclude_id is not None
            else "A company with this GSTIN already exists."
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def validate_and_get_company_profile(db, profile_id: int):
    profile = company_profile_repository.get_company_profile_by_id(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company Profile not found.",
        )
    return profile
