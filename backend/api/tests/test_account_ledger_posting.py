import pytest
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.model.account import Account, AccountRole, AccountLedger
from api.model.customer import Customer
from api.model.party import Party
from api.model.legacy_account_map import LegacyAccountMap
from api.schema.account_role import AccountRoleCode
from api.schema.party_type import PartyType
from api.services.account_provisioning import (
    provision_legacy_account,
    resolve_ledger_reference,
    signed_ledger_balance,
    ledger_balance_after_delta,
    apply_account_ledger_delta,
    get_account_net_settlement,
    apply_contra_offset,
)
from api.services.customer import apply_customer_balance_delta
from api.services.party import apply_party_balance_delta


def test_signed_and_delta_math_zero_balance_invariant():
    """Verify signed conversion and strict zero-balance check constraint adherence."""
    # 1. Zero balance produces None direction
    amt, direction = ledger_balance_after_delta(Decimal("0.00"), None, 0)
    assert amt == Decimal("0.00")
    assert direction is None

    # 2. Positive delta on zero becomes Credit
    amt, direction = ledger_balance_after_delta(Decimal("0.00"), None, Decimal("150.00"))
    assert amt == Decimal("150.00")
    assert direction == "Credit"

    # 3. Negative delta on zero becomes Debit
    amt, direction = ledger_balance_after_delta(Decimal("0.00"), None, Decimal("-150.00"))
    assert amt == Decimal("150.00")
    assert direction == "Debit"

    # 4. Dr 100 with +100 delta zeroes out exactly to None direction
    amt, direction = ledger_balance_after_delta(Decimal("100.00"), "Debit", Decimal("100.00"))
    assert amt == Decimal("0.00")
    assert direction is None

    # 5. Cr 100 with -100 delta zeroes out exactly to None direction
    amt, direction = ledger_balance_after_delta(Decimal("100.00"), "Credit", Decimal("-100.00"))
    assert amt == Decimal("0.00")
    assert direction is None

    # 6. Direction flips: Cr 50 with -150 delta becomes Dr 100
    amt, direction = ledger_balance_after_delta(Decimal("50.00"), "Credit", Decimal("-150.00"))
    assert amt == Decimal("100.00")
    assert direction == "Debit"


def test_customer_balance_delta_updates_account_ledger_in_lockstep(db_session: Session):
    """Applying customer delta updates both Customer and AccountLedger identically."""
    cust = Customer(
        customer_code="CUS-POST-01",
        customer_name="Test Posting Customer",
        mobile="9876543210",
        address="123 Market St",
        city="Ahmedabad",
        state="Gujarat",
        state_code="24",
        opening_balance=Decimal("0.00"),
        balance_type=None,
        current_balance=Decimal("0.00"),
        current_balance_type="Credit",
        is_active=True,
    )
    db_session.add(cust)
    db_session.flush()

    # Provision account
    account, role, ledger, mapping = provision_legacy_account(db_session, "customer", cust)
    assert ledger.current_balance == Decimal("0.00")
    assert ledger.current_balance_type is None

    # Bill created: customer owes 500 (delta = -500)
    apply_customer_balance_delta(db_session, cust.id, Decimal("-500.00"))
    db_session.flush()

    db_session.refresh(cust)
    db_session.refresh(ledger)
    assert cust.current_balance == Decimal("500.00")
    assert cust.current_balance_type == "Debit"
    assert ledger.current_balance == Decimal("500.00")
    assert ledger.current_balance_type == "Debit"

    # Customer pays 200 (delta = +200)
    apply_customer_balance_delta(db_session, cust.id, Decimal("200.00"))
    db_session.flush()

    db_session.refresh(cust)
    db_session.refresh(ledger)
    assert cust.current_balance == Decimal("300.00")
    assert cust.current_balance_type == "Debit"
    assert ledger.current_balance == Decimal("300.00")
    assert ledger.current_balance_type == "Debit"

    # Customer pays remaining 300 (delta = +300 -> zero balance)
    apply_customer_balance_delta(db_session, cust.id, Decimal("300.00"))
    db_session.flush()

    db_session.refresh(cust)
    db_session.refresh(ledger)
    assert cust.current_balance == Decimal("0.00")
    assert ledger.current_balance == Decimal("0.00")
    # Invariant: AccountLedger current_balance_type MUST be None when 0
    assert ledger.current_balance_type is None


