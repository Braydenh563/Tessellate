"""The composer's brief for a running model (CHAT_PLAN, "the composer everywhere"
9 and 10; Phase 5 a).

The owner, 2026-10-06: "ai should still be the core when it is available, but
the composer should be used to lessen the load, refine and better the
responses and results, assist and complement, as well as cheapen the run cost
of the ai". The model still answers; what it reads is the notes cut to the
parts on the question (`composer.brief`), measured here on the 25 showcase
questions (`tests/_composer_eval.py`), and the composed answer is shown while
it writes (`/chat/stream`'s `composed_preview`).
"""

from __future__ import annotations

import re

import json

import pytest

from tessellate.ai import composer, librarian
from tessellate.entry import manager
from tests import _composer_eval as ev
from tests.test_composer_688 import NOTES

LONG = {
    "id": 41,
    "content": (
        "# Boiler\n\nThe boiler service is due on 12 November. The engineer is Sam from Hearth & Co. "
        "We moved into the flat in spring and the hallway still needs painting. The neighbours "
        "have a cat that sits on our windowsill. The parking permit costs more than it did "
        "and the bins are collected by the council."
    ),
    "category": "Home",
}


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture(scope="module")
def rows():
    return ev.context_rows()


def test_a_long_note_is_cut_to_the_sentences_on_the_question():
    packed = composer.brief("When is the boiler service due?", [LONG])
    assert packed is not None
    text = packed["notes"][0]["content"]
    assert packed["notes"][0]["briefed"] is True
    assert "The boiler service is due on 12 November." in text
    assert "cat" not in text and "parking" not in text
    assert text.startswith("Boiler")
    assert text.endswith("…")
    assert packed["chars_after"] < packed["chars_before"]


def test_attached_notes_and_documents_go_whole():
    attached = {**LONG, "attached": True}
    document = {"id": "doc-3", "content": LONG["content"], "category": "Document"}
    packed = composer.brief("When is the boiler service due?", [attached, document, {**LONG, "id": 42}])
    assert packed is not None
    assert packed["notes"][0] is attached
    assert packed["notes"][1] is document
    assert packed["notes"][2].get("briefed") is True


def test_a_newest_notes_question_and_a_question_nothing_answers_are_not_briefed():
    assert composer.brief("What did I write recently?", [LONG], recent=True) is None
    assert composer.brief("What is the capital of Peru?", [LONG]) is None


def test_a_note_barely_shortened_goes_whole():
    short = {"id": 7, "content": "Check-up booked for the 21st. Ask about the night guard.", "category": "Health"}
    packed = composer.brief("When is the check-up?", [short, LONG])
    assert packed is not None
    assert packed["notes"][0] is short


def test_every_note_keeps_its_place_and_fields(rows):
    for row in rows:
        if not row["brief"]:
            continue
        before, after = row["notes"], row["brief"]["notes"]
        assert [n["id"] for n in after] == [n["id"] for n in before]
        for old, new in zip(before, after):
            assert {k: v for k, v in new.items() if k not in ("content", "briefed")} == {k: v for k, v in old.items() if k != "content"}


def test_every_part_of_the_brief_is_the_notes_own_words(rows):
    for row in rows:
        if not row["brief"]:
            continue
        for old, new in zip(row["notes"], row["brief"]["notes"]):
            if not new.get("briefed"):
                continue
            flat = _flat(old["content"])
            #: A checklist's items are read without their "- [x]" marks (the
            #: words are still the note's own), so compare against that too.
            unticked = _flat(re.sub(r"(?m)^\s*[-*+]\s+(?:\[[ xX]\]\s+)?", "", old["content"]))
            for part in new["content"].split(" … "):
                part = part.strip(" …").removeprefix(composer.read_note(old, 0).title).strip()
                if part:
                    assert part in flat or _flat(part) in flat or _flat(part) in unticked, (row["question"], part)


def test_the_brief_holds_everything_the_composed_answer_quotes(rows):
    """The answer shown while the model writes never says a thing the model
    was not shown."""
    on = ev.today()
    for row in rows:
        if not row["brief"]:
            continue
        result = composer.compose(row["question"], row["notes"], today=on)
        by_id = {n["id"]: n for n in row["brief"]["notes"]}
        original = {n["id"]: n for n in row["notes"]}
        for quoted in result["grounding"]:
            raw = _flat(original[quoted["note_id"]]["content"][quoted["start"] : quoted["end"]])
            assert raw in _flat(by_id[quoted["note_id"]]["content"]), (row["question"], raw)


