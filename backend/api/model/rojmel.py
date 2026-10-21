from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, Enum, Text, CheckConstraint
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
    account_ledger_id = Column(Integer, nullable=True, index=True)
    account_role = Column(String(20), nullable=True)
    __table_args__ = (
        CheckConstraint("party_id IS NULL OR customer_id IS NULL", name="ck_rojmel_one_account"),
        ForeignKeyConstraint(['account_ledger_id', 'account_role'], ['account_ledgers.id', 'account_ledgers.role'],
                             name='fk_rojmel_account_ledger_role', match='FULL', ondelete='RESTRICT', onupdate='RESTRICT'),
        CheckConstraint("account_role IS NULL OR account_role IN ('CUSTOMER', 'SUPPLIER', 'PURCHASE_VENDOR')",
                        name='ck_rojmel_account_role'),
        CheckConstraint('(account_ledger_id IS NULL) = (account_role IS NULL)',
                        name='ck_rojmel_account_reference_pair'),
        CheckConstraint("account_ledger_id IS NULL OR "
                        "(customer_id IS NOT NULL AND party_id IS NULL AND account_role = 'CUSTOMER') OR "
                        "(party_id IS NOT NULL AND customer_id IS NULL AND account_role IN ('SUPPLIER','PURCHASE_VENDOR'))",
                        name='ck_rojmel_account_context'),
    )

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
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
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