def test_party_balance_delta_updates_account_ledger_in_lockstep(db_session: Session):
    """Applying party delta updates both Party and AccountLedger identically."""
    pty = Party(
        party_code="PTY-POST-01",
        name="Test Posting Supplier",
        party_type=PartyType.SUPPLIER,
        mobile="9876543211",
        address="456 Vendor Lane",
        city="Surat",
        state="Gujarat",
        opening_balance=Decimal("0.00"),
        balance_type="Credit",
        current_balance=Decimal("0.00"),
        current_balance_type="Credit",
        is_active=True,
    )
    db_session.add(pty)
    db_session.flush()

    account, role, ledger, mapping = provision_legacy_account(db_session, "party", pty)
    assert ledger.current_balance == Decimal("0.00")
    assert ledger.current_balance_type is None

    # Purchase made: we owe supplier 1000 (delta = +1000)
    apply_party_balance_delta(db_session, pty.id, Decimal("1000.00"))
    db_session.flush()

    db_session.refresh(pty)
    db_session.refresh(ledger)
    assert pty.current_balance == Decimal("1000.00")
    assert pty.current_balance_type == "Credit"
    assert ledger.current_balance == Decimal("1000.00")
    assert ledger.current_balance_type == "Credit"

    # Purchase return: return goods worth 400 (delta = -400)
    apply_party_balance_delta(db_session, pty.id, Decimal("-400.00"))
    db_session.flush()

    db_session.refresh(pty)
    db_session.refresh(ledger)
    assert pty.current_balance == Decimal("600.00")
    assert pty.current_balance_type == "Credit"
    assert ledger.current_balance == Decimal("600.00")
    assert ledger.current_balance_type == "Credit"

    # Pay remaining 600 via Rojmel (delta = -600 -> zero balance)
    apply_party_balance_delta(db_session, pty.id, Decimal("-600.00"))
    db_session.flush()

    db_session.refresh(pty)
    db_session.refresh(ledger)
    assert pty.current_balance == Decimal("0.00")
    assert ledger.current_balance == Decimal("0.00")
    assert ledger.current_balance_type is None


def test_get_account_net_settlement_single_role(db_session: Session):
    """Test full & final settlement calculation for single-role account."""
    account = Account(
        account_code="ACC-NET-01",
        account_name="Single Role Account",
        country_code="+91",
        mobile="9876543212",
        state="Gujarat",
        state_code="24",
    )
    db_session.add(account)
    db_session.flush()

    role = AccountRole(account_id=account.id, role=AccountRoleCode.CUSTOMER)
    db_session.add(role)
    ledger = AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.CUSTOMER,
        opening_balance=Decimal("500.00"),
        balance_type="Debit",
        current_balance=Decimal("500.00"),
        current_balance_type="Debit",
    )
    db_session.add(ledger)
    db_session.flush()

    summary = get_account_net_settlement(db_session, account.id)
    assert summary["account_id"] == account.id
    assert summary["net_amount"] == Decimal("500.00")
    assert summary["net_direction"] == "Debit"
    assert summary["settlement_status"] == "RECEIVABLE"
    assert "owes you" in summary["summary_text"]
    assert len(summary["roles"]) == 1
    assert summary["roles"][0]["role"] == "CUSTOMER"
    assert summary["roles"][0]["current_balance"] == Decimal("500.00")


def test_get_account_net_settlement_multi_role_user_scenario(db_session: Session):
    """Test user's exact specification: Supplier Dr 1000, Customer Cr 2000 -> Net Payable Cr 1000."""
    account = Account(
        account_code="ACC-MULTI-01",
        account_name="Patel Multi Role Party",
        country_code="+91",
        mobile="9876543213",
        state="Gujarat",
        state_code="24",
    )
    db_session.add(account)
    db_session.flush()

    # Supplier role: 1000 Debit (supplier owes us / advance given)
    role_supp = AccountRole(account_id=account.id, role=AccountRoleCode.SUPPLIER)
    db_session.add(role_supp)
    ledger_supp = AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.SUPPLIER,
        opening_balance=Decimal("1000.00"),
        balance_type="Debit",
        current_balance=Decimal("1000.00"),
        current_balance_type="Debit",
    )
    db_session.add(ledger_supp)

    # Customer role: 2000 Credit (we owe customer / customer paid advance)
    role_cust = AccountRole(account_id=account.id, role=AccountRoleCode.CUSTOMER)
    db_session.add(role_cust)
    ledger_cust = AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.CUSTOMER,
        opening_balance=Decimal("2000.00"),
        balance_type="Credit",
        current_balance=Decimal("2000.00"),
        current_balance_type="Credit",
    )
    db_session.add(ledger_cust)
    db_session.flush()

    summary = get_account_net_settlement(db_session, account.id)
    assert summary["total_receivable"] == Decimal("1000.00")
    assert summary["total_payable"] == Decimal("2000.00")
    assert summary["net_amount"] == Decimal("1000.00")
    assert summary["net_direction"] == "Credit"
    assert summary["settlement_status"] == "PAYABLE"
    assert "You need to pay" in summary["summary_text"]
    assert len(summary["roles"]) == 2