def test_the_brief_costs_fewer_tokens_on_the_showcase_eval(rows):
    """Measured 2026-10-06: 18,883 to 15,613 prompt tokens over the 25 questions
    (17.3% fewer), the notes message 14,626 to 11,358 (22.3%); 24 of 25
    briefed (the "recently" question is not). The showcase notes are short
    (129 characters on average), so this is the floor: a note of a few
    paragraphs keeps its name and the sentences on the question."""
    summary = ev.context_summary(rows)
    assert summary["briefed"] == 24
    assert summary["prompt_saved"] >= 0.15
    assert summary["notes_saved"] >= 0.2
    assert all(r["prompt_after"] <= r["prompt_before"] for r in rows)


def test_the_prompt_says_once_what_the_cut_means():
    packed = composer.brief("When is the boiler service due?", [LONG])
    content = librarian.build_messages("When is the boiler service due?", packed["notes"])[-1]["content"]
    assert content.count(librarian.BRIEF_HEADER) == 1
    plain = librarian.build_messages("When is the boiler service due?", [LONG])[-1]["content"]
    assert librarian.BRIEF_HEADER not in plain


def test_with_tools_a_cut_note_names_get_note():
    packed = composer.brief("When is the boiler service due?", [LONG])
    assert "get_note(41)" in librarian.note_for_prompt(packed["notes"][0])
    assert "get_note" not in librarian.note_for_prompt(packed["notes"][0], can_fetch=False)


def test_the_brief_is_deterministic():
    one = composer.brief("What is the Harbor launch plan?", NOTES)
    two = composer.brief("What is the Harbor launch plan?", NOTES)
    assert one == two


# --- through the route, with the fake transport --------------------------------------


def _stream(client, question: str, **body) -> list[dict]:
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line.strip()]


def _seed(session) -> None:
    manager.create_entry(session, LONG["content"])
    manager.create_entry(session, "# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.")
    session.commit()


@pytest.mark.parametrize("body", [{"notes_only": True, "use_tools": False, "answer_from": "ai"}, {"use_tools": False}])
def test_a_running_model_reads_the_brief_and_the_composed_answer_shows_first(ai_client, fake_ollama, session, body):
    _seed(session)
    events = _stream(ai_client, "When is the boiler service due?", **body)
    kinds = [e["type"] for e in events]
    assert "composed_preview" in kinds
    preview = next(e for e in events if e["type"] == "composed_preview")
    assert kinds.index("composed_preview") < kinds.index("answer")
    assert "12 November" in preview["text"]
    assert preview["grounding"] and isinstance(preview["next"], list)
    #: The model is still the answerer.
    answer = "".join(e["delta"] for e in events if e["type"] == "answer")
    assert fake_ollama.librarian_reply in answer
    #: And what it read was the brief, not the whole note.
    sent = fake_ollama.chat_calls[-1][-1]["content"]
    assert librarian.BRIEF_HEADER in sent
    assert "The boiler service is due on 12 November." in sent
    assert "windowsill" not in sent


def test_a_composed_turn_has_no_preview(ai_client, fake_ollama, session):
    _seed(session)
    events = _stream(ai_client, "When is the boiler service due?", notes_only=True, use_tools=False, answer_from="notes")
    assert "composed_preview" not in [e["type"] for e in events]


def test_a_titled_notes_other_sentences_do_not_score_on_its_title():
    """L500: in the brief only the sentence that says the title's words takes the title weight."""
    from tessellate.ai.composer_select import _score

    note = {"id": 7, "content": "# Boiler service\n\nThe boiler service is due on 12 November. The cat sits on the sill.", "category": "Home"}
    view = composer.read_note(note, 0)

    def scores(carrier):
        return {s.text: s.score for s in _score("when", ["boiler", "service"], [view], carrier=carrier)}

    plain, carrier = scores(False), scores(True)
    assert "The cat sits on the sill." in plain
    assert "The cat sits on the sill." not in carrier
    assert carrier["The boiler service is due on 12 November."] > 0
