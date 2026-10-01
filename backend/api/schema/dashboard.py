from datetime import date
from decimal import Decimal
from pydantic import BaseModel


class Summary(BaseModel):
    start_date: date
    end_date: date
    balances_as_of: str
    total_sales: Decimal
    total_purchase: Decimal
    total_sales_return: Decimal
    total_purchase_return: Decimal
    net_sales: Decimal
    net_purchase: Decimal
    supplier_payable: Decimal
    supplier_advance: Decimal
    total_received: Decimal
    total_paid: Decimal
    net_cash_flow: Decimal
    customer_receivable: Decimal | None
    sales_return_rate: Decimal
    purchase_return_rate: Decimal


class Account(BaseModel):
    id: int
    name: str
    mobile: str | None
    address: str | None
    gstin: str | None
    is_active: bool
    current_balance: Decimal | None
    balance_type: str | None


class AccountPage(BaseModel):
    items: list[Account]
    total: int
    limit: int
    skip: int


class Partner(BaseModel):
    id: int
    name: str
    net_amount: Decimal
    rank: int


class PartnerPage(BaseModel):
    items: list[Partner]
    total: int
    limit: int
    skip: int


class Trend(BaseModel):
    start_date: date
    end_date: date
    labels: list[str]
    sales: list[Decimal]
    purchase: list[Decimal]


class Transaction(BaseModel):
    id: int
    number: str
    date: date
    name: str | None
    amount: Decimal
    type: str
