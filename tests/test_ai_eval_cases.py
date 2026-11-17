"""Checks on the AI evaluation set (tests/ai_eval/cases.json); no model is called."""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.schemas import SuggestionInput

CASES_FILE = Path(__file__).parent / "ai_eval" / "cases.json"
DATA = json.loads(CASES_FILE.read_text(encoding="utf-8"))
CASES = DATA["cases"]
NEGATION_MODES = {"required", "forbidden", "any"}


def mentions(text: str, term: str) -> bool:
    """Same rule as the evaluation: case-insensitive, word boundary at both ends."""
    pattern = r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)"
    return re.search(pattern, text.casefold()) is not None


def test_ids_are_unique():
    counts = Counter(case["id"] for case in CASES)
    assert [i for i, n in counts.items() if n > 1] == []


def test_core_set_has_at_least_four_cafe_cases_per_category():
    # Promised in the replies to Team A finding 7 and Group F finding 1.
    core = [c for c in CASES if c["core"]]
    assert len(core) >= 32
    assert {c["scenario"] for c in core} == {"cafe"}
    counts = Counter(c["category"] for c in core)
    assert all(counts[name] >= 4 for name in DATA["core_categories"]), counts


def test_every_category_is_used_at_least_twice():
    counts = Counter(c["category"] for c in CASES)
    assert set(counts) == set(DATA["categories"])
    assert min(counts.values()) >= 2, counts


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_well_formed(case):
    assert case["category"] in DATA["categories"]
    assert case["photo"] is None or case["photo"] in DATA["photos"]
    assert case["negation"] in NEGATION_MODES
    assert 1 <= case.get("rounds", 1) <= 3
    assert case["reference"].strip()
    assert all(isinstance(s, str) and s.strip() for s in case.get("examples", []))
    for group in case["required"]:
        assert group and all(isinstance(t, str) and t.strip() for t in group)
    if case.get("expect_empty"):
        assert case["required"] == []
    required = {t.casefold() for group in case["required"] for t in group}
    assert not required & {t.casefold() for t in case["forbidden"]}
    if case.get("negation_alternatives"):
        assert case["negation"] == "required"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_a_valid_backend_request(case):
    SuggestionInput(
        scene_hint=case["scene_hint"],
        selected_symbols=case["symbols"],
        intent_text=case["intention"],
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_forbidden_terms_only_appear_in_injection_inputs(case):
    # A forbidden word that the person typed would make the case contradictory.
    if case["category"] == "injection":
        return
    typed = " ".join([case["intention"], case["scene_hint"], *case["symbols"]])
    assert [t for t in case["forbidden"] if mentions(typed, t)] == []


def test_matching_rule_uses_word_boundaries():
    assert mentions("Could I borrow a pencil?", "pencil")
    assert not mentions("Could I borrow a pencil?", "pen")
    assert mentions("A coffee to go, please.", "to go")
    assert mentions("Two kilos of apples, please.", "two")
