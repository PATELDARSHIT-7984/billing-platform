"""Global namespace, API compatibility and atomic identity changes."""
import pytest
from sqlalchemy import event

from api.model.account_gstin import AccountGSTIN
from api.model.customer import Customer
from api.model.party import Party
from api.schema.customer import CustomerCreate, CustomerUpdate
from api.schema.party import PartyCreate, PartyUpdate
from api.services import customer, party
from api.services.gstin_identity import DUPLICATE_GSTIN

GSTIN = "24ABCDE1234F1Z5"
OTHER = "24FGHIJ5678K1Z5"
KINDS = ("customer", "Supplier", "PURCHASE_VENDOR")


def payload(kind, gstin=GSTIN):
    if kind == "customer":
        return dict(customer_name="GSTIN test", mobile="9876543210", address="Test road",
                    city="City", state="State", gstin=gstin)
    return dict(name="GSTIN test", party_type=kind, gstin=gstin)


def endpoint(kind):
    return "/customers/" if kind == "customer" else "/parties/"


@pytest.mark.parametrize("owner", KINDS)
@pytest.mark.parametrize("contender", KINDS)
@pytest.mark.parametrize("spelling", [GSTIN, GSTIN.lower(), "  " + GSTIN + "  "])
def test_duplicate_matrix(client, db_session, owner, contender, spelling):
    first = client.post(endpoint(owner), json=payload(owner))
    assert first.status_code == 201, first.text
    second = client.post(endpoint(contender), json=payload(contender, spelling))
    assert second.status_code == 400, second.text
    assert second.json()["detail"] == DUPLICATE_GSTIN
    assert db_session.query(AccountGSTIN).count() == 1
    assert db_session.query(Customer).count() + db_session.query(Party).count() == 1


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("gstin", [None, "", " \t\n "])
def test_empty_is_not_identity(client, db_session, kind, gstin):
    for _ in range(2):
        response = client.post(endpoint(kind), json=payload(kind, gstin))
        assert response.status_code == 201, response.text
        assert response.json()["gstin"] is None
    assert db_session.query(AccountGSTIN).count() == 0


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("gstin", ["24ABCDE1234F Z5", "XXXXXXXXXXXXXXX", "24ABCDE1234F1Z55"])
def test_shared_format_validation(client, kind, gstin):
    assert client.post(endpoint(kind), json=payload(kind, gstin)).status_code == 422


@pytest.mark.parametrize("kind", KINDS)
def test_update_keep_change_remove_reuse(client, db_session, kind):
    account = client.post(endpoint(kind), json=payload(kind)).json()
    url = endpoint(kind) + str(account["id"])
    same = client.put(url, json=payload(kind, GSTIN.lower()))
    assert same.status_code == 200, same.text
    changed = client.put(url, json=payload(kind, OTHER))
    assert changed.status_code == 200, changed.text
    assert db_session.query(AccountGSTIN).one().normalized_gstin == OTHER
    assert client.post('/parties/', json=payload('Supplier', GSTIN)).status_code == 201
    removed = client.put(url, json=payload(kind, None))
    assert removed.status_code == 200, removed.text
    assert client.post('/parties/', json=payload('PURCHASE_VENDOR', OTHER)).status_code == 201


def test_conflicting_update_preserves_account(client, db_session):
    first = client.post('/customers/', json=payload('customer')).json()
    assert client.post('/parties/', json=payload('Supplier', OTHER)).status_code == 201
    response = client.put('/customers/' + str(first['id']), json=payload('customer', OTHER))
    assert response.status_code == 400
    assert client.get('/customers/' + str(first['id'])).json() == first
    assert db_session.query(AccountGSTIN).count() == 2


@pytest.mark.parametrize("source", ["customer", "party"])
@pytest.mark.parametrize("operation", ["create", "change", "remove"])
def test_failure_after_identity_flush_rolls_back(db_session, source, operation):
    service = customer if source == 'customer' else party
    create = service.create_customer if source == 'customer' else service.create_party
    update = service.update_customer if source == 'customer' else service.update_party_by_id
    create_schema = CustomerCreate if source == 'customer' else PartyCreate
    update_schema = CustomerUpdate if source == 'customer' else PartyUpdate
    kind = 'customer' if source == 'customer' else 'Supplier'
    model = Customer if source == 'customer' else Party
    account_id = None
    if operation != 'create':
        account_id = create(db_session, create_schema(**payload(kind))).id

    def fail_before_commit(session):
        session.flush()  # Account and registry changes have reached the DB.
        raise RuntimeError('injected after flush')

    event.listen(db_session, 'before_commit', fail_before_commit)
    try:
        with pytest.raises(RuntimeError, match='injected after flush'):
            if operation == 'create':
                create(db_session, create_schema(**payload(kind)))
            else:
                update(db_session, account_id, update_schema(**payload(kind, OTHER if operation == 'change' else None)))
    finally:
        event.remove(db_session, 'before_commit', fail_before_commit)
    if operation == 'create':
        assert db_session.query(model).count() == 0
        assert db_session.query(AccountGSTIN).count() == 0
    else:
        assert db_session.get(model, account_id).gstin == GSTIN
        assert db_session.get(AccountGSTIN, (source, account_id)).normalized_gstin == GSTIN


def test_inactive_owner_and_party_role_change(client):
    owner = client.post('/parties/', json=payload('Supplier')).json()
    url = '/parties/' + str(owner['id'])
    assert client.put(url, json={'party_type': 'PURCHASE_VENDOR'}).status_code == 200
    assert client.delete(url).status_code == 200
    response = client.post('/customers/', json=payload('customer'))
    assert response.status_code == 400
    assert response.json()['detail'] == DUPLICATE_GSTIN
