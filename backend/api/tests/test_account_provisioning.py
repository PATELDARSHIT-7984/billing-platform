"""Unit and integration tests for automatic Account provisioning (Phase 3B Step 1)."""
from decimal import Decimal
import pytest
from sqlalchemy import event

from api.model.account import Account, AccountRole, AccountLedger
from api.model.customer import Customer
from api.model.legacy_account_map import LegacyAccountMap
from api.model.party import Party
from api.schema.account_role import AccountRoleCode
from api.schema.customer import CustomerCreate, CustomerUpdate
from api.schema.party import PartyCreate, PartyUpdate
from api.schema.party_type import PartyType
from api.services import customer as customer_service
from api.services import party as party_service


def test_customer_creation_provisions_account_role_ledger_and_map(db_session):
    data = CustomerCreate(
        customer_name="Ramesh Patel",
        mobile="9825012345",
        email="ramesh@example.com",
        address="101 Shivalik",
        city="Ahmedabad",
        state="Gujarat",
        pincode="380015",
        state_code="24",
        opening_balance=Decimal("0.00"),
        balance_type="Credit",
    )
    created = customer_service.create_customer(db_session, data)

    # 1. Map exists
    mapping = db_session.get(LegacyAccountMap, ("customer", created.id))
    assert mapping is not None
    assert mapping.legacy_code == created.customer_code
    assert mapping.account_role == AccountRoleCode.CUSTOMER.value
    assert mapping.migration_revision == "runtime"

    # 2. Account exists and fields match
    account = db_session.get(Account, mapping.account_id)
    assert account is not None
    assert account.account_code == created.customer_code
    assert account.account_name == "Ramesh Patel"
    assert account.mobile == "9825012345"
    assert account.email == "ramesh@example.com"
    assert account.state_code == "24"
    assert account.state == "Gujarat"
    assert account.is_active is True

    # 3. Role exists
    role = db_session.query(AccountRole).filter_by(account_id=account.id, role=AccountRoleCode.CUSTOMER).one()
    assert role.is_active is True

    # 4. Zero balance rule: balance_type MUST be None when opening_balance is 0
    ledger = db_session.get(AccountLedger, mapping.account_ledger_id)
    assert ledger is not None
    assert ledger.opening_balance == Decimal("0.00")
    assert ledger.balance_type is None
    assert ledger.current_balance == Decimal("0.00")
    assert ledger.current_balance_type is None


def test_customer_creation_with_positive_balance_preserves_direction(db_session):
    data = CustomerCreate(
        customer_name="Suresh Shah",
        mobile="9825098765",
        address="C.G. Road",
        city="Ahmedabad",
        state="Gujarat",
        state_code="24",
        opening_balance=Decimal("2500.50"),
        balance_type="Debit",
    )
    created = customer_service.create_customer(db_session, data)
    mapping = db_session.get(LegacyAccountMap, ("customer", created.id))
    ledger = db_session.get(AccountLedger, mapping.account_ledger_id)

    assert ledger.opening_balance == Decimal("2500.50")
    assert ledger.balance_type == "Debit"
    assert ledger.current_balance == Decimal("2500.50")
    assert ledger.current_balance_type == "Debit"


def test_gstin_derives_state_and_pan_on_account(db_session):
    data = CustomerCreate(
        customer_name="GST Enterprise",
        mobile="9825011111",
        address="Ring Road",
        city="Surat",
        state="Gujarat",
        gstin="24AAACG1234F1Z8",
    )
    created = customer_service.create_customer(db_session, data)
    mapping = db_session.get(LegacyAccountMap, ("customer", created.id))
    account = db_session.get(Account, mapping.account_id)

    assert account.gstin == "24AAACG1234F1Z8"
    assert account.state_code == "24"
    assert account.state == "Gujarat"
    assert account.pan_card == "AAACG1234F"
    assert account.gstin_pending is False


def test_party_supplier_and_vendor_role_provisioning(db_session):
    # Supplier
    sup_data = PartyCreate(
        name="Apex Supplier",
        party_type=PartyType.SUPPLIER,
        mobile="9825022222",
        opening_balance=Decimal("1000.00"),
        balance_type="Credit",
    )
    supplier = party_service.create_party(db_session, sup_data)
    sup_map = db_session.get(LegacyAccountMap, ("party", supplier.id))
    assert sup_map.account_role == AccountRoleCode.SUPPLIER.value

    sup_account = db_session.get(Account, sup_map.account_id)
    assert sup_account.account_code == supplier.party_code
    assert sup_account.account_name == "Apex Supplier"

    sup_ledger = db_session.get(AccountLedger, sup_map.account_ledger_id)
    assert sup_ledger.opening_balance == Decimal("1000.00")
    assert sup_ledger.balance_type == "Credit"

    # Purchase Vendor
    ven_data = PartyCreate(
        name="National Vendor",
        party_type=PartyType.PURCHASE_VENDOR,
        mobile="9825033333",
        opening_balance=Decimal("0.00"),
    )
    vendor = party_service.create_party(db_session, ven_data)
    ven_map = db_session.get(LegacyAccountMap, ("party", vendor.id))
    assert ven_map.account_role == AccountRoleCode.PURCHASE_VENDOR.value

    ven_ledger = db_session.get(AccountLedger, ven_map.account_ledger_id)
    assert ven_ledger.opening_balance == Decimal("0.00")
    assert ven_ledger.balance_type is None


