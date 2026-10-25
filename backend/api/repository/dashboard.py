"""Read-only dashboard queries querying unified Account and AccountLedger models with legacy fallback."""
from sqlalchemy import Numeric, cast, extract, func, or_, union_all

from api.model.account import Account, AccountLedger
from api.schema.account_role import AccountRoleCode
from api.model.party import Party
from api.model.customer import Customer
from api.model.purchase import Purchase
from api.model.purchase_return import PurchaseReturn
from api.model.bill import Bill
from api.model.sales_return import SalesReturn
from api.model.rojmel import Rojmel


DOCUMENTS = (
    ("purchase", Purchase, Purchase.bill_date, Purchase.id, Purchase.bill_no, Purchase.account_ledger_id, Party, Purchase.party_id, Party.name),
    ("sales", Bill, Bill.bill_date, Bill.bill_id, Bill.invoice_no, Bill.account_ledger_id, Customer, Bill.customer_id, Bill.customer_name),
    ("purchase_return", PurchaseReturn, PurchaseReturn.return_date, PurchaseReturn.id, PurchaseReturn.return_no, PurchaseReturn.account_ledger_id, Party, PurchaseReturn.party_id, Party.name),
    ("sales_return", SalesReturn, SalesReturn.return_date, SalesReturn.id, SalesReturn.return_no, SalesReturn.account_ledger_id, Customer, SalesReturn.customer_id, Customer.customer_name),
)


def dated(query, column, start, end):
    return query.filter(column >= start, column <= end)


def money(column):
    return cast(column, Numeric(18, 2))


def transaction_totals(db, start, end):
    return {
        key: dated(db.query(func.coalesce(func.sum(money(model.grand_total)), 0))
                   .filter(model.is_active.is_(True)), day, start, end).scalar()
        for key, model, day, *_ in DOCUMENTS
    }


def supplier_balances(db):
    party_rows = (
        db.query(Party.current_balance_type, func.sum(Party.current_balance))
        .filter(Party.party_type == "Supplier")
        .group_by(Party.current_balance_type)
        .all()
    )
    result = dict(party_rows)
    if any(result.values()):
        return result
    rows = (
        db.query(AccountLedger.current_balance_type, func.sum(AccountLedger.current_balance))
        .filter(AccountLedger.role.in_([AccountRoleCode.SUPPLIER, AccountRoleCode.PURCHASE_VENDOR]))
        .filter(AccountLedger.current_balance > 0)
        .group_by(AccountLedger.current_balance_type)
        .all()
    )
    return {direction: amount for direction, amount in rows if direction}


def customer_balances(db):
    cust_rows = (
        db.query(Customer.current_balance_type, func.sum(Customer.current_balance))
        .group_by(Customer.current_balance_type)
        .all()
    )
    result = dict(cust_rows)
    if any(result.values()):
        return result
    rows = (
        db.query(AccountLedger.current_balance_type, func.sum(AccountLedger.current_balance))
        .filter(AccountLedger.role == AccountRoleCode.CUSTOMER)
        .filter(AccountLedger.current_balance > 0)
        .group_by(AccountLedger.current_balance_type)
        .all()
    )
    return {direction: amount for direction, amount in rows if direction}


def search_accounts(query, search):
    if search and search.strip():
        pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(field.ilike(pattern, escape='\\') for field in
                                  (Account.account_name, Account.mobile, Account.address, Account.gstin))))
    return query


def _search_legacy(query, model, name, search):
    if search and search.strip():
        pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(field.ilike(pattern, escape='\\') for field in
                                  (name, model.mobile, model.address, model.gstin))))
    return query


def accounts(db, type, search, balance_type, sort, limit, skip):
    has_ledgers = db.query(AccountLedger.id).first() is not None
    if has_ledgers:
        role = AccountRoleCode.SUPPLIER if type == "supplier" else AccountRoleCode.CUSTOMER
        query = (
            db.query(Account, AccountLedger)
            .join(AccountLedger, AccountLedger.account_id == Account.id)
            .filter(AccountLedger.role == role)
        )
        if type == "supplier" and balance_type != "all":
            direction = {"payable": "Credit", "advance": "Debit"}[balance_type]
            query = query.filter(AccountLedger.current_balance_type == direction)
        elif type == "customer" and balance_type != "all":
            direction = {"receivable": "Debit", "credit": "Credit"}[balance_type]
            query = query.filter(AccountLedger.current_balance_type == direction)

        query = search_accounts(query, search)
        total = query.count()
        order = Account.account_name.desc() if sort == "name_desc" else Account.account_name.asc()
        if sort in ("balance_desc", "balance_asc"):
            order = AccountLedger.current_balance.desc() if sort == "balance_desc" else AccountLedger.current_balance.asc()

        rows = query.order_by(order, Account.id).offset(skip).limit(limit).all()

        class _DashboardAccountAdapter:
            def __init__(self, acc, led):
                self.id = acc.id
                self.name = acc.account_name
                self.customer_name = acc.account_name
                self.account_code = acc.account_code
                self.mobile = acc.mobile
                self.address = acc.address
                self.city = acc.city
                self.state = acc.state
                self.gstin = acc.gstin
                self.is_active = acc.is_active
                self.current_balance = led.current_balance
                self.current_balance_type = led.current_balance_type or "Credit"
                self.balance_type = led.current_balance_type or "Credit"

        items = [_DashboardAccountAdapter(acc, led) for acc, led in rows]
        return items, total

    # Fallback to legacy
    model, name = (Party, Party.name) if type == "supplier" else (Customer, Customer.customer_name)
    query = db.query(model)
    if type == "supplier":
        query = query.filter(Party.party_type == "Supplier")
        if balance_type != "all":
            query = query.filter(Party.current_balance_type == {"payable": "Credit", "advance": "Debit"}[balance_type])
    query = _search_legacy(query, model, name, search)
    total = query.count()
    order = name.desc() if sort == "name_desc" else name.asc()
    if sort in ("balance_desc", "balance_asc"):
        order = model.current_balance.desc() if sort == "balance_desc" else model.current_balance.asc()
    return query.order_by(order, model.id).offset(skip).limit(limit).all(), total


