from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, Enum, Text
from api.config.database import Base
import enum


class TransactionType(str, enum.Enum):
    CR_PAY = "Cr Pay"
    DR_PAY = "Dr Pay"
    CASH_BANK = "Cash/Bank"
    JV = "JV"


class Rojmel(Base):
    # Daily cash/bank ledger entry (a receipt or payment record).
    __tablename__ = "rojmel"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)

    receipt_no = Column(String(50), unique=True, index=True, nullable=False)
    given_taken_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=False)

    # FK targets match the real table names: Party's table is "parties"
    # (plural) and DoneBy's table is "employees" -- using the wrong
    # literal here doesn't fail at import time, only when the DDL/insert
    # actually hits Postgres, so it's an easy one to miss.
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=True)
    cash_bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    done_by_id = Column(Integer, ForeignKey("doneby.id"), nullable=False)

    pay_mode = Column(String(20), nullable=False)
    cheque_txn_no = Column(String(100), nullable=True)

    amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    sgst_percent = Column(Numeric(5, 2), default=0.00)
    cgst_percent = Column(Numeric(5, 2), default=0.00)
    igst_percent = Column(Numeric(5, 2), default=0.00)
    net_amount = Column(Numeric(10, 2), nullable=False, default=0.00)

    payment_for = Column(String(255), nullable=True)
    remarks = Column(Text, nullable=True)
