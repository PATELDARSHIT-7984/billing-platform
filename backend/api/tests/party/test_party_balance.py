from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.model.party import Party
from api.services.party import apply_party_balance_delta
from api.services import party as service
from api.schema.party import PartyCreate, PartyUpdate
from api.dependencies import dependencies
from api.model.item_master import ItemMaster
from api.schema.purchase import PurchaseCreate
from api.schema.purchase_return import PurchaseReturnCreate
from api.services.purchase import create_purchase
from api.services.purchase_return import create_purchase_return


@pytest.mark.parametrize(
    "balance,balance_type,delta,expected,expected_type,is_active",
    [
        ("5000", "Credit", Decimal("2000"), "7000", "Credit", True),
        ("5000", "Credit", -7000, "2000", "Debit", True),
        ("5000", "Debit", 7000, "2000", "Credit", True),
        ("5000", "Debit", -2000, "7000", "Debit", True),
        ("5000", "Credit", -5000, "0", "Credit", True),
        ("5000", "Credit", -7000, "2000", "Debit", False),
        ("0.10", "Credit", 0.2, "0.30", "Credit", True),
    ],
)
def test_balance_delta(
    db_session, balance, balance_type, delta, expected, expected_type, is_active
):
    party = Party(
        name="Balance test",
        current_balance=Decimal(balance),
        current_balance_type=balance_type,
        opening_balance=Decimal("123.45"),
        balance_type="Debit",
        is_active=is_active,
    )
    db_session.add(party)
    db_session.commit()

    with patch.object(db_session, "commit") as commit, patch.object(
        db_session, "rollback"
    ) as rollback:
        result = apply_party_balance_delta(db_session, party.id, delta)
        commit.assert_not_called()
        rollback.assert_not_called()

    assert result is party
    assert result.current_balance == Decimal(expected)
    assert result.current_balance_type == expected_type
    db_session.refresh(party)
    assert party.current_balance == Decimal(expected)
    assert party.current_balance_type == expected_type
    assert party.opening_balance == Decimal("123.45")
    assert party.balance_type == "Debit"
    assert party.is_active is is_active

    db_session.rollback()
    db_session.refresh(party)
    assert party.current_balance == Decimal(balance)
    assert party.current_balance_type == balance_type


def test_missing_party_raises_controlled_error(db_session):
    with patch.object(db_session, "commit") as commit, patch.object(
        db_session, "rollback"
    ) as rollback:
        with pytest.raises(HTTPException) as error:
            apply_party_balance_delta(db_session, 999999, Decimal("100"))
        commit.assert_not_called()
        rollback.assert_not_called()

    assert error.value.status_code == 404
    assert error.value.detail == "Party not found"


@pytest.mark.parametrize('amount,kind,expected_type', [
    ('1500', 'Credit', 'Credit'), ('800', 'Debit', 'Debit'),
    ('0', 'Credit', 'Credit'), ('0', 'Debit', 'Credit'),
])
def test_create_initializes_current_balance(client, party_api, db_session, amount, kind, expected_type):
    response = client.post(party_api.base_url, json=party_api.create_payload(
        opening_balance=amount, balance_type=kind))
    assert response.status_code == 201, response.text
    data = response.json()
    assert Decimal(data['current_balance']) == Decimal(amount)
    assert data['current_balance_type'] == expected_type
    party = db_session.get(Party, data['id'])
    assert party.current_balance == party.opening_balance == Decimal(amount)
    assert party.balance_type == kind
    assert party.current_balance_type == expected_type


