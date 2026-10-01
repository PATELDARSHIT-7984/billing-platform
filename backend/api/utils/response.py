from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    # Standard shape for every 2xx response in the API: success=True,
    # the HTTP status code, a human-readable message, and the actual
    # payload in `data` (a single object, a list, or None).
    success: bool = True
    status_code: int
    message: str = "Operation successful"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    # Standard shape for every 4xx/5xx response: success=False, the
    # HTTP status code, a human-readable message, and optional
    # structured `details` (e.g. per-field validation errors).
    success: bool = False
    status_code: int
    message: str
    details: Optional[List[Any]] = None


def success(data: Any = None, message: str = "Operation successful", status_code: int = 200) -> dict:
    # Shortcut for building a SuccessResponse dict without importing
    # the class everywhere -- use in routers: return success(data=item).
    return SuccessResponse(status_code=status_code, message=message, data=data).model_dump()


def error(message: str, status_code: int = 400, details: Optional[List[Any]] = None) -> dict:
    # Shortcut for building an ErrorResponse dict, mirroring success()
    # above. Mainly used by the global exception handlers.
    return ErrorResponse(status_code=status_code, message=message, details=details).model_dump()
