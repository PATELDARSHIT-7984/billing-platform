from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from api.dependencies.dependencies import get_db
from api.schema.company_profile import CompanyProfileUpdate, CompanyProfileResponse
from api.services import company_profile as company_profile_service

# NOTE: prefix is singular ("/company-profile") to match the frontend's
# companyService.js, and matches how the UI actually uses this resource --
# as one settings singleton, not a list of profiles to choose between.
router = APIRouter(prefix="/company-profile", tags=["Company Profile"])


@router.get("/", response_model=CompanyProfileResponse)
def get_company_profile(db: Session = Depends(get_db)):
    """Returns the single company profile, creating a blank default one on first run."""
    return company_profile_service.get_or_create_singleton_profile(db)


@router.put("/", response_model=CompanyProfileResponse)
def update_company_profile(profile_in: CompanyProfileUpdate, db: Session = Depends(get_db)):
    return company_profile_service.update_singleton_profile(db, profile_in)


@router.get("/all", response_model=List[CompanyProfileResponse])
def get_all_company_profiles(db: Session = Depends(get_db)):
    """Kept for admin/debugging use -- the UI itself only ever uses the singleton above."""
    return company_profile_service.get_all_company_profiles(db)


@router.get("/{profile_id}", response_model=CompanyProfileResponse)
def get_company_profile_by_id(profile_id: int, db: Session = Depends(get_db)):
    return company_profile_service.get_company_profile(db, profile_id)


@router.delete("/{profile_id}")
def delete_company_profile(profile_id: int, db: Session = Depends(get_db)):
    return company_profile_service.delete_company_profile(db, profile_id)