def test_get_account_net_settlement_fully_settled(db_session: Session):
    """Test full & final settlement when Dr and Cr balance out to 0."""
    account = Account(
        account_code="ACC-NIL-01",
        account_name="Nil Balance Party",
        country_code="+91",
        mobile="9876543214",
    )
    db_session.add(account)
    db_session.flush()

    db_session.add(AccountRole(account_id=account.id, role=AccountRoleCode.CUSTOMER))
    db_session.add(AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.CUSTOMER,
        opening_balance=Decimal("1500.00"),
        balance_type="Debit",
        current_balance=Decimal("1500.00"),
        current_balance_type="Debit",
    ))
    db_session.add(AccountRole(account_id=account.id, role=AccountRoleCode.SUPPLIER))
    db_session.add(AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.SUPPLIER,
        opening_balance=Decimal("1500.00"),
        balance_type="Credit",
        current_balance=Decimal("1500.00"),
        current_balance_type="Credit",
    ))
    db_session.flush()

    summary = get_account_net_settlement(db_session, account.id)
    assert summary["net_amount"] == Decimal("0.00")
    assert summary["net_direction"] is None
    assert summary["settlement_status"] == "SETTLED"
    assert "fully settled" in summary["summary_text"]


def test_apply_contra_offset_atomicity_and_legacy_sync(db_session: Session):
    """Test atomic contra offset between Customer and Supplier roles with legacy synchronization."""
    cust = Customer(
        customer_code="CUS-CONTRA-01",
        customer_name="Contra Partner",
        mobile="9876543215",
        address="10 Business Park",
        city="Rajkot",
        state="Gujarat",
        state_code="24",
        opening_balance=Decimal("6000.00"),
        balance_type="Debit",
        current_balance=Decimal("6000.00"),
        current_balance_type="Debit",
        is_active=True,
    )
    pty = Party(
        party_code="PTY-CONTRA-01",
        name="Contra Partner",
        party_type=PartyType.SUPPLIER,
        mobile="9876543215",
        address="10 Business Park",
        city="Rajkot",
        state="Gujarat",
        opening_balance=Decimal("10000.00"),
        balance_type="Credit",
        current_balance=Decimal("10000.00"),
        current_balance_type="Credit",
        is_active=True,
    )
    db_session.add_all([cust, pty])
    db_session.flush()

    account, _, cust_ledger, cust_map = provision_legacy_account(db_session, "customer", cust)

    # Attach supplier role to the SAME account
    supp_role = AccountRole(account_id=account.id, role=AccountRoleCode.SUPPLIER)
    db_session.add(supp_role)
    supp_ledger = AccountLedger(
        account_id=account.id,
        role=AccountRoleCode.SUPPLIER,
        opening_balance=Decimal("10000.00"),
        balance_type="Credit",
        current_balance=Decimal("10000.00"),
        current_balance_type="Credit",
    )
    db_session.add(supp_ledger)
    db_session.flush()

    supp_map = LegacyAccountMap(
        legacy_source="party",
        legacy_id=pty.id,
        account_id=account.id,
        account_role=AccountRoleCode.SUPPLIER.value,
        account_ledger_id=supp_ledger.id,
        legacy_code=pty.party_code,
        migration_revision="runtime",
        source_snapshot={},
    )
    db_session.add(supp_map)
    db_session.flush()

    # Pre-offset verification: Net is 4000 Credit
    before = get_account_net_settlement(db_session, account.id)
    assert before["net_amount"] == Decimal("4000.00")
    assert before["net_direction"] == "Credit"

    # Execute Contra Offset of 6000
    after = apply_contra_offset(
        db_session,
        account_id=account.id,
        receivable_role=AccountRoleCode.CUSTOMER,
        payable_role=AccountRoleCode.SUPPLIER,
        amount=Decimal("6000.00"),
    )

    # Net settlement is preserved: still 4000 Credit!
    assert after["net_amount"] == Decimal("4000.00")
    assert after["net_direction"] == "Credit"
    assert after["settlement_status"] == "PAYABLE"

    # Customer ledger is reduced to 0
    db_session.refresh(cust_ledger)
    db_session.refresh(supp_ledger)
    assert cust_ledger.current_balance == Decimal("0.00")
    assert cust_ledger.current_balance_type is None

    # Supplier ledger is reduced to 4000
    assert supp_ledger.current_balance == Decimal("4000.00")
    assert supp_ledger.current_balance_type == "Credit"

    # Mapped legacy tables also reflect the updated balances!
    db_session.refresh(cust)
    db_session.refresh(pty)
    assert cust.current_balance == Decimal("0.00")
    assert pty.current_balance == Decimal("4000.00")


def test_contra_offset_validations(db_session: Session):
    """Test validation errors for invalid contra offset inputs."""
    account = Account(account_code="ACC-VAL-01", account_name="Validation Party", country_code="+91")
    db_session.add(account)
    db_session.flush()

    # 1. Negative or zero amount
    with pytest.raises(HTTPException) as exc:
        apply_contra_offset(db_session, account.id, AccountRoleCode.CUSTOMER, AccountRoleCode.SUPPLIER, 0)
    assert exc.value.status_code == 400

    # 2. Same role
    with pytest.raises(HTTPException) as exc:
        apply_contra_offset(db_session, account.id, AccountRoleCode.CUSTOMER, AccountRoleCode.CUSTOMER, 100)
    assert exc.value.status_code == 400

    # 3. Missing account
    with pytest.raises(HTTPException) as exc:
        apply_contra_offset(db_session, 999999, AccountRoleCode.CUSTOMER, AccountRoleCode.SUPPLIER, 100)
    assert exc.value.status_code == 404
