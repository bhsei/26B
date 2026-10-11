from app.providers.base import GeneratedSentences
from app.schemas import SuggestionInput


class MockProvider:
    """Fixed café templates, not an AI model. Photos are deliberately ignored."""

    name = "mock"

    def generate(self, payload: SuggestionInput, image: bytes | None, excluded: list[str]):
        # Only support explicitly whitelisted demo intentions. Never turn a
        # negative or arbitrary sentence into an affirmative request.
        intent = payload.intent_text.lower().strip().rstrip(".!")
        supported = {
            "": None,
            "water": "water",
            "i want water": "water",
            "coffee": "coffee",
            "i want coffee": "coffee",
        }
        if intent not in supported:
            return GeneratedSentences([])
        words = {s.lower() for s in payload.selected_symbols}
        if supported[intent]:
            words.add(supported[intent])
        if words not in ({"water"}, {"coffee"}):
            return GeneratedSentences([])
        if "water" in words:
            candidates = [
                "Could I have a glass of water, please?",
                "I would like some water, please.",
                "May I have some water, please?",
                "Please could you bring me some water?",
                "A glass of water, please.",
                "Water, please.",
            ]
        elif "coffee" in words:
            candidates = [
                "Could I have a coffee, please?",
                "I would like some coffee, please.",
                "May I order a coffee, please?",
                "A coffee, please.",
                "Please could you bring me a coffee?",
                "Coffee, please.",
            ]
        else:
            # Do not pretend we understand an arbitrary intention.
            candidates = []
        return GeneratedSentences([s for s in candidates if s not in excluded][:3])
