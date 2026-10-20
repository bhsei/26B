from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.images import prepare_image
from app.providers.base import SentenceProvider
from app.schemas import GenerationOutput, SuggestionInput
from app.services.suggestions import generate


def create_suggestions_router(
    settings: Settings, sessions: sessionmaker, provider: SentenceProvider
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/suggestions", response_model=GenerationOutput, status_code=201)
    def suggestions(payload: SuggestionInput):
        return generate(payload, None, sessions, provider)

    @router.post("/api/suggestions/image", response_model=GenerationOutput, status_code=201)
    def suggestions_with_image(
        payload: Annotated[str, Form(description="JSON matching SuggestionInput", max_length=5000)],
        image: Annotated[UploadFile, File()],
    ):
        try:
            parsed = SuggestionInput.model_validate_json(payload)
        except ValidationError:
            image.file.close()
            raise HTTPException(422, "Invalid payload JSON. See SuggestionInput schema.") from None
        return generate(
            parsed, prepare_image(image, settings.max_image_bytes), sessions, provider
        )

    return router
