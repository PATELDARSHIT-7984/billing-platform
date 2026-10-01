from sqlalchemy import Column, Integer, String, Boolean
from api.config.database import Base

class BankModel(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    is_active = Column(Boolean, default=True)