@pytest.mark.parametrize('opening,kind,current,current_type,changes,expected,expected_type', [
    (1000, 'Credit', 1500, 'Credit', {'opening_balance': 1200}, 1700, 'Credit'),
    (1000, 'Credit', 1500, 'Credit', {'opening_balance': 200, 'balance_type': 'Debit'}, 300, 'Credit'),
    (500, 'Debit', 200, 'Debit', {'opening_balance': 100, 'balance_type': 'Credit'}, 400, 'Credit'),
    (1000, 'Credit', 300, 'Credit', {'opening_balance': 200}, 500, 'Debit'),
    (500, 'Debit', 200, 'Debit', {'opening_balance': 100}, 200, 'Credit'),
    (1000, 'Credit', 1500, 'Credit', {'balance_type': 'Debit'}, 500, 'Debit'),
    (1000, 'Credit', 300, 'Credit', {'opening_balance': 700}, 0, 'Credit'),
    (1000, 'Credit', 1500, 'Credit', {'name': 'Edited supplier', 'mobile': '12345'}, 1500, 'Credit'),
    (1000, 'Credit', 1500, 'Credit', {'opening_balance': 1000, 'balance_type': 'Credit'}, 1500, 'Credit'),
])
def test_opening_edit_preserves_transaction_effect(client, party_api, db_session,
        opening, kind, current, current_type, changes, expected, expected_type):
    party = Party(name='Supplier', opening_balance=opening, balance_type=kind,
                  current_balance=current, current_balance_type=current_type)
    db_session.add(party)
    db_session.commit()
    response = client.put(party_api.detail_url(party.id), json=changes)
    assert response.status_code == 200, response.text
    assert Decimal(response.json()['current_balance']) == Decimal(expected)
    assert response.json()['current_balance_type'] == expected_type
    db_session.refresh(party)
    assert party.current_balance == Decimal(expected)
    assert party.current_balance_type == expected_type
    assert party.opening_balance == Decimal(changes.get('opening_balance', opening))
    assert party.balance_type == changes.get('balance_type', kind)


@pytest.mark.parametrize('failure', ['negative', 'null_amount', 'null_type', 'duplicate_gstin', 'update'])
def test_failed_opening_edit_does_not_persist(client, test_app, party_api, db_session,
                                            test_session_factory, monkeypatch, failure):
    test_app.dependency_overrides.pop(dependencies.get_db)
    monkeypatch.setattr(dependencies, 'SessionLocal', test_session_factory)
    party = Party(name='Original', opening_balance=1000, balance_type='Credit',
                  current_balance=1500, current_balance_type='Credit')
    other = Party(name='Other', gstin='24ABCDE1234F1Z5')
    db_session.add_all([party, other])
    db_session.commit()
    changes = {'name': 'Changed', 'opening_balance': 1200}
    if failure == 'update':
        with patch.object(service.party_repo, 'update_party', side_effect=RuntimeError('update failed')):
            with pytest.raises(RuntimeError, match='update failed'):
                client.put(party_api.detail_url(party.id), json=changes)
    else:
        changes.update({'negative': {'opening_balance': -1},
                        'null_amount': {'opening_balance': None},
                        'null_type': {'balance_type': None},
                        'duplicate_gstin': {'gstin': other.gstin}}[failure])
        response = client.put(party_api.detail_url(party.id), json=changes)
        assert response.status_code == (400 if failure == 'duplicate_gstin' else 422)
    db_session.refresh(party)
    assert party.name == 'Original'
    assert party.opening_balance == 1000
    assert party.balance_type == 'Credit'
    assert party.current_balance == 1500
    assert party.current_balance_type == 'Credit'


def test_purchase_and_return_preserve_edited_opening(db_session):
    party = service.create_party(db_session, PartyCreate(name='Supplier', opening_balance=1000))
    item = ItemMaster(name='Tile', hsn_code='6907', unit='Box', current_stock=0)
    db_session.add(item)
    db_session.commit()
    line = dict(item_id=item.id, item_name=item.name, hsn_code=item.hsn_code,
                unit=item.unit, quantity=1, price=500)
    create_purchase(db_session, PurchaseCreate(bill_no='OPENING-TEST', party_id=party.id, items=[line]))
    db_session.refresh(party)
    assert party.current_balance == 1500
    service.update_party_by_id(db_session, party.id, PartyUpdate(opening_balance=1200))
    assert party.current_balance == 1700
    create_purchase_return(db_session, PurchaseReturnCreate(
        party_id=party.id, return_reason='Returned', items=[line]))
    db_session.refresh(party)
    assert party.current_balance == party.opening_balance == 1200
    assert party.current_balance_type == 'Credit'
