from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config.database import engine
from api.config.database import Base
from api.config.exceptions import AppException
from fastapi.exceptions import RequestValidationError
from api.config.exception_handlers import (
    app_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from api.router import purchase
from api.router import party
from api.router import customer
from api.router import bill
from api.router import item_master
from api.router import purchase_return
from api.router import quotation
from api.router import sales_return
from api.router import dashboard

pytest_plugins = (
    "api.tests.fixtures.party_fixtures",
)

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        )
app.include_router(purchase.router)
app.include_router(dashboard.router)
app.include_router(party.router)
app.include_router(customer.router)  
app.include_router(bill.router)    
app.include_router(item_master.router)   
app.include_router(purchase_return.router)
app.include_router(quotation.router)
app.include_router(sales_return.router)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

@app.get("/")

def home():
        return {"message" : "Backend Connected Successfully"}
