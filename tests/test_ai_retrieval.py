from src.ai.providers import Request
from src.ai.retrieval import Memory, MemoryStore, similarity


def store_with(tmp_path, *items):
    store = MemoryStore(tmp_path / "accepted.jsonl")
    for request, sentence in items:
        store.accept(request, sentence)
    return store


def test_symbol_order_case_and_spaces_do_not_matter():
    memory = Memory(["Water", " glass"], "", "A café", "A glass of water, please.")
    assert similarity(Request(["glass", "water"], scene_hint="a CAFÉ"), memory) == 1.0


def test_negated_and_plain_wish_never_match():
    memory = Memory(["coffee"], "I want sugar", "A café", "Coffee with sugar, please.")
    assert similarity(Request(["coffee"], "I do not want sugar", "A café"), memory) == 0.0


def test_reuse_needs_a_near_identical_request(tmp_path):
    store = store_with(tmp_path, (Request(["water"], scene_hint="A café"), "Water, please."))
    assert store.reuse(Request(["water"], scene_hint="A café")) == ["Water, please."]
    # Same wish, other place: not reused, but given to the model as an example.
    on_bus = Request(["water"], scene_hint="On the bus")
    assert store.reuse(on_bus) == []
    assert store.examples(on_bus) == ["Water, please."]


def test_unrelated_wish_gives_no_examples(tmp_path):
    store = store_with(tmp_path, (Request(["water"], scene_hint="A café"), "Water, please."))
    assert store.examples(Request(["toilet"], scene_hint="A café")) == []


def test_reuse_is_off_with_a_photo_unless_allowed(tmp_path):
    store = store_with(tmp_path, (Request(["water"], scene_hint="A café"), "Water, please."))
    with_photo = Request(["water"], scene_hint="A café", jpeg=b"jpeg")
    assert store.reuse(with_photo) == []
    assert store.reuse(with_photo, allow_photo=True) == ["Water, please."]


def test_newest_first_unique_and_avoided_sentences_left_out(tmp_path):
    request = Request(["water"], scene_hint="A café")
    store = store_with(
        tmp_path,
        (request, "Water, please."),
        (request, "May I have some water?"),
        (request, "water, please."),
        (request, "A glass of water, please."),
    )
    assert store.reuse(
        Request(["water"], scene_hint="A café", avoid=["A glass of water, please."])
    ) == ["water, please.", "May I have some water?"]


def test_store_keeps_no_photo_and_skips_damaged_lines(tmp_path):
    store = store_with(tmp_path, (Request(["water"], jpeg=b"secret-bytes"), "Water, please."))
    with store.path.open("a", encoding="utf-8") as f:
        f.write("{broken\n")
    text = store.path.read_text(encoding="utf-8")
    assert "secret-bytes" not in text and '"had_photo": true' in text
    assert [m.sentence for m in store.load()] == ["Water, please."]