def test_update_customer_synchronizes_account_and_ledger(db_session):
    data = CustomerCreate(
        customer_name="Original Name",
        mobile="9825044444",
        address="Original Addr",
        city="Ahmedabad",
        state="Gujarat",
        state_code="24",
        opening_balance=Decimal("1000.00"),
        balance_type="Credit",
    )
    created = customer_service.create_customer(db_session, data)
    mapping = db_session.get(LegacyAccountMap, ("customer", created.id))

    # Update metadata and opening balance
    update_data = CustomerUpdate(
        customer_name="Updated Name",
        mobile="9825055555",
        address="Updated Addr",
        city="Ahmedabad",
        state="Gujarat",
        state_code="24",
        opening_balance=Decimal("1500.00"),
        balance_type="Debit",
    )
    customer_service.update_customer(db_session, created.id, update_data)

    account = db_session.get(Account, mapping.account_id)
    assert account.account_name == "Updated Name"
    assert account.mobile == "9825055555"

    ledger = db_session.get(AccountLedger, mapping.account_ledger_id)
    assert ledger.opening_balance == Decimal("1500.00")
    assert ledger.balance_type == "Debit"


def test_deactivate_customer_and_party_cascades_is_active(db_session):
    # Customer deactivation
    cust = customer_service.create_customer(
        db_session,
        CustomerCreate(customer_name="To Delete Cust", mobile="9825066666", address="Road", city="City", state="Gujarat"),
    )
    cust_map = db_session.get(LegacyAccountMap, ("customer", cust.id))
    customer_service.delete_customer(db_session, cust.id)

    db_session.refresh(cust)
    assert cust.is_active is False
    cust_account = db_session.get(Account, cust_map.account_id)
    assert cust_account.is_active is False
    cust_role = db_session.query(AccountRole).filter_by(account_id=cust_account.id, role=AccountRoleCode.CUSTOMER).one()
    assert cust_role.is_active is False

    # Party deactivation
    pty = party_service.create_party(
        db_session,
        PartyCreate(name="To Delete Party", mobile="9825077777"),
    )
    pty_map = db_session.get(LegacyAccountMap, ("party", pty.id))
    party_service.delete_party_by_id(db_session, pty.id)

    db_session.refresh(pty)
    assert pty.is_active is False
    pty_account = db_session.get(Account, pty_map.account_id)
    assert pty_account.is_active is False
    pty_role = db_session.query(AccountRole).filter_by(account_id=pty_account.id, role=AccountRoleCode.SUPPLIER).one()
    assert pty_role.is_active is False


def test_deactivation_via_update_sets_account_and_role_inactive(db_session):
    cust = customer_service.create_customer(
        db_session,
        CustomerCreate(customer_name="Active Cust", mobile="9825088888", address="Road", city="City", state="Gujarat"),
    )
    cust_map = db_session.get(LegacyAccountMap, ("customer", cust.id))

    # Deactivate via update
    customer_service.update_customer(
        db_session,
        cust.id,
        CustomerUpdate(
            customer_name="Active Cust",
            mobile="9825088888",
            address="Road",
            city="City",
            state="Gujarat",
            is_active=False,
        ),
    )

    cust_account = db_session.get(Account, cust_map.account_id)
    assert cust_account.is_active is False
    cust_role = db_session.query(AccountRole).filter_by(account_id=cust_account.id, role=AccountRoleCode.CUSTOMER).one()
    assert cust_role.is_active is False


def test_creation_failure_rolls_back_account_and_map(db_session):
    # If something fails right before commit, nothing persists in accounts or legacy_account_map
    def blow_up(session):
        raise RuntimeError("Simulated DB failure")

    event.listen(db_session, "before_commit", blow_up)
    try:
        with pytest.raises(RuntimeError, match="Simulated DB failure"):
            customer_service.create_customer(
                db_session,
                CustomerCreate(customer_name="Rollback Cust", mobile="9825099999", address="Road", city="City", state="Gujarat"),
            )
    finally:
        event.remove(db_session, "before_commit", blow_up)

    assert db_session.query(Customer).filter_by(customer_name="Rollback Cust").first() is None
    assert db_session.query(Account).filter_by(account_name="Rollback Cust").first() is None
    assert db_session.query(LegacyAccountMap).count() == 0
