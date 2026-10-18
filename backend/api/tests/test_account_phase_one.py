"""Account foundation contracts, without a public write API."""
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from api.model.account import Account, AccountRole, AccountLedger
from api.schema.account import (
    AccountBase, AccountCreate, AccountUpdate, AccountResponse,
    AccountRoleInput, AccountLedgerResponse,
)
from api.schema.account_role import AccountRoleCode

GSTIN = '24ABCDE1234F1Z5'
OTHER = '24FGHIJ5678K1Z5'


def create_input(**changes):
    return AccountCreate.model_validate(dict(account_code='ACC-1', account_name='Example',
        roles=[{'role': 'CUSTOMER'}], **changes))


@pytest.mark.parametrize('gstin,pan,expected', [
    (None, None, None), (' ', '', None), (None, ' abcde1234f ', 'ABCDE1234F'),
    (GSTIN, None, 'ABCDE1234F'), (GSTIN.lower(), None, 'ABCDE1234F'),
    ('  ' + GSTIN + '  ', None, 'ABCDE1234F'), (GSTIN, ' abcde1234f ', 'ABCDE1234F'),
])
def test_tax_normalization_and_derivation(gstin, pan, expected):
    account = create_input(gstin=gstin, pan_card=pan)
    assert account.pan_card == expected
    assert account.gstin == (GSTIN if gstin and gstin.strip() else None)


@pytest.mark.parametrize('values', [
    {'gstin': 'XXXXXXXXXXXXXXX'}, {'gstin': '24ABCDE1234F Z5'},
    {'pan_card': 'ABCDEFGHIJ'}, {'pan_card': 'ABCDE 123F'},
    {'gstin': GSTIN, 'pan_card': 'PQRSX5678L'},
])
def test_invalid_tax_identity(values):
    with pytest.raises(ValidationError):
        create_input(**values)


@pytest.mark.parametrize('patch,gstin,pan', [
    ({}, GSTIN, 'ABCDE1234F'),
    ({'gstin': OTHER}, OTHER, 'FGHIJ5678K'),
    ({'gstin': OTHER, 'pan_card': None}, OTHER, 'FGHIJ5678K'),
    ({'gstin': OTHER, 'pan_card': 'fghij5678k'}, OTHER, 'FGHIJ5678K'),
    ({'gstin': None}, None, 'ABCDE1234F'),
    ({'gstin': '  '}, None, 'ABCDE1234F'),
    ({'gstin': None, 'pan_card': None}, None, None),
    ({'gstin': None, 'pan_card': 'FGHIJ5678K'}, None, 'FGHIJ5678K'),
    ({'pan_card': None}, GSTIN, 'ABCDE1234F'),
])
def test_patch_preserves_or_derives_pan(patch, gstin, pan):
    current = AccountBase(account_name='Before', gstin=GSTIN, mobile='123')
    result = AccountUpdate(**patch).apply_to(current)
    assert (result.gstin, result.pan_card) == (gstin, pan)
    assert result.account_name == 'Before' and result.mobile == '123'
    assert current.gstin == GSTIN  # Validation does not mutate the original.


@pytest.mark.parametrize('patch', [
    {'pan_card': 'FGHIJ5678K'}, {'gstin': OTHER, 'pan_card': 'ABCDE1234F'},
    {'account_name': None}, {'account_name': ' '}, {'is_active': None},
    {'current_balance': '5'}, {'roles': []},
])
def test_invalid_patch_final_state(patch):
    with pytest.raises(ValidationError):
        AccountUpdate(**patch).apply_to(AccountBase(account_name='Before', gstin=GSTIN))


@pytest.mark.parametrize('role', list(AccountRoleCode))
def test_each_canonical_role(role):
    assert AccountRoleInput(role=role).balance_type is None


@pytest.mark.parametrize('roles', [[], [{'role': 'UNKNOWN'}],
    [{'role': 'CUSTOMER'}, {'role': 'CUSTOMER'}],
    [{'role': 'CUSTOMER', 'gstin': GSTIN}],
    [{'role': 'CUSTOMER', 'current_balance': '10'}],
    [{'role': 'CUSTOMER', 'current_balance_type': 'Debit'}],
])
def test_invalid_roles(roles):
    with pytest.raises(ValidationError):
        AccountCreate(account_code='ACC-1', account_name='Example', roles=roles)


