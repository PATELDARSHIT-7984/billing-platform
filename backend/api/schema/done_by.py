from pydantic import BaseModel, ConfigDict
from typing import Optional

class EmployeeBase(BaseModel):
    name: str

class EmployeeCreate(EmployeeBase):
    pass

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class EmployeeResponse(EmployeeBase):
    id: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# router/done_by.py imports DoneByCreate/DoneByUpdate/DoneByResponse, but
# every class in this file is named Employee* -- that import would raise
# ImportError the moment this router is registered. Aliasing here instead
# of renaming the Employee* classes, since other code may already depend
# on those names and this is a pure additive fix.
DoneByCreate = EmployeeCreate
DoneByUpdate = EmployeeUpdate
DoneByResponse = EmployeeResponse