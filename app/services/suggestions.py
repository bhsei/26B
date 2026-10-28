from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.errors import AppError
from app.models import GenerationRequest, Suggestion
from app.providers.base import GeneratedSentences, ProviderUnavailable, SentenceProvider
from app.schemas import GenerationOutput, SuggestionInput, SuggestionOutput


def generate(
    payload: SuggestionInput,
    image: bytes | None,
    sessions: sessionmaker,
    provider: SentenceProvider,
) -> GenerationOutput:
    with sessions() as db:
        excluded = []
        parent = str(payload.parent_request_id) if payload.parent_request_id else None
        current = parent
        depth = 0
        while current:
            previous = db.get(GenerationRequest, current)
            if previous is None:
                raise AppError(404, "Previous request not found.", "REQUEST_NOT_FOUND")
            # A chain belongs to the same user intention. New inputs start a new chain.
            if (
                previous.scene_hint != payload.scene_hint
                or previous.intent_text != payload.intent_text
                or previous.selected_symbols != payload.selected_symbols
            ):
                raise AppError(
                    409, "Inputs changed. Omit parent_request_id to start again.", "INPUT_CHANGED"
                )
            excluded.extend(
                db.scalars(select(Suggestion.text).where(Suggestion.request_id == current))
            )
            current = previous.parent_request_id
            depth += 1
            if depth > 20:
                raise AppError(
                    409, "Start a new request after 20 generations.", "GENERATION_LIMIT_REACHED"
                )
        start = perf_counter()
        try:
            result = provider.generate(payload, image, excluded)
        except ProviderUnavailable:
            raise AppError(
                503, "Generation unavailable. Please try again later.", "PROVIDER_UNAVAILABLE"
            ) from None
        except Exception:  # noqa: BLE001 - provider details must not reach clients
            raise AppError(502, "Generation provider failed.", "PROVIDER_FAILED") from None
        # Validate even future AI output before storing or displaying it.
        if (
            not isinstance(result, GeneratedSentences)
            or not isinstance(result.sentences, list)
            or len(result.sentences) > 3
            or any(
                not isinstance(s, str) or not s.strip() or len(s) > 300 for s in result.sentences
            )
        ):
            raise AppError(
                502, "Generation provider returned invalid sentences.", "INVALID_PROVIDER_OUTPUT"
            )
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
            Suggestion(request_id=record.id, text=s, position=i) for i, s in enumerate(sentences)
        ]
        db.add_all(suggestions)
        db.commit()
        notice = "Mock templates only. Photos are not analyzed." if provider.name == "mock" else ""
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
