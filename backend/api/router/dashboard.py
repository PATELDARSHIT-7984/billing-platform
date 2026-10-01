from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.dashboard import Summary, AccountPage, PartnerPage, Trend, Transaction
from api.services import dashboard as service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def selected_range(period: Literal['today', 'week', 'month', 'financial_year', 'custom'] = 'month',
                   start_date: date | None = None, end_date: date | None = None):
    return service.date_range(period, start_date, end_date)


@router.get('/summary', response_model=Summary)
def summary(db: Session = Depends(get_db), dates=Depends(selected_range)):
    return service.summary(db, *dates)


@router.get('/accounts', response_model=AccountPage)
def accounts(type: Literal['supplier', 'customer'] = 'supplier', search: str | None = Query(None, max_length=200),
             balance_type: Literal['all', 'payable', 'advance'] = 'all',
             sort: Literal['name_asc', 'name_desc', 'balance_asc', 'balance_desc'] = 'name_asc',
             limit: int = Query(5, ge=1, le=100), skip: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return service.accounts(db, type, search, balance_type, sort, limit, skip)


@router.get('/top-partners', response_model=PartnerPage)
def top_partners(type: Literal['supplier', 'customer'] = 'supplier', search: str | None = Query(None, max_length=200),
                 limit: int = Query(5, ge=1, le=100), skip: int = Query(0, ge=0),
                 db: Session = Depends(get_db), dates=Depends(selected_range)):
    return service.top_partners(db, *dates, type, search, limit, skip)


@router.get('/trend', response_model=Trend)
def trend(request: Request, last_six_months: bool | None = None, db: Session = Depends(get_db), dates=Depends(selected_range)):
    start, end = dates
    # Bare requests keep the six-month default; explicit ranges win unless
    # the caller explicitly requests the six-month chart mode.
    if last_six_months is None:
        last_six_months = not any(key in request.query_params for key in ('period', 'start_date', 'end_date'))
    if last_six_months:
        month_index = end.year * 12 + end.month - 1 - 5
        start = date(month_index // 12, month_index % 12 + 1, 1)
    return service.trend(db, start, end)


@router.get('/recent-transactions', response_model=list[Transaction])
def recent_transactions(db: Session = Depends(get_db), dates=Depends(selected_range)):
    return service.recent_transactions(db, *dates)
