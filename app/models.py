from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id():
    return str(uuid4())


def utc_now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class GenerationRequest(Base):
    __tablename__ = "generation_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    scene_hint: Mapped[str] = mapped_column(Text)
    intent_text: Mapped[str] = mapped_column(Text)
    selected_symbols: Mapped[list] = mapped_column(JSON)
    language: Mapped[str] = mapped_column(String(5))
    image_supplied: Mapped[bool] = mapped_column(Boolean)
    provider: Mapped[str] = mapped_column(String(50))
    latency_ms: Mapped[int] = mapped_column(Integer)
    parent_request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("generation_requests.id"), nullable=True
    )


class Suggestion(Base):
    __tablename__ = "suggestions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_requests.id"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class Feedback(Base):
    __tablename__ = "feedback"
    # One current decision per generation request; PUT is retry-safe.
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_requests.id"), primary_key=True
    )
    action: Mapped[str] = mapped_column(String(10))
    suggestion_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suggestions.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
