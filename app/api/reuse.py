from fastapi import APIRouter
from sqlalchemy.orm import sessionmaker

from app.reuse_schemas import ReuseInput, ReuseOutput
from app.services.reuse import find_reusable_suggestions


def create_reuse_router(sessions: sessionmaker) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/suggestions/reuse",
        response_model=ReuseOutput,
        status_code=200,
        summary="Find previously accepted suggestions with matching text inputs",
        description=(
            "Read-only lookup for text and symbol requests. Returns up to three "
            "unique, currently accepted sentences with source IDs. Photo-based "
            "source requests are excluded. Does not call the generation provider "
            "or create a new interaction."
        ),
    )
    def reusable_suggestions(payload: ReuseInput):
        return find_reusable_suggestions(payload, sessions)

    return router
