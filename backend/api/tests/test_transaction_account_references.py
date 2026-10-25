"""Integration tests verifying runtime unified account references on transactions (Phase 3B Step 2)."""
from datetime import date
from decimal import Decimal
import pytest

from api.model.bank import BankModel
from api.model.done_by import DoneByModel
from api.model.item_master import ItemMaster
from api.model.legacy_account_map import LegacyAccountMap
from api.schema.account_role import AccountRoleCode
from api.schema.bill import BillCreate, BillUpdate
from api.schema.customer import CustomerCreate
from api.schema.party import PartyCreate
from api.schema.party_type import PartyType
from api.schema.purchase import PurchaseCreate
from api.schema.purchase_return import PurchaseReturnCreate
from api.schema.quotation import QuotationCreate, QuotationUpdate
from api.schema.rojmel import RojmelCreate, TransactionType
from api.schema.sales_return import SalesReturnCreate
from api.services import bill, customer, party, purchase, purchase_return, quotation, sales_return, rojmel


@pytest.fixture
def env(db_session):
    cust1 = customer.create_customer(
        db_session,
        CustomerCreate(customer_name="Alpha Buyer", mobile="9825100001", address="Road", city="Surat", state="Gujarat"),
    )
    cust2 = customer.create_customer(
        db_session,
        CustomerCreate(customer_name="Beta Buyer", mobile="9825100002", address="Road", city="Surat", state="Gujarat"),
    )
    supplier = party.create_party(
        db_session,
        PartyCreate(name="Grand Supplier", party_type=PartyType.SUPPLIER, mobile="9825200001"),
    )
    vendor = party.create_party(
        db_session,
        PartyCreate(name="Direct Vendor", party_type=PartyType.PURCHASE_VENDOR, mobile="9825200002"),
    )
    item = ItemMaster(name="Ceramic Tile", hsn_code="6907", unit="Box", current_stock=500, sale_price=200)
    bank = BankModel(name="Main Bank")
    operator = DoneByModel(name="Admin User")
    db_session.add_all([item, bank, operator])
    db_session.commit()
    return cust1, cust2, supplier, vendor, item, bank, operator


def test_bill_populates_and_switches_customer_ledger(db_session, env):
    cust1, cust2, _, _, item, _, _ = env
    map1 = db_session.get(LegacyAccountMap, ("customer", cust1.id))
    map2 = db_session.get(LegacyAccountMap, ("customer", cust2.id))

    # 1. Create bill
    b = bill.create_bill(
        db_session,
        BillCreate(
            customer_id=cust1.id,
            bill_date=date.today(),
            is_gst=False,
            items=[{"item_id": item.id, "quantity": 2, "rate": 200}],
        ),
    )
    assert b.account_ledger_id == map1.account_ledger_id
    assert b.account_role == AccountRoleCode.CUSTOMER.value

    # 2. Update customer on bill
    bill.update_bill(
        db_session,
        b.bill_id,
        BillUpdate(
            customer_id=cust2.id,
            bill_date=date.today(),
            items=[{"item_id": item.id, "quantity": 2, "rate": 200}],
        ),
    )
    from api.model.bill import Bill
    bill_row = db_session.get(Bill, b.bill_id)
    assert bill_row.account_ledger_id == map2.account_ledger_id
    assert bill_row.account_role == AccountRoleCode.CUSTOMER.value


def test_sales_return_populates_customer_ledger(db_session, env):
    cust1, _, _, _, item, _, _ = env
    map1 = db_session.get(LegacyAccountMap, ("customer", cust1.id))

    sr = sales_return.create_sales_return(
        db_session,
        SalesReturnCreate(
            customer_id=cust1.id,
            return_date=date.today(),
            is_gst=False,
            return_reason="Damaged",
            items=[{"item_id": item.id, "item_name": item.name, "hsn_code": item.hsn_code, "unit": item.unit, "quantity": 1, "price": 200}],
        ),
    )
    assert sr.account_ledger_id == map1.account_ledger_id
    assert sr.account_role == AccountRoleCode.CUSTOMER.value