@pytest.mark.parametrize('field', ['opening_balance', 'current_balance'])
@pytest.mark.parametrize('amount,direction,valid', [
    ('0', None, True), ('0', 'Credit', False), ('0', 'Debit', False),
    ('1', None, False), ('1', 'Debit', True), ('1', 'Credit', True),
    ('1', 'Other', False), ('-1', 'Debit', False), ('NaN', None, False),
    ('Infinity', 'Credit', False), ('-Infinity', 'Debit', False),
    ('0.001', 'Debit', False), ('10000000000000000', 'Credit', False),
])
def test_ledger_schema_amount_and_direction(field, amount, direction, valid):
    values = dict(id=1, account_id=1, role='CUSTOMER', opening_balance='0', balance_type=None,
                  current_balance='0', current_balance_type=None, created_at=datetime.now(), updated_at=datetime.now())
    values[field] = amount
    values['balance_type' if field == 'opening_balance' else 'current_balance_type'] = direction
    if valid:
        assert getattr(AccountLedgerResponse(**values), field) == Decimal(amount)
    else:
        with pytest.raises(ValidationError):
            AccountLedgerResponse(**values)


def test_multi_role_creation_and_balances(db_session):
    data = AccountCreate(account_code='ACC-1', account_name='ABC Traders', gstin=GSTIN,
        roles=[{'role': 'CUSTOMER', 'opening_balance': '10000', 'balance_type': 'Debit'},
               {'role': 'SUPPLIER', 'opening_balance': '6000', 'balance_type': 'Credit'}])
    account = Account(**data.model_dump(exclude={'roles'}))
    for entry in data.roles:
        role = AccountRole(role=entry.role)
        role.ledger = AccountLedger(**entry.model_dump(), current_balance=entry.opening_balance,
                                    current_balance_type=entry.balance_type)
        account.roles.append(role)
    db_session.add(account)
    db_session.commit()
    customer, supplier = account.roles
    customer.ledger.current_balance = Decimal('9000')
    supplier.is_active = False
    db_session.commit()
    db_session.expire_all()
    response = AccountResponse.model_validate(account)
    ledgers = {r.role: r.ledger for r in response.roles}
    assert ledgers[AccountRoleCode.CUSTOMER].current_balance == 9000
    assert ledgers[AccountRoleCode.SUPPLIER].current_balance == 6000
    assert customer.ledger.id != supplier.ledger.id
    assert supplier.is_active is False and account.is_active is True
    assert not hasattr(account, 'current_balance')


def test_model_uniqueness_and_nulls(db_session):
    db_session.add_all([Account(account_code='A', account_name='First', pan_card='ABCDE1234F'),
                        Account(account_code='B', account_name='Second', pan_card='ABCDE1234F')])
    db_session.commit()  # Duplicate PAN and multiple null GSTINs are allowed.
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(Account(account_code='A', account_name='Duplicate'))
        db_session.flush()
    assert db_session.query(Account).count() == 2


def test_role_ledger_database_relationship(db_session):
    account = Account(account_code='A', account_name='Example')
    db_session.add(account)
    db_session.flush()
    db_session.add(AccountRole(account_id=account.id, role='CUSTOMER'))
    db_session.commit()
    for row in [AccountRole(account_id=account.id, role='CUSTOMER'),
                AccountLedger(account_id=account.id, role='SUPPLIER')]:
        with pytest.raises(IntegrityError), db_session.begin_nested():
            db_session.add(row)
            db_session.flush()
    ledger = AccountLedger(account_id=account.id, role='CUSTOMER')
    db_session.add(ledger)
    db_session.commit()
    assert ledger.current_balance == 0 and ledger.current_balance_type is None
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(AccountLedger(account_id=account.id, role='CUSTOMER'))
        db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(db_session.query(AccountRole).one())
        db_session.flush()


def test_no_public_account_endpoints():
    from api.main import app
    assert not any(route.path.startswith('/accounts') for route in app.routes)
