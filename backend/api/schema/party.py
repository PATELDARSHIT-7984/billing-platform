from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PartyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    party_type: str = Field(default="Supplier", pattern="^(Supplier|Customer)$")

    country_code: Optional[str] = "+91"
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    gstin: Optional[str] = None
    pan_card: Optional[str] = None

    opening_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
    )
    balance_type: str = Field(
        default="Credit",
        pattern="^(Credit|Debit)$",
    )
    opening_remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 characters")
        return value

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value):
        if value:
            value = value.strip().upper()
            if len(value) != 15:
                raise ValueError("GSTIN must be exactly 15 characters")
        return value or None

    @field_validator("pan_card")
    @classmethod
    def validate_pan(cls, value):
        if value:
            value = value.strip().upper()
            if len(value) != 10:
                raise ValueError("PAN must be exactly 10 characters")
        return value or None


class PartyUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=200,
    )
    party_type: Optional[str] = Field(
        default=None,
        pattern="^(Supplier|Customer)$",
    )

    country_code: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    gstin: Optional[str] = None
    pan_card: Optional[str] = None

    opening_balance: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )
    balance_type: Optional[str] = Field(
        default=None,
        pattern="^(Credit|Debit)$",
    )
    opening_remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if value is None:
            return value

        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 characters")
        return value

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value):
        if value:
            value = value.strip().upper()
            if len(value) != 15:
                raise ValueError("GSTIN must be exactly 15 characters")
        return value or None

    @field_validator("pan_card")
    @classmethod
    def validate_pan(cls, value):
        if value:
            value = value.strip().upper()
            if len(value) != 10:
                raise ValueError("PAN must be exactly 10 characters")
        return value or None


class PartyResponse(BaseModel):
    id: int
    name: str
    party_code: Optional[str] = None
    party_type: str

    country_code: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    gstin: Optional[str] = None
    pan_card: Optional[str] = None

    opening_balance: Decimal
    balance_type: str
    opening_remark: Optional[str] = None

    current_balance: Decimal
    current_balance_type: str

    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True