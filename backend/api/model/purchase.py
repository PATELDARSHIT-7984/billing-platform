from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.config.database import Base


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    bill_no = Column(String(100), unique=True, nullable=False, index=True)
    order_no = Column(String(100), nullable=True, index=True)
    bill_date = Column(Date, nullable=False, default=func.current_date())
    due_term = Column(Integer, nullable=True)
    due_date = Column(Date, nullable=True)
    party_id = Column(Integer, ForeignKey("parties.id"), nullable=False, index=True)
    is_gst = Column(Boolean, nullable=False, default=True)
    contact_person = Column(String(150), nullable=True)
    contact_no = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    done_by = Column(String(100), nullable=True)
    brokerage = Column(Float, nullable=False, default=0.0)
    broker_remarks = Column(String(500), nullable=True)
    taxable_amount = Column(Float, nullable=False, default=0.0)
    sgst_total = Column(Float, nullable=False, default=0.0)
    cgst_total = Column(Float, nullable=False, default=0.0)
    igst_total = Column(Float, nullable=False, default=0.0)
    round_off = Column(Float, nullable=False, default=0.0)
    grand_total = Column(Float, nullable=False, default=0.0)
    delivery_date = Column(Date, nullable=True)
    transport = Column(String(200), nullable=True)
    ship_to = Column(String(200), nullable=True)
    ship_to_address = Column(String(1000), nullable=True)
    state = Column(String(100), nullable=True)
    reference = Column(String(200), nullable=True)
    remarks = Column(String(1000), nullable=True)
    show_shipping_address_on_bill = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    created_by = Column(Integer, nullable=True)

    party = relationship("Party")
    items = relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("item_master.id"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    hsn_code = Column(String(50), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    disc_percent = Column(Float, nullable=False, default=0.0)
    sgst = Column(Float, nullable=False, default=0.0)
    cgst = Column(Float, nullable=False, default=0.0)
    igst = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)

    purchase = relationship("Purchase", back_populates="items")
    item = relationship("ItemMaster")