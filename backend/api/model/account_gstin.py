from sqlalchemy import Column, Integer, String, UniqueConstraint

from api.config.database import Base


class AccountGSTIN(Base):
    __tablename__ = "account_gstin_registry"
    __table_args__ = (UniqueConstraint("normalized_gstin", name="uq_account_gstin"),)

    account_source = Column(String(30), primary_key=True)
    account_id = Column(Integer, primary_key=True)
    normalized_gstin = Column(String(15), nullable=False)
