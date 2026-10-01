from pydantic import BaseModel, ConfigDict
from typing import Optional

class BankBase(BaseModel):
    name: str

class BankCreate(BankBase):
    pass

class BankUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class BankResponse(BankBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)