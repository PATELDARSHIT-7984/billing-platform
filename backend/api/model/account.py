"""Unified Account, AccountRole, and AccountLedger models with runtime posting."""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Enum, ForeignKey,
    ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint,
    func, true, false,
)
from sqlalchemy.orm import relationship

from api.config.database import Base
from api.schema.account_role import AccountRoleCode
from api.utils.gstin import GSTIN_PATTERN, PAN_PATTERN
from api.utils.gst_state import GST_STATES


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("gstin IS NULL OR NOT gstin_pending", name="ck_accounts_gstin_pending"),
        CheckConstraint("gstin IS NULL OR (state_code IS NOT NULL AND substr(gstin, 1, 2) = state_code)",
                        name="ck_accounts_gstin_state"),
        CheckConstraint("state_code IS NULL OR state_code IN (" +
                        ','.join(repr(code) for code in GST_STATES) + ")", name="ck_accounts_state_code"),
        UniqueConstraint("account_code", name="uq_accounts_code"),
        UniqueConstraint("gstin", name="uq_accounts_gstin"),
        CheckConstraint("length(trim(account_code)) > 0", name="ck_accounts_code"),
        CheckConstraint("length(trim(account_name)) > 0", name="ck_accounts_name"),
        CheckConstraint(f"gstin IS NULL OR gstin ~ '^{GSTIN_PATTERN}$'",
                        name="ck_accounts_gstin").ddl_if(dialect="postgresql"),
        CheckConstraint(f"pan_card IS NULL OR pan_card ~ '^{PAN_PATTERN}$'",
                        name="ck_accounts_pan").ddl_if(dialect="postgresql"),
        CheckConstraint("gstin IS NULL OR (pan_card IS NOT NULL AND pan_card = substr(gstin, 3, 10))",
                        name="ck_accounts_gstin_pan"),
    )
    id = Column(Integer, primary_key=True)
    account_code = Column(String(30), nullable=False)
    account_name = Column(String(200), nullable=False)
    country_code = Column(String(10))
    mobile = Column(String(20))
    email = Column(String(320))
    address = Column(Text)
    city = Column(String)
    state = Column(String)
    pincode = Column(String(20))
    state_code = Column(String(2))
    gstin = Column(String)  # CHECK enforces length without VARCHAR truncating trailing spaces.
    gstin_pending = Column(Boolean, nullable=False, default=False, server_default=false())
    pan_card = Column(String)
    remarks = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    roles = relationship("AccountRole", back_populates="account", passive_deletes="all")

    @property
    def customer_name(self) -> str:
        return self.account_name

    @property
    def name(self) -> str:
        return self.account_name

    @property
    def customer_code(self) -> str:
        return self.account_code

    @property
    def party_code(self) -> str:
        return self.account_code

    @property
    def opening_remark(self) -> str | None:
        return self.remarks


class AccountRole(Base):
    __tablename__ = "account_roles"
    __table_args__ = (
        UniqueConstraint("account_id", "role", name="uq_account_roles_account_role"),
        Index("ix_account_roles_role_account", "role", "account_id"),
    )
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    role = Column(Enum(AccountRoleCode, native_enum=False, create_constraint=True,
                       name="ck_account_roles_role", length=20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    account = relationship("Account", back_populates="roles")
    ledger = relationship("AccountLedger", back_populates="account_role", uselist=False,
                          passive_deletes="all")


class AccountLedger(Base):
    __tablename__ = "account_ledgers"
    __table_args__ = (
        UniqueConstraint("id", "account_id", "role", name="uq_account_ledgers_identity"),
        UniqueConstraint("id", "role", name="uq_account_ledgers_id_role"),
        UniqueConstraint("account_id", "role", name="uq_account_ledgers_account_role"),
        ForeignKeyConstraint(["account_id", "role"], ["account_roles.account_id", "account_roles.role"],
                             name="fk_account_ledger_role", ondelete="RESTRICT", onupdate="RESTRICT"),
        # The upper bound also excludes PostgreSQL Numeric NaN/+Infinity.
        CheckConstraint("opening_balance >= 0 AND opening_balance < 10000000000000000",
                        name="ck_account_ledgers_opening_amount"),
        CheckConstraint("current_balance >= 0 AND current_balance < 10000000000000000",
                        name="ck_account_ledgers_current_amount"),
        CheckConstraint("(opening_balance = 0 AND balance_type IS NULL) OR "
                        "(opening_balance > 0 AND balance_type IS NOT NULL AND balance_type IN ('Debit','Credit'))",
                        name="ck_account_ledgers_opening_direction"),
        CheckConstraint("(current_balance = 0 AND current_balance_type IS NULL) OR "
                        "(current_balance > 0 AND current_balance_type IS NOT NULL AND current_balance_type IN ('Debit','Credit'))",
                        name="ck_account_ledgers_current_direction"),
    )
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, nullable=False)
    role = Column(Enum(AccountRoleCode, native_enum=False, create_constraint=True,
                       name="ck_account_ledgers_role", length=20), nullable=False)
    opening_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    balance_type = Column(String(10))
    current_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    current_balance_type = Column(String(10))
    opening_remark = Column(Text)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    account_role = relationship("AccountRole", back_populates="ledger")
