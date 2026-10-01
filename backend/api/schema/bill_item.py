from pydantic import BaseModel, Field, model_validator


# ==========================================
# Create Bill Item
# ==========================================

class BillItemCreate(BaseModel):

    item_id: int

    quantity: int = Field(gt=0)

    # Optional for legacy callers; edits resolve missing values from the invoice.
    bill_item_id: int | None = Field(default=None, gt=0)
    rate: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    disc_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    cgst: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    sgst: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    igst: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_tax_inputs(self):
        taxes = (self.cgst, self.sgst, self.igst)
        if any(value is not None for value in taxes):
            if any(value is None for value in taxes):
                raise ValueError("Provide cgst, sgst and igst together")
            if self.igst > 0 and (self.cgst > 0 or self.sgst > 0):
                raise ValueError("IGST cannot be combined with CGST or SGST")
        return self


# ==========================================
# Bill Item Response
# ==========================================

class BillItemResponse(BaseModel):

    bill_item_id: int

    item_id: int

    item_name: str

    brand_name: str | None = None

    unit: str

    hsn_code: str

    quantity: int

    rate: float

    discount_amount: float = 0.0

    taxable_amount: float

    gst_percent: float

    cgst_percent: float

    sgst_percent: float

    igst_percent: float

    cgst_amount: float

    sgst_amount: float

    igst_amount: float

    line_total: float

    class Config:
        from_attributes = True
