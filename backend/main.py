from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.database.database import engine
from api.database.connection import Base

from api.router import purchase_router
from api.router import party_router
from api.router import customer_router
from api.router import bill_router
from api.router import item_master_router
from api.router import purchase_return_router
from api.router import quotation_router
from api.router import sales_return_router

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        )
app.include_router(purchase_router.router)
app.include_router(party_router.router)
app.include_router(customer_router.router)  
app.include_router(bill_router.router)    
app.include_router(item_master_router.router)   
app.include_router(purchase_return_router.router)
app.include_router(quotation_router.router)
app.include_router(sales_return_router.router)

@app.get("/")

def home():
        return {"message" : "Backend Connected Successfully"}
