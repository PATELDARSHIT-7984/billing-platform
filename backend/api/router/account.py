"""FastAPI router for unified Account management, global search, settlement, and contra operations."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies.dependencies import get_db
from api.schema.account import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    AccountRoleInput,
    AccountNetSettlementResponse,
    AccountContraOffsetRequest,
)
from api.schema.account_role import AccountRoleCode
from api.schema.pagination import HistoryPage
from api.services import account as account_service

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(account_in: AccountCreate, db: Session = Depends(get_db)):
    """Create a new unified account with one or more roles and initial opening balances."""
    return account_service.create_account(db, account_in)


@router.get("/", response_model=HistoryPage[AccountResponse] | list[AccountResponse])
def get_all_accounts(
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Global search by party name, address, city, mobile, code, GSTIN"),
    role: Optional[AccountRoleCode] = Query(None, description="Filter by role (CUSTOMER, SUPPLIER, PURCHASE_VENDOR)"),
    page: Optional[int] = Query(1, ge=1, description="Page number (default 1)"),
    page_size: int = Query(10, ge=1, le=200, description="Items per page (default 10)"),
    skip: Optional[int] = Query(None, ge=0, description="Optional raw offset for array responses"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Optional raw limit for array responses"),
):
    """Search and paginate accounts. Default is 10 items per page with global search by name and address."""
    if skip is not None and limit is not None:
        return account_service.get_all_accounts(db, search=search, role=role, skip=skip, limit=limit)

    actual_page = page or 1
    total = account_service.get_all_accounts(db, search=search, role=role, count_only=True)
    items = account_service.get_all_accounts(
        db,
        search=search,
        role=role,
        skip=(actual_page - 1) * page_size,
        limit=page_size,
    )
    return HistoryPage(items=items, total=total, page=actual_page, page_size=page_size)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    """Retrieve full account details, contact info, and active roles with ledgers."""
    return account_service.get_account_by_id(db, account_id)


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(account_id: int, account_in: AccountUpdate, db: Session = Depends(get_db)):
    """Update profile details of an existing account."""
    return account_service.update_account(db, account_id, account_in)


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """Soft-delete an account and all its active roles."""
    return account_service.delete_account(db, account_id)


@router.get("/{account_id}/settlement", response_model=AccountNetSettlementResponse)
def get_account_settlement(account_id: int, db: Session = Depends(get_db)):
    """Calculate consolidated full & final net settlement amount with per-role breakdown."""
    return account_service.get_account_settlement(db, account_id)


@router.post("/{account_id}/contra-offset", response_model=AccountNetSettlementResponse)
def execute_contra_offset(
    account_id: int,
    contra_in: AccountContraOffsetRequest,
    db: Session = Depends(get_db),
):
    """Execute an atomic contra offset between two opposing roles of this account."""
    return account_service.execute_contra_offset(db, account_id, contra_in)


@router.post("/{account_id}/roles", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def add_account_role(
    account_id: int,
    role_in: AccountRoleInput,
    db: Session = Depends(get_db),
):
    """Attach an additional role (e.g. CUSTOMER, SUPPLIER) with its ledger to an existing account."""
    return account_service.add_role_to_account(db, account_id, role_in)

