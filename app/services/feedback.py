from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from app.errors import AppError
from app.models import Feedback, GenerationRequest, Suggestion, utc_now
from app.schemas import FeedbackInput

_INSERT_BY_DIALECT = {"sqlite": sqlite_insert, "postgresql": postgres_insert}


def save_feedback(request_id: UUID, payload: FeedbackInput, sessions: sessionmaker):
    key = str(request_id)
    with sessions() as db:
        if not db.get(GenerationRequest, key):
            raise AppError(404, "Request not found.", "REQUEST_NOT_FOUND")

        suggestion_id = str(payload.suggestion_id) if payload.suggestion_id else None
        if suggestion_id:
            item = db.get(Suggestion, suggestion_id)
            if not item or item.request_id != key:
                raise AppError(
                    422, "The suggestion does not belong to this request.", "SUGGESTION_MISMATCH"
                )

        values = {
            "action": payload.action,
            "suggestion_id": suggestion_id,
            "updated_at": utc_now(),
        }
        insert = _INSERT_BY_DIALECT[db.get_bind().dialect.name]
        statement = insert(Feedback).values(request_id=key, **values)

        # Let the database resolve concurrent writes to the same request ID.
        db.execute(
            statement.on_conflict_do_update(index_elements=[Feedback.request_id], set_=values)
        )
        db.commit()

    return {"request_id": key, "action": payload.action, "suggestion_id": suggestion_id}