from fastapi import APIRouter
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.errors import AppError
from app.models import GenerationRequest
from app.providers.base import SentenceProvider


def create_health_router(sessions: sessionmaker, provider: SentenceProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok", "provider": provider.name, "version": "0.1.0"}

    @router.get("/ready")
    def ready():
        try:
            with sessions() as db:
                db.execute(select(GenerationRequest.id).limit(1))
                revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if revision != "0001":
                    raise AppError(
                        503, "Run: python -m alembic upgrade head", "MIGRATIONS_REQUIRED"
                    )
        except SQLAlchemyError:
            raise AppError(
                503, "Database unavailable or migrations missing.", "DATABASE_UNAVAILABLE"
            ) from None
        return {"status": "ready"}

    return router
