"""Read-only dashboard queries. Current balances deliberately have no date filter."""
from sqlalchemy import Numeric, cast, extract, func, or_, union_all

from api.model.party import Party
from api.model.customer import Customer
from api.model.purchase import Purchase
from api.model.purchase_return import PurchaseReturn
from api.model.bill import Bill
from api.model.sales_return import SalesReturn
from api.model.rojmel import Rojmel


DOCUMENTS = (
    ("purchase", Purchase, Purchase.bill_date, Purchase.id, Purchase.bill_no, Party, Purchase.party_id, Party.name),
    ("sales", Bill, Bill.bill_date, Bill.bill_id, Bill.invoice_no, Customer, Bill.customer_id, Bill.customer_name),
    ("purchase_return", PurchaseReturn, PurchaseReturn.return_date, PurchaseReturn.id, PurchaseReturn.return_no, Party, PurchaseReturn.party_id, Party.name),
    ("sales_return", SalesReturn, SalesReturn.return_date, SalesReturn.id, SalesReturn.return_no, Customer, SalesReturn.customer_id, Customer.customer_name),
)


def dated(query, column, start, end):
    return query.filter(column >= start, column <= end)


def money(column):
    # Transaction models store Float; cast each authoritative document total
    # before SQL summation so subsequent business arithmetic uses Decimal.
    return cast(column, Numeric(18, 2))


def transaction_totals(db, start, end):
    return {
        key: dated(db.query(func.coalesce(func.sum(money(model.grand_total)), 0))
                   .filter(model.is_active.is_(True)), day, start, end).scalar()
        for key, model, day, *_ in DOCUMENTS
    }


def supplier_balances(db):
    return dict(db.query(Party.current_balance_type, func.sum(Party.current_balance))
                .filter(Party.party_type == "Supplier")
                .group_by(Party.current_balance_type).all())


def search_accounts(query, model, name, search):
    if search and search.strip():
        pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(*(field.ilike(pattern, escape='\\') for field in
                                  (name, model.mobile, model.address, model.gstin))))
    return query


def accounts(db, type, search, balance_type, sort, limit, skip):
    model, name = (Party, Party.name) if type == "supplier" else (Customer, Customer.customer_name)
    query = db.query(model)
    if type == "supplier":
        query = query.filter(Party.party_type == "Supplier")
        if balance_type != "all":
            query = query.filter(Party.current_balance_type == {"payable": "Credit", "advance": "Debit"}[balance_type])
    query = search_accounts(query, model, name, search)
    total = query.count()
    order = name.desc() if sort == "name_desc" else name.asc()
    if type == "supplier" and sort in ("balance_desc", "balance_asc"):
        order = Party.current_balance.desc() if sort == "balance_desc" else Party.current_balance.asc()
    return query.order_by(order, model.id).offset(skip).limit(limit).all(), total


def top_partners(db, type, search, start, end, limit, skip):
    supplier = type == "supplier"
    model, name = (Party, Party.name) if supplier else (Customer, Customer.customer_name)
    specs = [DOCUMENTS[0], DOCUMENTS[2]] if supplier else [DOCUMENTS[1], DOCUMENTS[3]]
    statements = []
    for sign, (_, doc, day, _, _, _, partner_id, _) in zip((1, -1), specs):
        statements.append(dated(db.query(partner_id.label("partner_id"), (money(doc.grand_total) * sign).label("amount"))
                                .filter(doc.is_active.is_(True)), day, start, end).statement)
    movements = union_all(*statements).subquery()
    net = func.sum(movements.c.amount).label("net_amount")
    query = db.query(model.id, name.label("name"), net).join(movements, movements.c.partner_id == model.id)
    if supplier:
        query = query.filter(Party.party_type == "Supplier")
    query = search_accounts(query, model, name, search).group_by(model.id, name)
    total = query.count()
    return query.order_by(net.desc(), name.asc(), model.id).offset(skip).limit(limit).all(), total


def monthly_totals(db, model, day, start, end):
    year, month = extract('year', day), extract('month', day)
    rows = dated(db.query(year, month, func.sum(money(model.grand_total)))
                 .filter(model.is_active.is_(True)), day, start, end).group_by(year, month).all()
    return {(int(y), int(m)): amount for y, m, amount in rows}


def recent_candidates(db, start, end, limit=5):
    result = []
    for key, model, day, pk, number, partner, fk, name in DOCUMENTS:
        query = db.query(pk.label('id'), number.label('number'), day.label('date'), name.label('name'), money(model.grand_total).label('amount'))
        rows = dated(query.outerjoin(partner, fk == partner.id).filter(model.is_active.is_(True)), day, start, end).order_by(day.desc(), pk.desc()).limit(limit).all()
        result.extend(dict(row._mapping, type=key) for row in rows)
    rows = dated(db.query(Rojmel.id, Rojmel.receipt_no.label('number'), Rojmel.effective_date.label('date'), Party.name, Rojmel.net_amount.label('amount'), Rojmel.transaction_type)
                 .outerjoin(Party, Rojmel.party_id == Party.id), Rojmel.effective_date, start, end).order_by(Rojmel.effective_date.desc(), Rojmel.id.desc()).limit(limit).all()
    for row in rows:
        entry = dict(row._mapping)
        entry['type'] = entry.pop('transaction_type').value
        result.append(entry)
    return result
