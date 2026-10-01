from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Boolean,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.config.database import Base


class BillItem(Base):
    __tablename__ = "bill_item"

    # -------------------------
    # Primary Key
    # -------------------------

    bill_item_id = Column(Integer, primary_key=True, index=True)

    bill_id = Column(Integer,ForeignKey("bill.bill_id"),nullable=False)

    item_id = Column(Integer,ForeignKey("item_master.id"),nullable=False)

    # -------------------------
    # Product Snapshot
    # -------------------------

    item_name = Column(String(150), nullable=False)

    brand_name = Column(String(100), nullable=True)

    hsn_code = Column(String(20), nullable=False)

    unit = Column(String(20), nullable=False)

    # -------------------------
    # Quantity
    # -------------------------

    quantity = Column(Integer, nullable=False)

    # -------------------------
    # Price Snapshot
    # -------------------------

    rate = Column(Float, nullable=False)

    discount_amount = Column(Float, default=0.0)

    taxable_amount = Column(Float, nullable=False)

    # -------------------------
    # GST Snapshot
    # -------------------------

    gst_percent = Column(Float, nullable=False)

    cgst_percent = Column(Float, default=0.0)

    sgst_percent = Column(Float, default=0.0)

    igst_percent = Column(Float, default=0.0)

    cgst_amount = Column(Float, default=0.0)

    sgst_amount = Column(Float, default=0.0)

    igst_amount = Column(Float, default=0.0)

    # -------------------------
    # Final Line Total
    # -------------------------

    line_total = Column(Float, nullable=False)

    # -------------------------
    # Status
    # -------------------------

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True),server_default=func.now())

    # -------------------------
    # Relationships
    # -------------------------

    bill = relationship("Bill",back_populates="bill_items")

    item = relationship("ItemMaster")