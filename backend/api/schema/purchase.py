from datetime import date, datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


class PurchaseItemCreate(BaseModel):
    item_id: int | None = Field(default=None, gt=0)
    item_name: str = Field(..., min_length=1, max_length=255)
    hsn_code: str = Field(..., min_length=1, max_length=50)
    quantity: float = Field(..., gt=0, allow_inf_nan=False)
    unit: str = Field(..., min_length=1, max_length=50)
    price: float = Field(..., ge=0)
    disc_percent: float = Field(default=0.0, ge=0, le=100)
    sgst: float = Field(default=0.0, ge=0, le=100)
    cgst: float = Field(default=0.0, ge=0, le=100)
    igst: float = Field(default=0.0, ge=0, le=100)

    @field_validator("item_name", "hsn_code", "unit")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_tax_mode(self):
        if self.igst > 0 and (self.cgst > 0 or self.sgst > 0):
            raise ValueError("IGST cannot be used together with CGST or SGST")
        return self


class PurchaseCreate(BaseModel):
    bill_no: str = Field(..., min_length=1, max_length=100)
    order_no: Optional[str] = Field(default=None, max_length=100)
    bill_date: date = Field(default_factory=date.today)
    due_term: Optional[int] = Field(default=None, ge=0, le=3650)
    due_date: Optional[date] = None
    party_id: int = Field(..., gt=0)
    is_gst: bool = True
    contact_person: Optional[str] = Field(default=None, max_length=150)
    contact_no: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    done_by: Optional[str] = Field(default=None, min_length=1, max_length=100)
    brokerage: float = Field(default=0.0, ge=0)
    broker_remarks: Optional[str] = Field(default=None, max_length=500)
    items: List[PurchaseItemCreate] = Field(..., min_length=1)
    delivery_date: Optional[date] = None
    transport: Optional[str] = Field(default=None, max_length=200)
    ship_to: Optional[str] = Field(default=None, max_length=200)
    ship_to_address: Optional[str] = Field(default=None, max_length=1000)
    state: Optional[str] = Field(default=None, max_length=100)
    reference: Optional[str] = Field(default=None, max_length=200)
    remarks: Optional[str] = Field(default=None, max_length=1000)
    show_shipping_address_on_bill: bool = False

    @field_validator("bill_no")
    @classmethod
    def normalize_bill_no(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("Bill number is required")
        return value

    @field_validator(
        "order_no", "contact_person", "contact_no", "email", "broker_remarks",
        "transport", "ship_to", "ship_to_address", "state", "reference", "remarks"
    )
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)

    @model_validator(mode="after")
    def set_due_date(self):
        if self.due_term is not None:
            self.due_date = self.bill_date + timedelta(days=self.due_term)
        return self

    @model_validator(mode="after")
    def validate_shipping(self):
        if self.show_shipping_address_on_bill:
            if not self.ship_to:
                raise ValueError("Ship To is required when shipping address is shown on the bill")
            if not self.ship_to_address:
                raise ValueError("Ship To Address is required when shipping address is shown on the bill")
            if not self.state:
                raise ValueError("State is required when shipping address is shown on the bill")
        return self


class PurchaseUpdate(BaseModel):
    bill_no: Optional[str] = Field(default=None, min_length=1, max_length=100)
    order_no: Optional[str] = Field(default=None, max_length=100)
    bill_date: Optional[date] = None
    due_term: Optional[int] = Field(default=None, ge=0, le=3650)
    due_date: Optional[date] = None
    party_id: Optional[int] = Field(default=None, gt=0)
    is_gst: Optional[bool] = None
    contact_person: Optional[str] = Field(default=None, max_length=150)
    contact_no: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    done_by: Optional[str] = Field(default=None, min_length=1, max_length=100)
    brokerage: Optional[float] = Field(default=None, ge=0)
    broker_remarks: Optional[str] = Field(default=None, max_length=500)
    items: Optional[List[PurchaseItemCreate]] = Field(default=None, min_length=1)
    delivery_date: Optional[date] = None
    transport: Optional[str] = Field(default=None, max_length=200)
    ship_to: Optional[str] = Field(default=None, max_length=200)
    ship_to_address: Optional[str] = Field(default=None, max_length=1000)
    state: Optional[str] = Field(default=None, max_length=100)
    reference: Optional[str] = Field(default=None, max_length=200)
    remarks: Optional[str] = Field(default=None, max_length=1000)
    show_shipping_address_on_bill: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("bill_no")
    @classmethod
    def normalize_bill_no(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip().upper()
        if not value:
            raise ValueError("Bill number cannot be empty")
        return value

    @field_validator(
        "order_no", "contact_person", "contact_no", "email", "broker_remarks",
        "transport", "ship_to", "ship_to_address", "state", "reference", "remarks"
    )
    @classmethod
    def clean_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _clean(value)


class PurchaseItemResponse(BaseModel):
    id: int
    item_id: Optional[int] = None
    item_name: str
    hsn_code: str
    quantity: float
    unit: str
    price: float
    disc_percent: float = 0.0
    sgst: float = 0.0
    cgst: float = 0.0
    igst: float = 0.0
    amount: float

    model_config = ConfigDict(from_attributes=True)


class PurchaseResponse(BaseModel):
    id: int
    bill_no: str
    order_no: Optional[str] = None
    bill_date: date
    due_term: Optional[int] = None
    due_date: Optional[date] = None
    party_id: int
    party_name: Optional[str] = None
    is_gst: bool = True
    contact_person: Optional[str] = None
    contact_no: Optional[str] = None
    email: Optional[str] = None
    done_by: Optional[str] = None
    brokerage: float = 0.0
    broker_remarks: Optional[str] = None
    taxable_amount: float = 0.0
    sgst_total: float = 0.0
    cgst_total: float = 0.0
    igst_total: float = 0.0
    round_off: float = 0.0
    grand_total: float = 0.0
    delivery_date: Optional[date] = None
    transport: Optional[str] = None
    ship_to: Optional[str] = None
    ship_to_address: Optional[str] = None
    state: Optional[str] = None
    reference: Optional[str] = None
    remarks: Optional[str] = None
    show_shipping_address_on_bill: bool = False
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[int] = None
    items: List[PurchaseItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PurchaseListResponse(BaseModel):
    id: int
    bill_no: str
    order_no: Optional[str] = None
    bill_date: date
    due_date: Optional[date] = None
    party_id: int
    party_name: Optional[str] = None
    item_count: int = 0
    item_names: List[str] = Field(default_factory=list)
    hsn_codes: List[str] = Field(default_factory=list)
    purchase_prices: List[float] = Field(default_factory=list)
    taxable_amount: float = 0.0
    grand_total: float = 0.0
    done_by: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
