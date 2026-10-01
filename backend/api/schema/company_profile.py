from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CompanyProfileUpdate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    gstin: Optional[str] = Field(default=None, max_length=15)
    pan_card: Optional[str] = Field(default=None, max_length=10)
    udyam_no: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    terms_and_conditions: List[str] = Field(default_factory=list)
    jurisdiction_note: Optional[str] = None


class CompanyProfileResponse(CompanyProfileUpdate):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)