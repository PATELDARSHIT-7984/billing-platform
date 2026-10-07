"""Supplier and Purchase Vendor share the same real Party posting path."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster
from api.router.purchase import router as purchase_router
from api.schema.party import PartyCreate
from api.schema.purchase import PurchaseCreate, PurchaseUpdate
from api.schema.purchase_return import PurchaseReturnCreate, PurchaseReturnUpdate
from api.schema.rojmel import RojmelCreate, RojmelUpdate
from api.services import party, purchase, purchase_return, rojmel
from api.utils.account_balance import signed_balance


@pytest.mark.parametrize('kind', ['Supplier', 'PURCHASE_VENDOR'])
@pytest.mark.parametrize('amount,direction', [(0, 'Debit'), (100, 'Credit'), (100, 'Debit')])
def test_opening_and_lookup(db_session, kind, amount, direction):
    saved = party.create_party(db_session, PartyCreate(name='Vendor', party_type=kind,
        opening_balance=amount, balance_type=direction, gstin=''))
    assert saved.current_balance == amount
    assert saved.current_balance_type == (direction if amount else 'Credit')
    assert saved.gstin is None
    assert party.get_party_by_id(db_session, saved.id).id == saved.id


@pytest.mark.parametrize('kind', ['Supplier', 'PURCHASE_VENDOR'])
def test_purchase_return_and_payment_lifecycle(db_session, client, test_app, kind):
    test_app.include_router(purchase_router)
    other_kind = 'Supplier' if kind == 'PURCHASE_VENDOR' else 'PURCHASE_VENDOR'
    accounts = [party.create_party(db_session, PartyCreate(name=name, party_type=classification,
        opening_balance=1000)) for name, classification in [('First', kind), ('Second', other_kind)]]
    item = ItemMaster(name='Tile', hsn_code='1234', unit='Box', current_stock=100)
    bank, person = BankModel(name='Cash'), DoneByModel(name='Operator')
    db_session.add_all([item, bank, person])
    db_session.commit()

    def balances():
        for account in accounts:
            db_session.refresh(account)
        return [signed_balance(a.current_balance, a.current_balance_type) for a in accounts]

    def line(price):
        return dict(item_id=item.id, item_name=item.name, hsn_code='1234', unit='Box', quantity=1, price=price)

    saved = purchase.create_purchase(db_session, PurchaseCreate(bill_no='VENDOR-1',
        party_id=accounts[0].id, items=[line(500)]))
    assert balances() == [1000 + Decimal(str(saved.grand_total)), 1000]
    saved = purchase.update_purchase_by_id(db_session, saved.id, PurchaseUpdate(items=[line(600)]))
    assert balances() == [1000 + Decimal(str(saved.grand_total)), 1000]
    saved = purchase.update_purchase_by_id(db_session, saved.id, PurchaseUpdate(party_id=accounts[1].id))
    purchase_total = Decimal(str(saved.grand_total))
    assert balances() == [1000, 1000 + purchase_total]
    # Purchase deletion is deliberately not exposed for either classification.
    for _ in range(2):
        assert client.delete(f'/purchases/{saved.id}').status_code == 405
    assert balances() == [1000, 1000 + purchase_total]

    returned = purchase_return.create_purchase_return(db_session, PurchaseReturnCreate(
        party_id=accounts[0].id, return_reason='Damaged', items=[line(100)]))
    assert balances() == [1000 - Decimal(str(returned.grand_total)), 1000 + purchase_total]
    returned = purchase_return.update_purchase_return_by_id(db_session, returned.id,
        PurchaseReturnUpdate(items=[line(200)]))
    assert balances() == [1000 - Decimal(str(returned.grand_total)), 1000 + purchase_total]
    returned = purchase_return.update_purchase_return_by_id(db_session, returned.id,
        PurchaseReturnUpdate(party_id=accounts[1].id))
    assert balances() == [1000, 1000 + purchase_total - Decimal(str(returned.grand_total))]
    purchase_return.delete_purchase_return_by_id(db_session, returned.id)
    with pytest.raises(HTTPException):
        purchase_return.delete_purchase_return_by_id(db_session, returned.id)
    assert balances() == [1000, 1000 + purchase_total]

    payment = rojmel.create_rojmel(db_session, RojmelCreate(transaction_type='Dr Pay',
        party_id=accounts[0].id, amount=100, receipt_no='ignored',
        given_taken_date=date.today(), effective_date=date.today(), cash_bank_id=bank.id,
        done_by_id=person.id, pay_mode='Cash'))
    assert balances() == [900, 1000 + purchase_total]
    rojmel.update_rojmel(db_session, payment.id, RojmelUpdate(amount=200))
    assert balances() == [800, 1000 + purchase_total]
    rojmel.update_rojmel(db_session, payment.id, RojmelUpdate(party_id=accounts[1].id))
    assert balances() == [1000, 800 + purchase_total]
    rojmel.update_rojmel(db_session, payment.id, RojmelUpdate(transaction_type='Cr Pay'))
    assert balances() == [1000, 1000 + purchase_total]  # existing Party Cr Pay policy
    rojmel.update_rojmel(db_session, payment.id, RojmelUpdate(transaction_type='Dr Pay'))
    rojmel.delete_rojmel(db_session, payment.id)
    with pytest.raises(HTTPException):
        rojmel.delete_rojmel(db_session, payment.id)
    assert balances() == [1000, 1000 + purchase_total]
