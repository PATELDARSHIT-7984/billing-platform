from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException

from api.repository import dashboard as repo
from api.services.rojmel import get_rojmel_summary


def date_range(period="month", start_date=None, end_date=None, today=None):
    # Existing documents are business dates; Indian FY is April–March.
    today = today or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    if period == "custom":
        if not start_date or not end_date or start_date > end_date:
            raise HTTPException(422, "Provide a valid start and end date")
        start, end = start_date, end_date
    else:
        start = {"today": today, "week": today - timedelta(days=today.weekday()),
                 "month": today.replace(day=1),
                 "financial_year": date(today.year if today.month >= 4 else today.year - 1, 4, 1)}[period]
        end = today
    if (end - start).days > 3660:
        raise HTTPException(422, "Choose a date range of ten years or less")
    return start, end


def summary(db, start, end):
    totals = repo.transaction_totals(db, start, end)
    balances = repo.supplier_balances(db)
    cash = get_rojmel_summary(db, start_date=start, end_date=end)
    result = {f'total_{key}': value for key, value in totals.items()}
    result.update(net_sales=totals['sales'] - totals['sales_return'],
                  net_purchase=totals['purchase'] - totals['purchase_return'],
                  supplier_payable=balances.get('Credit', Decimal('0.00')),
                  supplier_advance=balances.get('Debit', Decimal('0.00')),
                  total_received=cash['total_received'], total_paid=cash['total_paid'],
                  net_cash_flow=cash['net_earning'], customer_receivable=None)
    for kind in ('sales', 'purchase'):
        result[f'{kind}_return_rate'] = ((totals[f'{kind}_return'] / totals[kind] * 100).quantize(Decimal('.01'))
                                         if totals[kind] else Decimal('0.00'))
    return dict(start_date=start, end_date=end, balances_as_of="current", **result)


def accounts(db, type="supplier", search=None, balance_type="all", sort="name_asc", limit=5, skip=0):
    rows, total = repo.accounts(db, type, search, balance_type, sort, limit, skip)
    items = [dict(id=row.id, name=row.name if type == 'supplier' else row.customer_name,
                  mobile=row.mobile, address=row.address, gstin=row.gstin, is_active=row.is_active,
                  current_balance=row.current_balance if type == 'supplier' else None,
                  balance_type=row.current_balance_type if type == 'supplier' else None) for row in rows]
    return dict(items=items, total=total, limit=limit, skip=skip)


def top_partners(db, start, end, type="supplier", search=None, limit=5, skip=0):
    rows, total = repo.top_partners(db, type, search, start, end, limit, skip)
    return dict(items=[dict(row._mapping, rank=skip + index + 1) for index, row in enumerate(rows)], total=total, limit=limit, skip=skip)


def trend(db, start, end):
    sales = repo.monthly_totals(db, repo.Bill, repo.Bill.bill_date, start, end)
    purchases = repo.monthly_totals(db, repo.Purchase, repo.Purchase.bill_date, start, end)
    months = []
    cursor = start.replace(day=1)
    while cursor <= end:
        months.append(cursor)
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return dict(start_date=start, end_date=end, labels=[m.strftime('%b %Y') for m in months],
                sales=[sales.get((m.year, m.month), Decimal('0.00')) for m in months],
                purchase=[purchases.get((m.year, m.month), Decimal('0.00')) for m in months])


def recent_transactions(db, start, end):
    return sorted(repo.recent_candidates(db, start, end), key=lambda row: (row['date'], row['id'], row['type']), reverse=True)[:5]
