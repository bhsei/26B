import json

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, detail: str, error_code: str, *, headers=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    response = await request_validation_exception_handler(request, exc)
    content = json.loads(response.body)
    # Validation errors must never echo submitted passwords or session credentials.
    for item in content.get("detail", []):
        item.pop("input", None)
    content["error_code"] = "VALIDATION_ERROR"
    return JSONResponse(status_code=response.status_code, content=content)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
