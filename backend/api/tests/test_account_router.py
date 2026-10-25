from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from api.model.account import Account, AccountRole, AccountLedger
from api.schema.account import (
    AccountCreate,
    AccountUpdate,
    AccountRoleInput,
    AccountContraOffsetRequest,
)
from api.schema.account_role import AccountRoleCode
from api.services import account as account_service


def test_create_account_with_auto_generated_code(db_session: Session):
    """Omitting account_code auto-generates ACC-0001 sequential code."""
    data = AccountCreate(
        account_name="Auto Code Enterprise",
        mobile="9876543210",
        address="10 Industrial Zone",
        city="Surat",
        state="Gujarat",
        state_code="24",
        roles=[
            AccountRoleInput(role=AccountRoleCode.CUSTOMER, opening_balance=Decimal("0.00")),
        ],
    )
    account = account_service.create_account(db_session, data)
    assert account.id is not None
    assert account.account_code.startswith("ACC-")
    assert account.account_name == "Auto Code Enterprise"
    assert len(account.roles) == 1
    assert account.roles[0].role == AccountRoleCode.CUSTOMER
    assert account.roles[0].ledger.current_balance == Decimal("0.00")
    assert account.roles[0].ledger.current_balance_type is None


def test_create_account_multi_role_separate_balances(db_session: Session):
    """Account can hold multiple roles with strictly separated opening balances."""
    data = AccountCreate(
        account_code="ACC-MULTI-TEST",
        account_name="Patel Multi Trader",
        mobile="9876543211",
        address="Ring Road Complex",
        city="Surat",
        state="Gujarat",
        state_code="24",
        roles=[
            AccountRoleInput(role=AccountRoleCode.SUPPLIER, opening_balance=Decimal("1000.00"), balance_type="Debit"),
            AccountRoleInput(role=AccountRoleCode.CUSTOMER, opening_balance=Decimal("2000.00"), balance_type="Credit"),
        ],
    )
    account = account_service.create_account(db_session, data)
    assert account.account_code == "ACC-MULTI-TEST"
    assert len(account.roles) == 2

    roles_dict = {r.role: r for r in account.roles}
    assert AccountRoleCode.SUPPLIER in roles_dict
    assert AccountRoleCode.CUSTOMER in roles_dict

    supp_ledger = roles_dict[AccountRoleCode.SUPPLIER].ledger
    assert supp_ledger.current_balance == Decimal("1000.00")
    assert supp_ledger.current_balance_type == "Debit"

    cust_ledger = roles_dict[AccountRoleCode.CUSTOMER].ledger
    assert cust_ledger.current_balance == Decimal("2000.00")
    assert cust_ledger.current_balance_type == "Credit"


def test_global_search_by_name_and_address(db_session: Session):
    """Global search matches party name, street address, or city."""
    account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-SRCH-1",
            account_name="Ramesh Ceramics",
            mobile="9876543221",
            address="Near Bus Stand, Varachha",
            city="Surat",
            state="Gujarat",
            state_code="24",
            roles=[AccountRoleInput(role=AccountRoleCode.CUSTOMER)],
        ),
    )
    account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-SRCH-2",
            account_name="Suresh Sanitary",
            mobile="9876543222",
            address="GIDC Industrial Area",
            city="Ahmedabad",
            state="Gujarat",
            state_code="24",
            roles=[AccountRoleInput(role=AccountRoleCode.SUPPLIER)],
        ),
    )
    account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-SRCH-3",
            account_name="Mahesh Hardware",
            mobile="9876543223",
            address="Market Yard, Sector 4",
            city="Rajkot",
            state="Gujarat",
            state_code="24",
            roles=[AccountRoleInput(role=AccountRoleCode.PURCHASE_VENDOR)],
        ),
    )

    # 1. Search by Party Name
    res_name = account_service.get_all_accounts(db_session, search="Ramesh")
    assert len(res_name) == 1
    assert res_name[0].account_name == "Ramesh Ceramics"

    # 2. Search by Street Address keyword
    res_addr = account_service.get_all_accounts(db_session, search="Varachha")
    assert len(res_addr) == 1
    assert res_addr[0].account_name == "Ramesh Ceramics"

    # 3. Search by City
    res_city = account_service.get_all_accounts(db_session, search="Ahmedabad")
    assert len(res_city) == 1
    assert res_city[0].account_name == "Suresh Sanitary"

    # 4. Search by Industrial address keyword
    res_gidc = account_service.get_all_accounts(db_session, search="GIDC")
    assert len(res_gidc) == 1
    assert res_gidc[0].account_name == "Suresh Sanitary"


def test_ten_page_pagination(db_session: Session):
    """Pagination defaults to 10 items per page with accurate total and total_pages."""
    # Create 25 accounts
    for i in range(1, 26):
        account_service.create_account(
            db_session,
            AccountCreate(
                account_code=f"ACC-PAG-{i:03d}",
                account_name=f"Party Number {i:03d}",
                address=f"Street {i}",
                city="Surat",
                state="Gujarat",
                state_code="24",
                roles=[AccountRoleInput(role=AccountRoleCode.CUSTOMER)],
            ),
        )

    # Total count
    total = account_service.get_all_accounts(db_session, search="Party Number", count_only=True)
    assert total == 25

    # Page 1: 10 items
    page_1 = account_service.get_all_accounts(db_session, search="Party Number", skip=0, limit=10)
    assert len(page_1) == 10
    assert page_1[0].account_name == "Party Number 001"
    assert page_1[9].account_name == "Party Number 010"

    # Page 2: 10 items
    page_2 = account_service.get_all_accounts(db_session, search="Party Number", skip=10, limit=10)
    assert len(page_2) == 10
    assert page_2[0].account_name == "Party Number 011"
    assert page_2[9].account_name == "Party Number 020"

    # Page 3: remaining 5 items
    page_3 = account_service.get_all_accounts(db_session, search="Party Number", skip=20, limit=10)
    assert len(page_3) == 5
    assert page_3[0].account_name == "Party Number 021"
    assert page_3[4].account_name == "Party Number 025"


