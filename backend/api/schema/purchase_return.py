from datetime import date, datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PurchaseReturnItemCreate(BaseModel):
    item_id: Optional[int] = Field(default=None, gt=0)
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
    def clean_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required")
        return cleaned

    @model_validator(mode="after")
    def validate_tax_mode(self):
        if self.igst > 0 and (self.sgst > 0 or self.cgst > 0):
            raise ValueError(
                "IGST cannot be used together with SGST or CGST"
            )
        return self


class PurchaseReturnCreate(BaseModel):
    return_no: Optional[str] = Field(default=None, max_length=100)
    order_no: Optional[str] = Field(default=None, max_length=100)
    original_bill_no: Optional[str] = Field(default=None, max_length=100)
    return_date: date = Field(default_factory=date.today)
    due_term: Optional[int] = Field(default=None, ge=0, le=3650)
    due_date: Optional[date] = None
    party_id: int = Field(..., gt=0)
    is_gst: bool = True
    address: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=150)
    party_state: Optional[str] = Field(default=None, max_length=100)
    contact_no: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    done_by: Optional[str] = Field(default=None, min_length=1, max_length=100)
    brokerage: float = Field(default=0.0, ge=0)
    broker_remarks: Optional[str] = Field(default=None, max_length=500)
    return_reason: str = Field(..., min_length=2, max_length=500)
    items: List[PurchaseReturnItemCreate] = Field(..., min_length=1)
    delivery_date: Optional[date] = None
    transport: Optional[str] = Field(default=None, max_length=200)
    ship_to: Optional[str] = Field(default=None, max_length=200)
    ship_to_address: Optional[str] = None
    state: Optional[str] = Field(default=None, max_length=100)
    reference: Optional[str] = Field(default=None, max_length=200)
    remarks: Optional[str] = None
    show_shipping_address_on_bill: bool = False

    @model_validator(mode="after")
    def calculate_due_date(self):
        if self.due_term is not None:
            self.due_date = self.return_date + timedelta(days=self.due_term)
        return self


class PurchaseReturnUpdate(BaseModel):
    return_no: Optional[str] = Field(default=None, max_length=100)
    order_no: Optional[str] = Field(default=None, max_length=100)
    original_bill_no: Optional[str] = Field(default=None, max_length=100)
    return_date: Optional[date] = None
    due_term: Optional[int] = Field(default=None, ge=0, le=3650)
    due_date: Optional[date] = None
    party_id: Optional[int] = Field(default=None, gt=0)
    is_gst: Optional[bool] = None
    address: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=150)
    party_state: Optional[str] = Field(default=None, max_length=100)
    contact_no: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    done_by: Optional[str] = Field(default=None, min_length=1, max_length=100)
    brokerage: Optional[float] = Field(default=None, ge=0)
    broker_remarks: Optional[str] = Field(default=None, max_length=500)
    return_reason: Optional[str] = Field(default=None, min_length=2, max_length=500)
    items: Optional[List[PurchaseReturnItemCreate]] = Field(default=None, min_length=1)
    delivery_date: Optional[date] = None
    transport: Optional[str] = Field(default=None, max_length=200)
    ship_to: Optional[str] = Field(default=None, max_length=200)
    ship_to_address: Optional[str] = None
    state: Optional[str] = Field(default=None, max_length=100)
    reference: Optional[str] = Field(default=None, max_length=200)
    remarks: Optional[str] = None
    show_shipping_address_on_bill: Optional[bool] = None
    is_active: Optional[bool] = None


class PurchaseReturnItemResponse(BaseModel):
    id: int
    item_id: Optional[int] = None
    item_name: str
    hsn_code: str
    quantity: float
    unit: str
    price: float
    disc_percent: float
    sgst: float
    cgst: float
    igst: float
    amount: float
    current_stock: float = 0.0
    available_stock: float = 0.0

    class Config:
        from_attributes = True


class PurchaseReturnResponse(BaseModel):
    id: int
    return_no: str
    order_no: Optional[str] = None
    original_bill_no: Optional[str] = None
    return_date: date
    due_term: Optional[int] = None
    due_date: Optional[date] = None
    party_id: int
    party_name: Optional[str] = None
    is_gst: bool
    address: Optional[str] = None
    city: Optional[str] = None
    party_state: Optional[str] = None
    contact_no: Optional[str] = None
    email: Optional[str] = None
    done_by: Optional[str] = None
    brokerage: float = 0.0
    broker_remarks: Optional[str] = None
    return_reason: str
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
    updated_at: datetime
    items: List[PurchaseReturnItemResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PurchaseReturnListResponse(BaseModel):
    id: int
    return_no: str
    original_bill_no: Optional[str] = None
    return_date: date
    party_id: int
    party_name: Optional[str] = None
    item_count: int = 0
    item_names: List[str] = Field(default_factory=list)
    hsn_codes: List[str] = Field(default_factory=list)
    total_quantity: float = 0.0
    return_reason: str
    grand_total: float = 0.0
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