def test_purchase_populates_supplier_and_vendor_ledger(db_session, env):
    _, _, supplier, vendor, item, _, _ = env
    sup_map = db_session.get(LegacyAccountMap, ("party", supplier.id))
    ven_map = db_session.get(LegacyAccountMap, ("party", vendor.id))

    # Supplier purchase
    p_sup = purchase.create_purchase(
        db_session,
        PurchaseCreate(
            party_id=supplier.id,
            bill_no="SUP-BILL-101",
            bill_date=date.today(),
            is_gst=False,
            items=[{"item_name": item.name, "hsn_code": item.hsn_code, "unit": item.unit, "quantity": 5, "price": 150}],
        ),
    )
    assert p_sup.account_ledger_id == sup_map.account_ledger_id
    assert p_sup.account_role == AccountRoleCode.SUPPLIER.value

    # Purchase vendor purchase
    p_ven = purchase.create_purchase(
        db_session,
        PurchaseCreate(
            party_id=vendor.id,
            bill_no="VEN-BILL-102",
            bill_date=date.today(),
            is_gst=False,
            items=[{"item_name": item.name, "hsn_code": item.hsn_code, "unit": item.unit, "quantity": 5, "price": 150}],
        ),
    )
    assert p_ven.account_ledger_id == ven_map.account_ledger_id
    assert p_ven.account_role == AccountRoleCode.PURCHASE_VENDOR.value


def test_purchase_return_populates_party_ledger(db_session, env):
    _, _, supplier, _, item, _, _ = env
    sup_map = db_session.get(LegacyAccountMap, ("party", supplier.id))

    pr = purchase_return.create_purchase_return(
        db_session,
        PurchaseReturnCreate(
            party_id=supplier.id,
            return_date=date.today(),
            is_gst=False,
            return_reason="Defective",
            items=[{"item_id": item.id, "item_name": item.name, "hsn_code": item.hsn_code, "unit": item.unit, "quantity": 1, "price": 150}],
        ),
    )
    assert pr.account_ledger_id == sup_map.account_ledger_id
    assert pr.account_role == AccountRoleCode.SUPPLIER.value


def test_quotation_populates_account_id(db_session, env):
    cust1, cust2, _, _, item, _, _ = env
    map1 = db_session.get(LegacyAccountMap, ("customer", cust1.id))
    map2 = db_session.get(LegacyAccountMap, ("customer", cust2.id))

    q = quotation.create_quotation(
        db_session,
        QuotationCreate(
            customer_id=cust1.id,
            quotation_date=date.today(),
            is_gst=False,
            items=[{"item_id": item.id, "item_name": item.name, "hsn_code": item.hsn_code, "unit": item.unit, "quantity": 10, "price": 180}],
        ),
    )
    assert q.account_id == map1.account_id

    # Switch customer on quotation
    updated_q = quotation.update_quotation_by_id(
        db_session,
        q.id,
        QuotationUpdate(customer_id=cust2.id),
    )
    assert updated_q.account_id == map2.account_id


def test_rojmel_populates_customer_supplier_and_contra(db_session, env):
    cust1, _, supplier, _, _, bank, operator = env
    cust_map = db_session.get(LegacyAccountMap, ("customer", cust1.id))
    sup_map = db_session.get(LegacyAccountMap, ("party", supplier.id))

    # 1. Customer receipt (Cr Pay)
    r_cust = rojmel.create_rojmel(
        db_session,
        RojmelCreate(
            receipt_no="ignored",
            transaction_type=TransactionType.CR_PAY,
            customer_id=cust1.id,
            amount=Decimal("1000.00"),
            given_taken_date=date.today(),
            effective_date=date.today(),
            cash_bank_id=bank.id,
            done_by_id=operator.id,
            pay_mode="Cash",
        ),
    )
    assert r_cust.account_ledger_id == cust_map.account_ledger_id
    assert r_cust.account_role == AccountRoleCode.CUSTOMER.value

    # 2. Supplier payment (Dr Pay)
    r_sup = rojmel.create_rojmel(
        db_session,
        RojmelCreate(
            receipt_no="ignored",
            transaction_type=TransactionType.DR_PAY,
            party_id=supplier.id,
            amount=Decimal("500.00"),
            given_taken_date=date.today(),
            effective_date=date.today(),
            cash_bank_id=bank.id,
            done_by_id=operator.id,
            pay_mode="Cash",
        ),
    )
    assert r_sup.account_ledger_id == sup_map.account_ledger_id
    assert r_sup.account_role == AccountRoleCode.SUPPLIER.value

    # 3. Cash/Bank transfer (contra / no customer or party)
    r_contra = rojmel.create_rojmel(
        db_session,
        RojmelCreate(
            receipt_no="ignored",
            transaction_type=TransactionType.CASH_BANK,
            amount=Decimal("2000.00"),
            given_taken_date=date.today(),
            effective_date=date.today(),
            cash_bank_id=bank.id,
            done_by_id=operator.id,
            pay_mode="Bank",
        ),
    )
    assert r_contra.account_ledger_id is None
    assert r_contra.account_role is None
