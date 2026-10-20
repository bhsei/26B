from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.orm import sessionmaker

from app.schemas import FeedbackInput
from app.services.feedback import save_feedback


def create_feedback_router(sessions: sessionmaker) -> APIRouter:
    router = APIRouter()

    @router.put("/api/requests/{request_id}/feedback")
    def feedback(request_id: UUID, payload: FeedbackInput):
        return save_feedback(request_id, payload, sessions)

    return router
