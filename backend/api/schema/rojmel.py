from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import date
from decimal import Decimal
from enum import Enum


class TransactionType(str, Enum):
    CR_PAY = "Cr Pay"
    DR_PAY = "Dr Pay"
    CASH_BANK = "Cash/Bank"
    JV = "JV"


class RojmelBase(BaseModel):
    transaction_type: TransactionType
    receipt_no: str
    given_taken_date: date
    effective_date: date

    party_id: Optional[int] = None
    customer_id: Optional[int] = None

    cash_bank_id: int
    done_by_id: int

    pay_mode: str
    cheque_txn_no: Optional[str] = None

    amount: Decimal = Field(default=Decimal('0.00'), decimal_places=2)
    sgst_percent: Decimal = Field(default=Decimal('0.00'), decimal_places=2)
    cgst_percent: Decimal = Field(default=Decimal('0.00'), decimal_places=2)
    igst_percent: Decimal = Field(default=Decimal('0.00'), decimal_places=2)
    net_amount: Decimal = Field(default=Decimal('0.00'), decimal_places=2)

    payment_for: Optional[str] = None
    remarks: Optional[str] = None


# Payload for creating a new receipt. receipt_no is still required by
# RojmelBase but the service always overwrites it with an auto-generated
# value -- the frontend sends a placeholder.
class RojmelCreate(RojmelBase):
    pass


# Payload for editing a receipt -- every field optional so the caller can
# send only what changed.
class RojmelUpdate(BaseModel):
    transaction_type: Optional[TransactionType] = None
    receipt_no: Optional[str] = None
    given_taken_date: Optional[date] = None
    effective_date: Optional[date] = None
    party_id: Optional[int] = None
    customer_id: Optional[int] = None
    cash_bank_id: Optional[int] = None
    done_by_id: Optional[int] = None
    pay_mode: Optional[str] = None
    cheque_txn_no: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, decimal_places=2)
    sgst_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    cgst_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    igst_percent: Optional[Decimal] = Field(default=None, decimal_places=2)
    net_amount: Optional[Decimal] = Field(default=None, decimal_places=2)
    payment_for: Optional[str] = None
    remarks: Optional[str] = None


class RojmelResponse(RojmelBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Shape returned by the paginated list endpoint: the current page of rows
# plus enough metadata for the frontend to render pagination controls.
class RojmelPage(BaseModel):
    items: List[RojmelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Shape returned by the summary endpoint -- gives the owner an at-a-glance
# view of money in vs. money out across every matching receipt.
class RojmelSummary(BaseModel):
    total_received: Decimal
    total_paid: Decimal
    total_cash_bank: Decimal
    total_jv: Decimal
    net_earning: Decimal
