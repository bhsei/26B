from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas import ShortText


class ReuseInput(BaseModel):
    """Text-only lookup input; regeneration and photo fields are not accepted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_hint: str = Field(default="", max_length=500)
    selected_symbols: list[ShortText] = Field(default_factory=list, max_length=20)
    intent_text: str = Field(default="", max_length=500)
    language: Literal["en"] = "en"

    @model_validator(mode="after")
    def require_intent(self):
        if not self.selected_symbols and not self.intent_text:
            raise ValueError("Select at least one symbol or enter an intention.")
        return self


class ReusableSuggestion(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    source_request_id: UUID
    source_suggestion_id: UUID


class ReuseOutput(BaseModel):
    suggestions: list[ReusableSuggestion] = Field(max_length=3)
