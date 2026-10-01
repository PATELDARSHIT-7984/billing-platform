from sqlalchemy import Boolean, Column, Integer, String, Float, Date, DateTime
from sqlalchemy.sql import func
from api.config.database import Base


class ItemMaster(Base):
    __tablename__ = "item_master"

    id = Column(Integer, primary_key=True, index=True)

    # Basic
    name = Column(String, nullable=False, unique=True, index=True)
    code = Column(String, unique=True, nullable=True)
    hsn_code = Column(String, nullable=False)

    # Unit
    unit = Column(String, nullable=False)

    # Stock
    current_stock = Column(Float, default=0.0)

    # Pricing
    purchase_price = Column(Float, default=0.0)
    sale_price = Column(Float, default=0.0)
    mrp = Column(Float, default=0.0)

    # GST
    cgst = Column(Float, default=9.0)
    sgst = Column(Float, default=9.0)

    # Other
    category = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    description = Column(String, nullable=True)

    last_purchase_date = Column(Date, nullable=True)
    last_sale_date = Column(Date, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())