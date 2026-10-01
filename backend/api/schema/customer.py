from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re


class CustomerCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=100)
    mobile: str = Field(...)

    email: Optional[EmailStr] = None

    address: str = Field(..., min_length=2)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)

    pincode: Optional[str] = None

    gstin: Optional[str] = None
    pan_card: Optional[str] = None
    state_code: Optional[str] = None

    remarks: Optional[str] = None

    @field_validator("mobile")
    def validate_mobile(cls, v):
        if not re.fullmatch(r"[6-9]\d{9}", v):
            raise ValueError("Mobile number must contain exactly 10 digits")
        return v

    @field_validator("gstin")
    def validate_gstin(cls, v):
        if v is None:
            return v

        v = v.strip().upper()
        if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}", v.upper()):
            raise ValueError("Invalid GSTIN")

        return v.upper()

    @field_validator('pan_card')
    def validate_pan(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if len(v) != 10:
            raise ValueError('PAN must be exactly 10 characters')
        return v


class CustomerUpdate(CustomerCreate):
    is_active: Optional[bool] = None


class CustomerResponse(BaseModel):
    id: int
    customer_name: str
    customer_code: Optional[str] = None
    mobile: str

    email: Optional[str]
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]

    gstin: Optional[str]
    pan_card: Optional[str]
    state_code: Optional[str]

    remarks: Optional[str]

    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# Customer List (Customer Management table)
# =====================================================
class CustomerListResponse(BaseModel):
    id: int
    customer_name: str
    customer_code: Optional[str] = None
    mobile: str
    city: Optional[str]
    state: Optional[str]
    gstin: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True