from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemMasterCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    code: Optional[str] = Field(default=None, max_length=100)
    hsn_code: str = Field(..., min_length=1, max_length=50)

    unit: str = Field(..., min_length=1, max_length=50)

    current_stock: float = Field(default=0.0, ge=0)

    purchase_price: float = Field(default=0.0, ge=0)
    sale_price: float = Field(default=0.0, ge=0)
    mrp: float = Field(default=0.0, ge=0)

    cgst: float = Field(default=9.0, ge=0, le=100)
    sgst: float = Field(default=9.0, ge=0, le=100)

    category: Optional[str] = Field(default=None, max_length=150)
    brand: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None

    last_purchase_date: Optional[date] = None
    last_sale_date: Optional[date] = None

    @field_validator(
        "name",
        "code",
        "hsn_code",
        "unit",
        "category",
        "brand",
        "description",
        mode="before"
    )
    @classmethod
    def clean_text_fields(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None

        return value

    @field_validator("name", "hsn_code", "unit")
    @classmethod
    def validate_required_text(cls, value):
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        if value:
            return value.upper()
        return value

    @field_validator("hsn_code")
    @classmethod
    def normalize_hsn(cls, value):
        return value.upper()


class ItemMasterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    code: Optional[str] = Field(default=None, max_length=100)
    hsn_code: Optional[str] = Field(default=None, min_length=1, max_length=50)

    unit: Optional[str] = Field(default=None, min_length=1, max_length=50)

    purchase_price: Optional[float] = Field(default=None, ge=0)
    sale_price: Optional[float] = Field(default=None, ge=0)
    mrp: Optional[float] = Field(default=None, ge=0)

    cgst: Optional[float] = Field(default=None, ge=0, le=100)
    sgst: Optional[float] = Field(default=None, ge=0, le=100)

    category: Optional[str] = Field(default=None, max_length=150)
    brand: Optional[str] = Field(default=None, max_length=150)
    description: Optional[str] = None

    last_purchase_date: Optional[date] = None
    last_sale_date: Optional[date] = None

    is_active: Optional[bool] = None

    @field_validator(
        "name",
        "code",
        "hsn_code",
        "unit",
        "category",
        "brand",
        "description",
        mode="before"
    )
    @classmethod
    def clean_text_fields(cls, value):
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return None

        return value

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value):
        if value:
            return value.upper()
        return value

    @field_validator("hsn_code")
    @classmethod
    def normalize_hsn(cls, value):
        if value:
            return value.upper()
        return value


class ItemMasterResponse(BaseModel):
    id: int

    name: str
    code: Optional[str] = None
    hsn_code: str

    unit: str
    current_stock: float

    purchase_price: float
    sale_price: float
    mrp: float

    cgst: float
    sgst: float

    category: Optional[str] = None
    brand: Optional[str] = None
    description: Optional[str] = None

    last_purchase_date: Optional[date] = None
    last_sale_date: Optional[date] = None

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)