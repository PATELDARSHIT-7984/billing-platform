"""Roles of the new Account identity; legacy PartyType retains its wire values."""
from enum import Enum


class AccountRoleCode(str, Enum):
    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    PURCHASE_VENDOR = "PURCHASE_VENDOR"