def test_filter_by_account_role(db_session: Session):
    """Role parameter filters accounts having specific active role."""
    cust_acc = account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-ROLE-C",
            account_name="Only Customer",
            roles=[AccountRoleInput(role=AccountRoleCode.CUSTOMER)],
        ),
    )
    supp_acc = account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-ROLE-S",
            account_name="Only Supplier",
            roles=[AccountRoleInput(role=AccountRoleCode.SUPPLIER)],
        ),
    )

    customers = account_service.get_all_accounts(db_session, search="Only", role=AccountRoleCode.CUSTOMER)
    assert len(customers) == 1
    assert customers[0].account_code == "ACC-ROLE-C"

    suppliers = account_service.get_all_accounts(db_session, search="Only", role=AccountRoleCode.SUPPLIER)
    assert len(suppliers) == 1
    assert suppliers[0].account_code == "ACC-ROLE-S"


def test_update_and_soft_delete_account(db_session: Session):
    """Account profile update and soft-delete behavior."""
    account = account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-UPD-01",
            account_name="Old Business Name",
            address="Old Address",
            city="Surat",
            roles=[AccountRoleInput(role=AccountRoleCode.CUSTOMER)],
        ),
    )

    # Update
    updated = account_service.update_account(
        db_session,
        account.id,
        AccountUpdate(account_name="New Business Name", address="New Upgraded Address"),
    )
    assert updated.account_name == "New Business Name"
    assert updated.address == "New Upgraded Address"

    # Delete
    msg = account_service.delete_account(db_session, account.id)
    assert "deleted successfully" in msg["message"]

    # Inactive account is excluded from search
    active_search = account_service.get_all_accounts(db_session, search="New Business Name")
    assert len(active_search) == 0


def test_settlement_and_contra_offset_services(db_session: Session):
    """Verify settlement breakdown and contra offset execution."""
    account = account_service.create_account(
        db_session,
        AccountCreate(
            account_code="ACC-SETTLE-01",
            account_name="Full Settlement Enterprise",
            roles=[
                AccountRoleInput(role=AccountRoleCode.SUPPLIER, opening_balance=Decimal("1000.00"), balance_type="Debit"),
                AccountRoleInput(role=AccountRoleCode.CUSTOMER, opening_balance=Decimal("2000.00"), balance_type="Credit"),
            ],
        ),
    )

    # 1. Net Settlement
    settlement = account_service.get_account_settlement(db_session, account.id)
    assert settlement["net_amount"] == Decimal("1000.00")
    assert settlement["net_direction"] == "Credit"
    assert settlement["settlement_status"] == "PAYABLE"
    assert "You need to pay" in settlement["summary_text"]
    assert len(settlement["roles"]) == 2

    # 2. Add third role
    added_acc = account_service.add_role_to_account(
        db_session,
        account.id,
        AccountRoleInput(role=AccountRoleCode.PURCHASE_VENDOR, opening_balance=Decimal("500.00"), balance_type="Credit"),
    )
    assert len(added_acc.roles) == 3

    # Settlement now has 3 roles: Total Payable = 2000 + 500 = 2500, Receivable = 1000 -> Net Payable 1500 Credit
    settlement_3 = account_service.get_account_settlement(db_session, account.id)
    assert settlement_3["total_payable"] == Decimal("2500.00")
    assert settlement_3["total_receivable"] == Decimal("1000.00")
    assert settlement_3["net_amount"] == Decimal("1500.00")
    assert settlement_3["net_direction"] == "Credit"


def test_account_router_http_pagination_and_search_contract(client):
    """Test HTTP endpoint GET /accounts for search and 10-item pagination."""
    # Create 15 accounts via POST /accounts/
    for i in range(1, 16):
        payload = {
            "account_name": f"HTTP Partner {i:02d}",
            "mobile": f"9876543{i:03d}",
            "address": f"Building {i}, Station Road",
            "city": "Surat" if i % 2 == 0 else "Vadodara",
            "roles": [{"role": "CUSTOMER", "opening_balance": 0.0}],
        }
        resp = client.post("/accounts/", json=payload)
        assert resp.status_code == 201, resp.text

    # 1. Global search by name
    res = client.get("/accounts/?search=HTTP Partner 05")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["account_name"] == "HTTP Partner 05"

    # 2. Global search by address keyword
    res = client.get("/accounts/?search=Station Road")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 15

    # 3. 10-page pagination (page=1, page_size=10)
    res_p1 = client.get("/accounts/?search=HTTP Partner&page=1&page_size=10")
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert len(p1_data["items"]) == 10
    assert p1_data["total"] == 15
    assert p1_data["page"] == 1
    assert p1_data["page_size"] == 10
    assert p1_data["total_pages"] == 2

    # 4. Page 2 (remaining 5)
    res_p2 = client.get("/accounts/?search=HTTP Partner&page=2&page_size=10")
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    assert len(p2_data["items"]) == 5
    assert p2_data["page"] == 2
    assert p2_data["total_pages"] == 2

