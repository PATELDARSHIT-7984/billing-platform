"""Canonical optional account GSTIN (format, not checksum verification)."""
import re

GSTIN_PATTERN = r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]"
PAN_PATTERN = r"[A-Z]{5}[0-9]{4}[A-Z]"


def normalize_gstin(value: str | None) -> str | None:
    value = value.strip().upper() if value else None
    if not value:
        return None
    if not re.fullmatch(GSTIN_PATTERN, value):
        raise ValueError("Invalid GSTIN")
    return value


def normalize_pan(value: str | None) -> str | None:
    """New Account validation; legacy PAN contracts are intentionally unchanged."""
    value = value.strip().upper() if value else None
    if not value:
        return None
    if not re.fullmatch(PAN_PATTERN, value):
        raise ValueError("Invalid PAN")
    return value


def pan_from_gstin(gstin: str | None) -> str | None:
    gstin = normalize_gstin(gstin)
    return gstin[2:12] if gstin else None
