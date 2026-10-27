from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Feedback, GenerationRequest, Suggestion
from app.reuse_schemas import ReusableSuggestion, ReuseInput, ReuseOutput

MAX_REUSABLE_SUGGESTIONS = 3
CANDIDATE_BATCH_SIZE = 100


def find_reusable_suggestions(payload: ReuseInput, sessions: sessionmaker) -> ReuseOutput:
    """Read accepted exact matches without calling a provider or writing records."""
    statement = (
        select(
            GenerationRequest.id.label("source_request_id"),
            GenerationRequest.scene_hint,
            GenerationRequest.intent_text,
            GenerationRequest.selected_symbols,
            Suggestion.id.label("source_suggestion_id"),
            Suggestion.text,
        )
        .select_from(Feedback)
        .join(GenerationRequest, GenerationRequest.id == Feedback.request_id)
        .join(
            Suggestion,
            (Suggestion.id == Feedback.suggestion_id)
            & (Suggestion.request_id == GenerationRequest.id),
        )
        .where(
            Feedback.action == "accepted",
            GenerationRequest.language == payload.language,
            GenerationRequest.image_supplied.is_(False),
        )
        .order_by(Feedback.updated_at.desc(), Suggestion.id.asc())
        .execution_options(yield_per=CANDIDATE_BATCH_SIZE)
    )

    suggestions = []
    seen = set()
    scene = payload.scene_hint.strip()
    intention = payload.intent_text.strip()

    with sessions() as db:
        with db.execute(statement) as candidates:
            for candidate in candidates:
                # Python comparisons preserve case, Unicode trimming, and array order
                # without depending on database-specific collations or JSON equality.
                if (
                    candidate.scene_hint.strip() != scene
                    or candidate.intent_text.strip() != intention
                    or candidate.selected_symbols != payload.selected_symbols
                ):
                    continue

                sentence = candidate.text.strip()
                # Legacy rows may bypass the current generation validation rules.
                if not sentence or len(sentence) > 300 or sentence in seen:
                    continue

                seen.add(sentence)
                suggestions.append(
                    ReusableSuggestion(
                        text=sentence,
                        source_request_id=candidate.source_request_id,
                        source_suggestion_id=candidate.source_suggestion_id,
                    )
                )
                # Limit unique results after matching, not the initial SQL rows.
                if len(suggestions) == MAX_REUSABLE_SUGGESTIONS:
                    break

    return ReuseOutput(suggestions=suggestions)
