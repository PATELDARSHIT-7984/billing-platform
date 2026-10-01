from datetime import date, datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from api.schema.bill_item import (
    BillItemCreate,
    BillItemResponse,
)


class BillCreate(BaseModel):
    is_gst: bool = True
    customer_id: int = Field(..., gt=0)

    bill_date: date

    due_term: Optional[int] = Field(
        default=None,
        ge=0,
    )

    due_date: Optional[date] = None

    is_interstate: bool = False

    done_by: Optional[str] = Field(
        default=None,
        min_length=1, max_length=100,
    )

    brokerage: float = Field(
        default=0.0,
        ge=0,
    )

    broker_remarks: Optional[str] = None

    delivery_date: Optional[date] = None

    ship_to: Optional[str] = None

    ship_to_address: Optional[str] = None

    shipping_state: Optional[str] = None

    transport: Optional[str] = None

    reference: Optional[str] = None

    remarks: Optional[str] = None

    show_shipping_address_on_bill: bool = False

    items: List[BillItemCreate] = Field(
        ...,
        min_length=1,
    )

    @model_validator(mode="after")
    def calculate_due_date(self):
        if self.due_term is not None:
            self.due_date = (
                self.bill_date
                + timedelta(days=self.due_term)
            )

        return self


class BillUpdate(BaseModel):
    # None preserves the saved tax rates for legacy update payloads.
    is_gst: Optional[bool] = None
    customer_id: int = Field(..., gt=0)

    bill_date: date

    due_term: Optional[int] = Field(
        default=None,
        ge=0,
    )

    due_date: Optional[date] = None

    is_interstate: bool = False

    done_by: Optional[str] = Field(
        default=None,
        min_length=1, max_length=100,
    )

    brokerage: float = Field(
        default=0.0,
        ge=0,
    )

    broker_remarks: Optional[str] = None

    delivery_date: Optional[date] = None

    ship_to: Optional[str] = None

    ship_to_address: Optional[str] = None

    shipping_state: Optional[str] = None

    transport: Optional[str] = None

    reference: Optional[str] = None

    remarks: Optional[str] = None

    show_shipping_address_on_bill: bool = False

    items: List[BillItemCreate] = Field(
        ...,
        min_length=1,
    )

    @model_validator(mode="after")
    def calculate_due_date(self):
        if self.due_term is not None:
            self.due_date = (
                self.bill_date
                + timedelta(days=self.due_term)
            )

        return self


class BillListResponse(BaseModel):
    bill_id: int
    invoice_no: str
    customer_id: int
    customer_name: str
    bill_date: date
    total_boxes: int
    grand_total: float

    class Config:
        from_attributes = True


class BillResponse(BaseModel):
    bill_id: int
    invoice_no: str
    customer_id: int
    bill_date: date

    due_term: Optional[int] = None
    due_date: Optional[date] = None

    is_interstate: bool = False

    customer_name: str
    mobile: str
    email: Optional[str] = None
    address: str
    city: str
    state: str
    pincode: Optional[str] = None

    buyer_gstin: Optional[str] = None
    buyer_pan: Optional[str] = None
    buyer_state_code: Optional[str] = None

    done_by: Optional[str] = None
    brokerage: float = 0.0
    broker_remarks: Optional[str] = None

    total_boxes: int
    subtotal: float
    discount_amount: float = 0.0
    taxable_amount: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    grand_total: float
    amount_in_words: str

    delivery_date: Optional[date] = None
    ship_to: Optional[str] = None
    ship_to_address: Optional[str] = None
    shipping_state: Optional[str] = None
    transport: Optional[str] = None
    reference: Optional[str] = None
    remarks: Optional[str] = None

    show_shipping_address_on_bill: bool = False
    is_active: bool = True

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BillDetailResponse(BaseModel):
    bill: BillResponse
    items: List[BillItemResponse]


class BillSearch(BaseModel):
    customer_name: Optional[str] = None
    invoice_no: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
