"""Future Account contracts only: no public endpoints or posting authority."""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from api.schema.account_role import AccountRoleCode
from api.utils.account_balance import BalanceType
from api.utils.gstin import normalize_gstin, normalize_pan, pan_from_gstin

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]


def _check_direction(amount, direction):
    if (amount == 0) != (direction is None):
        raise ValueError("Zero balance requires no direction; positive balance requires Debit or Credit.")


class AccountBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)
    account_name: str = Field(min_length=2, max_length=200)
    country_code: str | None = Field(default=None, max_length=10)
    mobile: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = Field(default=None, max_length=320)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=2)
    gstin: str | None = None
    pan_card: str | None = None
    remarks: str | None = None
    is_active: bool = True

    _gstin = field_validator("gstin")(normalize_gstin)
    _pan = field_validator("pan_card")(normalize_pan)

    @model_validator(mode="after")
    def consistent_tax_identity(self):
        if self.gstin:
            derived = pan_from_gstin(self.gstin)
            if self.pan_card is not None and self.pan_card != derived:
                raise ValueError("PAN does not match the PAN contained in GSTIN.")
            self.pan_card = derived
        return self


class AccountRoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    role: AccountRoleCode
    opening_balance: Money = Decimal("0.00")
    balance_type: BalanceType | None = None
    opening_remark: str | None = None

    @model_validator(mode="after")
    def opening_direction(self):
        _check_direction(self.opening_balance, self.balance_type)
        return self


class AccountCreate(AccountBase):
    account_code: str = Field(min_length=1, max_length=30)
    roles: list[AccountRoleInput] = Field(min_length=1)

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, roles):
        if len({entry.role for entry in roles}) != len(roles):
            raise ValueError("Duplicate account role.")
        return roles


class AccountUpdate(AccountBase):
    account_name: str | None = Field(default=None, min_length=2, max_length=200)

    @field_validator("account_name")
    @classmethod
    def name_cannot_be_cleared(cls, value):
        if value is None:
            raise ValueError("Account name cannot be null.")
        return value

    def apply_to(self, current: AccountBase) -> AccountBase:
        """Validate PATCH against existing identity before any future DB write.

        A changed GSTIN derives PAN in the inherited validator. Clearing GSTIN
        alone leaves PAN untouched because absent fields are excluded here.
        PAN-only edits must also agree with the existing GSTIN.
        """
        values = current.model_dump(include=set(AccountBase.model_fields))
        values.update(self.model_dump(exclude_unset=True))
        return AccountBase.model_validate(values)


class AccountLedgerResponse(AccountRoleInput):
    id: int
    account_id: int
    current_balance: Money
    current_balance_type: BalanceType | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def current_direction(self):
        _check_direction(self.current_balance, self.current_balance_type)
        return self


class AccountRoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    role: AccountRoleCode
    is_active: bool
    created_at: datetime
    updated_at: datetime
    ledger: AccountLedgerResponse | None


class AccountResponse(AccountBase):
    id: int
    account_code: str
    created_at: datetime
    updated_at: datetime
    roles: list[AccountRoleResponse]
