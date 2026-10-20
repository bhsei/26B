from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.models import Feedback, GenerationRequest, Suggestion, utc_now
from app.schemas import FeedbackInput


def save_feedback(request_id: UUID, payload: FeedbackInput, sessions: sessionmaker):
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
