from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class SuggestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    scene_hint: str = Field(default="", max_length=500)
    selected_symbols: list[ShortText] = Field(default_factory=list, max_length=20)
    intent_text: str = Field(default="", max_length=500)
    language: Literal["en"] = "en"
    parent_request_id: UUID | None = None

    @model_validator(mode="after")
    def require_intent(self):
        if not self.selected_symbols and not self.intent_text:
            raise ValueError("Select at least one symbol or enter an intention.")
        return self


class SuggestionOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str


class GenerationOutput(BaseModel):
    request_id: UUID
    provider: str
    image_supplied: bool
    image_analyzed: bool
    suggestions: list[SuggestionOutput]
    notice: str


class FeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["accepted", "rejected"]
    suggestion_id: UUID | None = None

    @model_validator(mode="after")
    def check_selection(self):
        if (self.action == "accepted") != (self.suggestion_id is not None):
            raise ValueError("accepted needs suggestion_id; rejected must omit it.")
        return self
