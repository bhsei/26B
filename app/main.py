from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import make_database
from app.images import prepare_image
from app.models import Feedback, GenerationRequest, Suggestion, utc_now
from app.providers.base import GeneratedSentences, ProviderUnavailable, SentenceProvider
from app.providers.mock import MockProvider
from app.schemas import FeedbackInput, GenerationOutput, SuggestionInput, SuggestionOutput

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

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": provider.name, "version": "0.1.0"}

    @app.get("/ready")
    def ready():
        try:
            with sessions() as db:
                db.execute(select(GenerationRequest.id).limit(1))
                revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if revision != "0001":
                    raise HTTPException(503, "Run: python -m alembic upgrade head")
        except SQLAlchemyError:
            raise HTTPException(503, "Database unavailable or migrations missing.") from None
        return {"status": "ready"}

    def generate(payload: SuggestionInput, image: bytes | None):
        with sessions() as db:
            excluded = []
            parent = str(payload.parent_request_id) if payload.parent_request_id else None
            current = parent
            depth = 0
            while current:
                previous = db.get(GenerationRequest, current)
                if previous is None:
                    raise HTTPException(404, "Previous request not found.")
                # A chain belongs to the same user intention. New inputs start a new chain.
                if (
                    previous.scene_hint != payload.scene_hint
                    or previous.intent_text != payload.intent_text
                    or previous.selected_symbols != payload.selected_symbols
                ):
                    raise HTTPException(
                        409, "Inputs changed. Omit parent_request_id to start again."
                    )
                excluded.extend(
                    db.scalars(select(Suggestion.text).where(Suggestion.request_id == current))
                )
                current = previous.parent_request_id
                depth += 1
                if depth > 20:
                    raise HTTPException(409, "Start a new request after 20 generations.")
            start = perf_counter()
            try:
                result = provider.generate(payload, image, excluded)
            except ProviderUnavailable:
                raise HTTPException(
                    503, "Generation unavailable. Please try again later."
                ) from None
            except Exception:  # noqa: BLE001 - provider details must not reach clients
                raise HTTPException(502, "Generation provider failed.") from None
            # Validate even future AI output before storing or displaying it.
            if (
                not isinstance(result, GeneratedSentences)
                or not isinstance(result.sentences, list)
                or len(result.sentences) > 3
                or any(
                    not isinstance(s, str) or not s.strip() or len(s) > 300
                    for s in result.sentences
                )
            ):
                raise HTTPException(502, "Generation provider returned invalid sentences.")
            sentences = list(dict.fromkeys(s.strip() for s in result.sentences))
            sentences = [s for s in sentences if s not in excluded]
            record = GenerationRequest(
                scene_hint=payload.scene_hint,
                intent_text=payload.intent_text,
                selected_symbols=payload.selected_symbols,
                language=payload.language,
                image_supplied=image is not None,
                provider=provider.name,
                latency_ms=int((perf_counter() - start) * 1000),
                parent_request_id=parent,
            )
            db.add(record)
            db.flush()
            suggestions = [
                Suggestion(request_id=record.id, text=s, position=i)
                for i, s in enumerate(sentences)
            ]
            db.add_all(suggestions)
            db.commit()
            notice = (
                "Mock templates only. Photos are not analyzed." if provider.name == "mock" else ""
            )
            if not sentences:
                notice += " No new suggestions. In mock mode try water or coffee, or start again."
            return GenerationOutput(
                request_id=record.id,
                provider=provider.name,
                image_supplied=image is not None,
                image_analyzed=result.image_analyzed,
                suggestions=[SuggestionOutput.model_validate(s) for s in suggestions],
                notice=notice,
            )

    @app.post("/api/suggestions", response_model=GenerationOutput, status_code=201)
    def suggestions(payload: SuggestionInput):
        return generate(payload, None)

    @app.post("/api/suggestions/image", response_model=GenerationOutput, status_code=201)
    def suggestions_with_image(
        payload: Annotated[str, Form(description="JSON matching SuggestionInput", max_length=5000)],
        image: Annotated[UploadFile, File()],
    ):
        try:
            parsed = SuggestionInput.model_validate_json(payload)
        except ValidationError:
            image.file.close()
            raise HTTPException(422, "Invalid payload JSON. See SuggestionInput schema.") from None
        return generate(parsed, prepare_image(image, settings.max_image_bytes))

    @app.put("/api/requests/{request_id}/feedback")
    def feedback(request_id: UUID, payload: FeedbackInput):
        key = str(request_id)
        with sessions() as db:
            if not db.get(GenerationRequest, key):
                raise HTTPException(404, "Request not found.")
            suggestion_id = str(payload.suggestion_id) if payload.suggestion_id else None
            if suggestion_id:
                item = db.get(Suggestion, suggestion_id)
                if not item or item.request_id != key:
                    raise HTTPException(422, "The suggestion does not belong to this request.")
            record = db.get(Feedback, key)
            if record is None:
                record = Feedback(request_id=key)
                db.add(record)
            record.action = payload.action
            record.suggestion_id = suggestion_id
            record.updated_at = utc_now()
            db.commit()
        return {"request_id": key, "action": payload.action, "suggestion_id": suggestion_id}

    return app


app = create_app()
