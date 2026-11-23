from pathlib import Path

from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.errors import AppError
from app.models import AuthSession, Feedback, GenerationRequest, Suggestion, User
from app.providers.base import SentenceProvider


def expected_heads() -> set[str]:
    directory = Path(__file__).resolve().parents[2] / "migrations"
    return set(ScriptDirectory(str(directory)).get_heads())


def create_health_router(sessions: sessionmaker, provider: SentenceProvider) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health():
        return {"status": "ok", "provider": provider.name, "version": "0.1.0"}

    @router.get("/ready")
    def ready():
        try:
            with sessions() as db:
                current = set(MigrationContext.configure(db.connection()).get_current_heads())
                if current != expected_heads():
                    raise AppError(
                        503, "Run: python -m alembic upgrade head", "MIGRATIONS_REQUIRED"
                    )
                for model in (GenerationRequest, Suggestion, Feedback, User, AuthSession):
                    db.execute(select(model).limit(1))
        except SQLAlchemyError:
            raise AppError(
                503, "Database unavailable or migrations missing.", "DATABASE_UNAVAILABLE"
            ) from None
        return {"status": "ready"}

    return router
