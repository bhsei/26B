from dataclasses import dataclass
from typing import Protocol

from app.schemas import SuggestionInput


@dataclass(frozen=True)
class GeneratedSentences:
    sentences: list[str]
    image_analyzed: bool = False


class ProviderUnavailable(Exception):
    """Translate provider/network failures into this exception (never expose keys)."""


class SentenceProvider(Protocol):
    name: str

    def generate(
        self, payload: SuggestionInput, image: bytes | None, excluded: list[str]
    ) -> GeneratedSentences: ...
