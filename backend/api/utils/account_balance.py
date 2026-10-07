"""Party-compatible amount/direction arithmetic; no database or posting policy."""
from decimal import Decimal
from typing import Literal

BalanceType = Literal["Credit", "Debit"]


def signed_balance(amount, direction):
    amount = Decimal(str(amount))
    return -amount if direction == "Debit" else amount


def balance_after_delta(amount, direction, delta):
    value = signed_balance(amount, direction) + Decimal(str(delta))
    return abs(value), "Debit" if value < 0 else "Credit"
