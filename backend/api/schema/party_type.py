from enum import Enum


class PartyType(str, Enum):
    # Keep the existing wire/storage values; Customer is legacy compatibility.
    SUPPLIER = "Supplier"
    PURCHASE_VENDOR = "PURCHASE_VENDOR"
    LEGACY_CUSTOMER = "Customer"
