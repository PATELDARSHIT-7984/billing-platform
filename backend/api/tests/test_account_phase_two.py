"""Final merged Account identity rules; no public writers."""
import pytest
from pydantic import ValidationError
from api.schema.account import AccountBase, AccountCreate, AccountUpdate
from api.utils.gst_state import GST_STATES, state_code_from_name

GSTIN = '24ABCDE1234F1Z5'
OTHER = '27FGHIJ5678K1Z2'


def current():
    return AccountBase(account_name='Existing', state_code='24', gstin=GSTIN, mobile='123')


@pytest.mark.parametrize('patch', [
    {'gstin': OTHER}, {'state_code': '27'}, {'state': 'Maharashtra'},
    {'state_code': None}, {'state': None},
    {'gstin': OTHER, 'state_code': '27', 'pan_card': 'ABCDE1234F'},
    {'pan_card': 'FGHIJ5678K'},
])
def test_inconsistent_patch_rejected(patch):
    with pytest.raises(ValidationError):
        AccountUpdate(**patch).apply_to(current())


@pytest.mark.parametrize('pan', [None, ' fghij5678k '])
def test_matching_gstin_state_change(pan):
    saved = current()
    result = AccountUpdate(gstin=OTHER, state_code='27', pan_card=pan).apply_to(saved)
    assert (result.gstin, result.pan_card, result.state_code, result.state) == (OTHER, 'FGHIJ5678K', '27', 'Maharashtra')
    assert saved.gstin == GSTIN and result.mobile == saved.mobile


def test_omitted_pan_derived_on_gstin_change():
    assert AccountUpdate(gstin=OTHER, state_code='27').apply_to(current()).pan_card == 'FGHIJ5678K'


@pytest.mark.parametrize('pending', [False, True])
def test_clear_gstin_preserves_other_fields(pending):
    result = AccountUpdate(gstin=None, gstin_pending=pending).apply_to(current())
    assert (result.gstin, result.pan_card, result.state, result.state_code, result.gstin_pending) == (
        None, 'ABCDE1234F', 'Gujarat', '24', pending)
    assert AccountUpdate(remarks='Text').apply_to(result).model_dump(exclude={'remarks'}) == result.model_dump(exclude={'remarks'})


def test_clear_gstin_and_state_and_pan():
    result = AccountUpdate(gstin=None, state_code=None, pan_card=None).apply_to(current())
    assert result.gstin is result.pan_card is result.state is result.state_code is None


@pytest.mark.parametrize('pending', [False, True])
def test_valid_gstin_clears_pending(pending):
    saved = AccountBase(account_name='Pending', state_code='24', gstin_pending=pending)
    result = AccountUpdate(gstin=GSTIN, gstin_pending=True).apply_to(saved)
    assert result.gstin_pending is False
    assert current().gstin_pending is False


@pytest.mark.parametrize('code,name', [('24','Gujarat'),('27','Maharashtra')])
def test_canonical_state(code, name):
    value = AccountBase(account_name='State', state_code=code, state='Untrusted text')
    assert value.state == name
    assert state_code_from_name(' '+name.lower()+' ') == code
    assert AccountUpdate(state_code=code, state='Wrong').apply_to(AccountBase(account_name='Test')).state == name


@pytest.mark.parametrize('values', [
    {'gstin': GSTIN}, {'gstin': GSTIN, 'state_code':'27'},
    {'state_code':'00'}, {'state_code':'99'}, {'state_code':'GJ'}, {'state':'Unknown'},
])
def test_create_rejects_invalid_state(values):
    with pytest.raises(ValidationError):
        AccountCreate(account_code='NEW', account_name='Example', roles=[{'role':'CUSTOMER'}], **values)


def test_create_normalizes_and_derives_identity():
    value = AccountCreate(account_code='NEW', account_name='Example', roles=[{'role':'CUSTOMER'}],
                          state=' gujarat ', gstin=' '+GSTIN.lower()+' ', gstin_pending=True)
    assert (value.state_code, value.state, value.pan_card, value.gstin_pending) == ('24','Gujarat','ABCDE1234F',False)


def test_mapping_covers_registration_states_and_legacy_codes():
    assert set(GST_STATES) == {f'{i:02}' for i in range(1,39)} | {'97'}


@pytest.mark.parametrize('code', ['25', '28'])
@pytest.mark.parametrize('selection', ['code', 'name'])
def test_historical_state_not_selectable(code, selection):
    fields = {'state_code':code} if selection == 'code' else {'state':GST_STATES[code]}
    with pytest.raises(ValidationError, match='current GST state'):
        AccountCreate(account_code='NEW', account_name='New', roles=[{'role':'CUSTOMER'}], **fields)
    with pytest.raises(ValidationError, match='current GST state'):
        AccountUpdate(**fields)


@pytest.mark.parametrize('patch', [
    {'account_name':'Updated Name'}, {'mobile':'123','email':'test@example.com','address':'New road'},
    {'pan_card':'BBBCR5055K'}, {'remarks':'History'},
])
def test_historical_read_and_unrelated_patch(patch):
    from datetime import datetime
    from api.schema.account import AccountResponse
    saved = AccountResponse(id=1,account_code='OLD',account_name='Historical',state_code='28',
        gstin='28BBBCR5055K1Z9',roles=[],created_at=datetime.now(),updated_at=datetime.now())
    result = AccountUpdate(**patch).apply_to(saved)
    assert (result.state_code,result.state,result.gstin) == ('28','Andhra Pradesh (Old)','28BBBCR5055K1Z9')


@pytest.mark.parametrize('code', ['25', '28'])
def test_gstin_change_cannot_create_historical_identity(code):
    with pytest.raises(ValidationError, match='current GST state'):
        AccountUpdate(gstin=code+'ABCDE1234F1Z5')


def test_historical_identity_can_change_to_current_pair():
    saved = AccountBase(account_name='Historical',state_code='28',gstin='28BBBCR5055K1Z9')
    result = AccountUpdate(state_code='27',gstin=OTHER).apply_to(saved)
    assert (result.state_code,result.state,result.pan_card) == ('27','Maharashtra','FGHIJ5678K')
