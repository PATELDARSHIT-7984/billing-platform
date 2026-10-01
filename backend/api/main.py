from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.config.exceptions import AppException
from api.config.settings import FRONTEND_ORIGINS
from api.config.exception_handlers import (
    app_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

from api.router.bank import router as bank_router
from api.router.dashboard import router as dashboard_router
from api.router.bill import router as bill_router
from api.router.company_profile import router as company_profile_router
from api.router.customer import router as customer_router
from api.router.done_by import router as done_by_router
from api.router.item_master import router as item_master_router
from api.router.party import router as party_router
from api.router.purchase import router as purchase_router
from api.router.purchase_return import router as purchase_return_router
from api.router.quotation import router as quotation_router
from api.router.rojmel import router as rojmel_router
from api.router.sales_return import router as sales_return_router

app = FastAPI(title="Billing API")

# Exact browser origins come from environment configuration. This is not authentication.
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every error path (business-rule exceptions, "not found"/"already exists"
# HTTPExceptions from the validation layer, request validation errors, and
# any unhandled exception) is normalized to the same ErrorResponse shape
# via api/utils/response.py -- see api/config/exception_handlers.py.
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

for router in (
    dashboard_router,
    bank_router,
    bill_router,
    company_profile_router,
    customer_router,
    done_by_router,
    item_master_router,
    party_router,
    purchase_router,
    purchase_return_router,
    quotation_router,
    rojmel_router,
    sales_return_router,
):
    app.include_router(router)


@app.get("/health")
def health_check():
    # Quick liveness check -- hit this to confirm the API is up and routers loaded.
    return {"status": "ok"}
