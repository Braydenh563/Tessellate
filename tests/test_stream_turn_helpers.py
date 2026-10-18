"""The streamed chat turn's stages (`routes_chat._stream_lines` split, INBOX 1298)."""

from tessellate.api import routes_chat as rc


def test_a_new_prose_burst_after_a_tool_starts_a_new_paragraph() -> None:
    t = rc._Turn()
    rc._fold_event(t, "answer", {"delta": "One."}, None)
    rc._fold_event(t, "tool", {"touched": [{"kind": "note", "id": 7}, {"kind": "note", "id": "x"}]}, None)
    rc._fold_event(t, "answer", {"delta": "Two."}, None)
    assert t.answer_text == "One.\n\nTwo."
    assert t.touched_note_ids == [7]


def test_deltas_in_one_burst_are_joined_as_they_came() -> None:
    t = rc._Turn()
    for part in ("He", "llo"):
        rc._fold_event(t, "answer", {"delta": part}, None)
    assert t.answer_text == "Hello"


def test_only_a_sentence_end_asks_the_live_grounder() -> None:
    class Grounder:
        calls = 0

        def feed(self, text: str) -> list:
            self.calls += 1
            return [{"row": 1}]

    g = Grounder()
    t = rc._Turn()
    assert rc._fold_event(t, "answer", {"delta": "no stop"}, g) == []
    assert g.calls == 0
    assert rc._fold_event(t, "answer", {"delta": " here."}, g) == [{"row": 1}]


def test_an_exact_grounding_and_its_shape_are_remembered() -> None:
    t = rc._Turn()
    rc._note_kind(t, "grounding", {"exact": True, "sentences": [{"a": 1}], "support": {"shape": "all"}})
    assert t.exact_grounding == [{"a": 1}]
    assert t.shape == "all"
    assert "grounding" in t.sent_kinds
