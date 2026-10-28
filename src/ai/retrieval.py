"""Retrieval over past accepted sentences: reuse before generation, examples for the prompt.

Standalone version of the backend lookup (`/api/suggestions/reuse` on the refactor
branch). That endpoint needs an exact match; this one scores similarity, so
["glass", "water"] matches ["water", "glass"] and "I want water" matches "water please".
No embeddings: plain token overlap needs no model, no quota and no extra RAM.

- Reuse: a near-identical past request returns its accepted sentences with no AI call.
- RAG: the closest accepted sentences go to the model as 'examples' for wording.

The store is a local JSONL file of synthetic test data. It has no user ownership yet,
so it must not hold real people's sentences.
"""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.ai.providers import NEGATION, Request

WEIGHTS = {"symbols": 0.5, "words": 0.3, "scene": 0.2}
REUSE_SCORE = 0.9
EXAMPLE_SCORE = 0.4
STOPWORDS = {
    "a",
    "an",
    "the",
    "i",
    "me",
    "my",
    "to",
    "of",
    "in",
    "at",
    "on",
    "is",
    "am",
    "be",
    "some",
    "please",
    "would",
    "like",
    "want",
    "could",
    "can",
    "have",
    "may",
    "you",
}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w']+", text.casefold()) if t not in STOPWORDS}


def overlap(a: set[str], b: set[str]) -> float:
    """Jaccard similarity; two empty fields count as the same."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


@dataclass
class Memory:
    symbols: list[str]
    intention: str
    scene_hint: str
    sentence: str
    had_photo: bool = False
    time_utc: str = ""


def similarity(request: Request, memory: Memory) -> float:
    # Opposite wishes share most words ("sugar" vs "no sugar"): never match them.
    asked = f"{request.intention} {' '.join(request.symbols)}"
    stored = f"{memory.intention} {' '.join(memory.symbols)}"
    if bool(NEGATION.search(asked)) != bool(NEGATION.search(stored)):
        return 0.0
    symbols = overlap(
        {s.casefold().strip() for s in request.symbols},
        {s.casefold().strip() for s in memory.symbols},
    )
    # Words of symbols and intention together, so a symbol typed as text still matches.
    words = overlap(tokens(asked), tokens(stored))
    scene = overlap(tokens(request.scene_hint), tokens(memory.scene_hint))
    return WEIGHTS["symbols"] * symbols + WEIGHTS["words"] * words + WEIGHTS["scene"] * scene


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[Memory]:
        if not self.path.exists():
            return []
        memories = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                memories.append(Memory(**json.loads(line)))
            except (ValueError, TypeError):
                continue  # Skip a damaged line instead of losing the whole store.
        return memories

    def accept(self, request: Request, sentence: str) -> None:
        """Record the sentence the person chose. Only accepted sentences are stored."""
        memory = Memory(
            symbols=request.symbols,
            intention=request.intention,
            scene_hint=request.scene_hint,
            sentence=sentence,
            had_photo=request.jpeg is not None,
            time_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(memory.__dict__, ensure_ascii=False) + "\n")

    def ranked(self, request: Request, min_score: float) -> list[tuple[float, Memory]]:
        scored = [(similarity(request, m), i, m) for i, m in enumerate(self.load())]
        # Best score first; among equal scores the newest line (the file is in time order).
        scored = sorted((x for x in scored if x[0] >= min_score), key=lambda x: x[:2], reverse=True)
        unique, seen = [], set()
        for score, _, memory in scored:
            if memory.sentence.casefold() not in seen:
                seen.add(memory.sentence.casefold())
                unique.append((score, memory))
        return unique

    def reuse(self, request: Request, allow_photo: bool = False) -> list[str]:
        """Up to three sentences to show without calling a model, or [] to generate.

        With a photo the scene may differ from the stored one, so reuse is off by
        default (same rule as the backend lookup); examples are still used.
        """
        if request.jpeg is not None and not allow_photo:
            return []
        avoid = {s.casefold() for s in request.avoid}
        return [
            m.sentence
            for _, m in self.ranked(request, REUSE_SCORE)
            if m.sentence.casefold() not in avoid
        ][:3]

    def examples(self, request: Request, k: int = 3) -> list[str]:
        return [m.sentence for _, m in self.ranked(request, EXAMPLE_SCORE)][:k]