def top_partners(db, type, search, start, end, limit, skip):
    has_ledgers = db.query(AccountLedger.id).first() is not None
    if has_ledgers:
        role = AccountRoleCode.SUPPLIER if type == "supplier" else AccountRoleCode.CUSTOMER
        specs = [DOCUMENTS[0], DOCUMENTS[2]] if type == "supplier" else [DOCUMENTS[1], DOCUMENTS[3]]
        statements = []
        for sign, (_, doc, day, _, _, ledger_fk, *_) in zip((1, -1), specs):
            statements.append(
                dated(
                    db.query(ledger_fk.label("ledger_id"), (money(doc.grand_total) * sign).label("amount"))
                    .filter(doc.is_active.is_(True), ledger_fk.isnot(None)),
                    day, start, end
                ).statement
            )
        movements = union_all(*statements).subquery()
        net = func.sum(movements.c.amount).label("net_amount")

        query = (
            db.query(Account.id, Account.account_name.label("name"), net)
            .join(AccountLedger, AccountLedger.account_id == Account.id)
            .join(movements, movements.c.ledger_id == AccountLedger.id)
            .filter(AccountLedger.role == role)
        )
        query = search_accounts(query, search).group_by(Account.id, Account.account_name)
        total = query.count()
        return query.order_by(net.desc(), Account.account_name.asc(), Account.id).offset(skip).limit(limit).all(), total

    # Fallback to legacy
    supplier = type == "supplier"
    model, name = (Party, Party.name) if supplier else (Customer, Customer.customer_name)
    specs = [DOCUMENTS[0], DOCUMENTS[2]] if supplier else [DOCUMENTS[1], DOCUMENTS[3]]
    statements = []
    for sign, (_, doc, day, _, _, _, partner, fk, _) in zip((1, -1), specs):
        statements.append(dated(db.query(fk.label("partner_id"), (money(doc.grand_total) * sign).label("amount"))
                                .filter(doc.is_active.is_(True)), day, start, end).statement)
    movements = union_all(*statements).subquery()
    net = func.sum(movements.c.amount).label("net_amount")
    query = db.query(model.id, name.label("name"), net).join(movements, movements.c.partner_id == model.id)
    if supplier:
        query = query.filter(Party.party_type == "Supplier")
    query = _search_legacy(query, model, name, search).group_by(model.id, name)
    total = query.count()
    return query.order_by(net.desc(), name.asc(), model.id).offset(skip).limit(limit).all(), total


def monthly_totals(db, model, day, start, end):
    year, month = extract('year', day), extract('month', day)
    rows = dated(db.query(year, month, func.sum(money(model.grand_total)))
                 .filter(model.is_active.is_(True)), day, start, end).group_by(year, month).all()
    return {(int(y), int(m)): amount for y, m, amount in rows}


def recent_candidates(db, start, end, limit=5):
    result = []
    for key, model, day, pk, number, ledger_fk, partner, fk, name in DOCUMENTS:
        query = (
            db.query(
                pk.label('id'),
                number.label('number'),
                day.label('date'),
                func.coalesce(Account.account_name, name).label('name'),
                money(model.grand_total).label('amount'),
            )
            .outerjoin(AccountLedger, ledger_fk == AccountLedger.id)
            .outerjoin(Account, AccountLedger.account_id == Account.id)
            .outerjoin(partner, fk == partner.id)
            .filter(model.is_active.is_(True))
        )
        rows = dated(query, day, start, end).order_by(day.desc(), pk.desc()).limit(limit).all()
        result.extend(dict(row._mapping, type=key) for row in rows)

    rows = (
        dated(
            db.query(
                Rojmel.id,
                Rojmel.receipt_no.label('number'),
                Rojmel.effective_date.label('date'),
                func.coalesce(Account.account_name, Party.name, Customer.customer_name).label('name'),
                Rojmel.net_amount.label('amount'),
                Rojmel.transaction_type,
            )
            .outerjoin(AccountLedger, Rojmel.account_ledger_id == AccountLedger.id)
            .outerjoin(Account, AccountLedger.account_id == Account.id)
            .outerjoin(Party, Rojmel.party_id == Party.id)
            .outerjoin(Customer, Rojmel.customer_id == Customer.id),
            Rojmel.effective_date, start, end
        )
        .order_by(Rojmel.effective_date.desc(), Rojmel.id.desc())
        .limit(limit)
        .all()
    )
    for row in rows:
        entry = dict(row._mapping)
        entry['type'] = entry.pop('transaction_type').value
        result.append(entry)
    return result
