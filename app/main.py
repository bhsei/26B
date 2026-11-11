from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.feedback import create_feedback_router
from app.api.health import create_health_router
from app.api.reuse import create_reuse_router
from app.api.suggestions import create_suggestions_router
from app.config import Settings
from app.database import make_database
from app.errors import register_error_handlers
from app.providers.base import SentenceProvider
from app.providers.mock import MockProvider

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, provider: SentenceProvider | None = None):
    settings = settings or Settings()
    provider = provider or MockProvider()
    engine, sessions = make_database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()

    app = FastAPI(title="The Outliers AAC API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.state.engine = engine
    app.state.sessions = sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def demo():
        return FileResponse(STATIC / "index.html")

    app.include_router(create_health_router(sessions, provider))
    app.include_router(create_suggestions_router(settings, sessions, provider))
    app.include_router(create_feedback_router(sessions))
    app.include_router(create_reuse_router(sessions))

    return app


app = create_app()
