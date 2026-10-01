from fastapi import HTTPException, status

from api.repository import rojmel as rojmel_repository


def validate_and_get_active_bank(db, cash_bank_id: int):
    # Confirms the selected Cash/Bank account exists and is active; returns it.
    bank = rojmel_repository.get_active_bank_by_id(db, cash_bank_id)
    if not bank:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected Cash/Bank is invalid or inactive.")
    return bank


def validate_and_get_active_done_by(db, done_by_id: int):
    # Confirms the selected "Done By" person exists and is active; returns them.
    done_by = rojmel_repository.get_active_done_by_by_id(db, done_by_id)
    if not done_by:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected 'Done By' person is invalid or inactive.")
    return done_by


def validate_party_exists(db, party_id: int | None):
    # Party is optional on a receipt; only validated when one is provided.
    if not party_id:
        return None
    party = rojmel_repository.get_party_by_id_any_status(db, party_id)
    if not party:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected Party does not exist.")
    return party


def validate_and_get_supplier_payment_party(db, transaction_type, party_id, require_active=False):
    """Resolve supplier payments; historical reversals may use inactive parties."""
    if transaction_type != "Dr Pay" or party_id is None:
        return None
    party = validate_party_exists(db, party_id)
    if party is None or party.party_type != "Supplier":
        return None
    if require_active and not party.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected supplier is inactive.")
    return party


def validate_and_get_rojmel(db, rojmel_id: int):
    # Fetches a receipt by id or raises 404 if it doesn't exist.
    rojmel = rojmel_repository.get_rojmel_by_id(db, rojmel_id)
    if not rojmel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rojmel entry not found.")
    return rojmel


def validate_gst_type_is_exclusive(sgst, cgst, igst) -> None:
    # IGST is for inter-state transactions, SGST+CGST for intra-state --
    # a single entry can never legitimately carry both.
    if igst and igst > 0 and ((sgst and sgst > 0) or (cgst and cgst > 0)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IGST cannot be applied together with SGST or CGST.",
        )
