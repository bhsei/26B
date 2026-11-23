import secrets

from fastapi import Depends, Request

from app.config import Settings
from app.errors import AppError
from app.services.auth import authenticate

COOKIE_NAME = "outliers_session"


def check_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/"), *settings.cors_origins}
    if origin is not None and origin not in allowed:
        raise AppError(403, "This request origin is not allowed.", "CSRF_FAILED")
    if request.headers.get("sec-fetch-site") == "cross-site" and origin not in allowed:
        raise AppError(403, "This request origin is not allowed.", "CSRF_FAILED")


def make_auth_dependencies(sessions, settings: Settings):
    def current_user(request: Request):
        return authenticate(request.cookies.get(COOKIE_NAME), sessions, settings)

    def authenticated_write(request: Request, user=Depends(current_user)):
        check_origin(request, settings)
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied.encode("utf-8"), user.csrf_token.encode("utf-8")):
            raise AppError(403, "Refresh the page and try again.", "CSRF_FAILED")
        return user

    return current_user, authenticated_write
