from fastapi import Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from api.config.exceptions import AppException
from api.utils.response import error


async def app_exception_handler(request: Request, exc: AppException):
    # Handles custom business-logic exceptions raised anywhere in the app.
    return JSONResponse(status_code=exc.status_code, content=error(message=exc.message, status_code=exc.status_code, details=exc.details))


async def http_exception_handler(request: Request, exc: HTTPException):
    # Handles fastapi.HTTPException -- this is what the validation layer
    # raises (see api/validation/*.py) for things like "not found" or
    # "already exists". Without this handler those responses would come
    # back as FastAPI's bare {"detail": "..."} instead of matching the
    # rest of the API's error shape.
    return JSONResponse(status_code=exc.status_code, content=error(message=str(exc.detail), status_code=exc.status_code))


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Handles Pydantic request-body validation errors (missing/invalid fields).
    details = [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error(message="Data Validation Error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details),
    )


async def general_exception_handler(request: Request, exc: Exception):
    # Safety net for anything unhandled -- never leak a raw traceback to the client.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(message="An unexpected internal server error occurred.", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR),
    )
