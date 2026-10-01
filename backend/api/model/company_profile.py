from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func
from api.config.database import Base


class CompanyProfile(Base):
    __tablename__ = "company_profile"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, default="Your Company Name")
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    mobile = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    gstin = Column(String(15), nullable=True)
    pan_card = Column(String(10), nullable=True)
    udyam_no = Column(String(100), nullable=True)
    bank_account_name = Column(String(255), nullable=True)
    bank_account_no = Column(String(100), nullable=True)
    bank_ifsc = Column(String(50), nullable=True)
    bank_name = Column(String(255), nullable=True)
    terms_and_conditions = Column(JSON, nullable=False, default=list)
    jurisdiction_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())