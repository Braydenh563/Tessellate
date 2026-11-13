"""L101: the model is told how the shown notes link and why each was shown
(INBOX 1310: "it has no frame of reference for how related each shown
matching record is or why it was shown and how the shown notes link").
`chat_pool._frame_matches` gives each note `linked_to`, `link_reasons` and a
`match_info["why"]`; the composer said them and the model's prompt did not."""

from __future__ import annotations

from tessellate.ai import librarian


def _notes():
    return [
        {"id": 7, "content": "Book the ferry to Skye.", "linked_to": [9], "link_reasons": {9: "same trip"},
         "match_info": {"type": "keyword", "terms": ["skye"], "why": "Has the word “skye”"}},
        {"id": 8, "content": "Buy walking boots.", "linked_to": [], "link_reasons": {}},
        {"id": 9, "content": "Skye packing list.", "linked_to": [7], "link_reasons": {7: "same trip"}},
    ]


def _prompt(notes) -> str:
    return "\n".join(m["content"] for m in librarian.build_messages("what about skye", notes))


def test_each_note_names_the_shown_notes_it_links_to_by_number_with_the_reason():
    text = _prompt(_notes())
    assert "(linked to note 3: same trip)" in text
    assert "(linked to note 1: same trip)" in text


def test_a_note_says_why_it_was_shown():
    assert "(why shown: Has the word “skye”)" in _prompt(_notes())


def test_a_note_with_no_links_or_why_reads_as_before():
    line = next(l for l in _prompt(_notes()).splitlines() if "walking boots" in l)
    assert "linked to" not in line and "why shown" not in line


def test_a_link_to_a_note_not_in_the_prompt_is_not_named():
    notes = _notes()[:2]
    assert "linked to note" not in _prompt(notes)
