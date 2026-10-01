from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime
)
from sqlalchemy.sql import func
from api.config.database import Base


class Customer(Base):

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)

    customer_name = Column(String, nullable=False, index=True)
    customer_code = Column(String(30), unique=True, nullable=True, index=True)

    mobile = Column(String(10), nullable=False)

    email = Column(String, nullable=True)

    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)

    pincode = Column(String, nullable=True)

    gstin = Column(String(15), nullable=True, unique=True)
    pan_card = Column(String(10), nullable=True, unique=True)
    state_code = Column(String(2), nullable=True)

    remarks = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())