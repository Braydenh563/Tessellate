"""INBOX 1420, "what have I written about uni" (no model): the answer named a
note "the note on What your notes currently leave out" and closed on "A good
next question here: “how do I ask about one note”", a how-to for the app
after an answer from the notes."""

from pathlib import Path

import pytest

from tessellate.ai import composer_aware, composer_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "first",
    [
        "What your notes currently leave out is the complete structure of your double degree.",
        "How the course is marked is still unclear.",
        "Why the bus is late is anyone's guess.",
        "Which subject comes next is up to the faculty.",
    ],
)
def test_a_wh_clause_is_never_the_subject_a_note_is_named_by(first):
    name = composer_frame.short_name({"content": first + " More after it."})
    assert not name.startswith("the note on"), name
    assert "“" in name


def test_a_plain_subject_still_names_the_note():
    assert composer_frame.short_name({"content": "Cloud computing is the delivery of services."}) == "the note on cloud computing"


def test_a_notes_answer_does_not_close_on_a_howto():
    src = (ROOT / "src" / "tessellate" / "api" / "routes_chat.py").read_text(encoding="utf-8")
    assert "related=not cited" in src
    aw = composer_aware.build(tab="ask", actions=[])
    assert "how do I" not in composer_aware.closing(aw, "s", related=False, asked="what have I written about uni")
    # With nothing cited the how-to may still help.
    assert "how do I ask about one note" in "".join(composer_aware.closing(aw, f"s{i}", asked="hello") for i in range(6))


@pytest.mark.parametrize(
    ("written", "said"),
    [
        ("so I walked and was 20 minutes late", "so you walked and were 20 minutes late"),
        ("I told him and was told off", "you told him and were told off"),
        ("I walked and wasn't late", "you walked and weren't late"),
        # Another subject in between keeps its own verb.
        ("I think it rained and was cold", "you think it rained and was cold"),
        ("The bus was late and was full", "The bus was late and was full"),
    ],
)
def test_a_was_that_shares_the_writers_i_agrees_with_you(written, said):
    from tessellate.ai.realise import shift_person

    assert shift_person(written) == said
