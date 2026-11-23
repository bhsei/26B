from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import sessionmaker

from app.auth import COOKIE_NAME, check_origin
from app.auth_schemas import AuthOutput, LoginInput, UserOutput
from app.config import Settings
from app.errors import AppError
from app.services.auth import LoginLimiter, login, logout


def create_auth_router(
    sessions: sessionmaker, settings: Settings, current_user, authenticated_write
):
    router = APIRouter(prefix="/api/auth", tags=["authentication"])
    limiter = LoginLimiter(settings)

    def output(user):
        return AuthOutput(
            user=UserOutput(id=user.user_id, email=user.email), csrf_token=user.csrf_token
        )

    @router.post("/login", response_model=AuthOutput)
    def sign_in(payload: LoginInput, request: Request, response: Response):
        check_origin(request, settings)
        # Custom header + explicit CORS allow-list protect the pre-session login.
        if request.headers.get("x-requested-with") != "OutliersAAC":
            raise AppError(403, "Use the sign-in page to continue.", "CSRF_FAILED")
        limiter.check(request.client.host if request.client else "unknown")
        raw, user = login(payload.email, payload.password.get_secret_value(), sessions, settings)
        response.set_cookie(
            COOKIE_NAME,
            raw,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
            path="/",
            max_age=settings.auth_session_ttl_seconds,
        )
        return output(user)

    @router.get("/me", response_model=AuthOutput)
    def me(user=Depends(current_user)):
        return output(user)

    @router.post("/logout", status_code=204)
    def sign_out(user=Depends(authenticated_write)):
        logout(user.token_hash, sessions)
        response = Response(status_code=204)
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
        )
        return response

    return router
