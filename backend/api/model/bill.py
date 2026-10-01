from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.config.database import Base


class Bill(Base):
    __tablename__ = "bill"

    bill_id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    invoice_no = Column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
    )

    bill_date = Column(
        Date,
        nullable=False,
    )

    # Added for Sales Edit
    due_term = Column(
        Integer,
        nullable=True,
    )

    due_date = Column(
        Date,
        nullable=True,
    )

    is_interstate = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Buyer snapshot
    customer_name = Column(
        String(100),
        nullable=False,
    )

    mobile = Column(
        String(15),
        nullable=False,
    )

    email = Column(
        String(100),
        nullable=True,
    )

    address = Column(
        String(255),
        nullable=False,
    )

    city = Column(
        String(100),
        nullable=False,
    )

    state = Column(
        String(100),
        nullable=False,
    )

    pincode = Column(
        String(10),
        nullable=True,
    )

    buyer_gstin = Column(
        String(15),
        nullable=True,
    )

    buyer_pan = Column(
        String(10),
        nullable=True,
    )

    buyer_state_code = Column(
        String(2),
        nullable=True,
    )

    # Added for Sales Edit
    done_by = Column(
        String(100),
        nullable=True,
    )

    brokerage = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    broker_remarks = Column(
        String(500),
        nullable=True,
    )

    # Invoice summary
    total_boxes = Column(
        Integer,
        nullable=False,
    )

    subtotal = Column(
        Float,
        nullable=False,
    )

    discount_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    taxable_amount = Column(
        Float,
        nullable=False,
    )

    cgst_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    sgst_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    igst_amount = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    grand_total = Column(
        Float,
        nullable=False,
    )

    amount_in_words = Column(
        String(300),
        nullable=False,
    )

    # Added for Sales Edit
    delivery_date = Column(
        Date,
        nullable=True,
    )

    ship_to = Column(
        String(200),
        nullable=True,
    )

    ship_to_address = Column(
        String(500),
        nullable=True,
    )

    shipping_state = Column(
        String(100),
        nullable=True,
    )

    transport = Column(
        String(200),
        nullable=True,
    )

    reference = Column(
        String(200),
        nullable=True,
    )

    remarks = Column(
        String(500),
        nullable=True,
    )

    show_shipping_address_on_bill = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer = relationship("Customer")

    bill_items = relationship(
        "BillItem",
        back_populates="bill",
        cascade="all, delete-orphan",
    )