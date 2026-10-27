"""The engine probe's bugs P1 to P8 (docs/roadmap/archive/agent-remaining/engine-probe-1010.md),
each as the route answered it on 2026-10-10 and as it must answer now.

Route-level where the bug was the route's (`/chat/stream`, the Ask box's From
your notes, `tests/test_composer_route_688.py`'s `_ask`), composer-level where
the cause is the composer's own and a stand-in would hide it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tessellate.ai import composer
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOTES_ONLY = {"notes_only": True, "use_tools": False, "answer_from": "notes"}


def _seed(session) -> None:
    for content in (
        "# Race day checklist\n\n- Same breakfast as the long runs\n- Bib and pins the night before",
        "# Boiler service\n\nDue in March. The engineer last time said the valve was worn.",
        "# Harbor launch plan\n\nShip Harbor to the public on the 14th of next month.",
        "# Harbor risks\n\nHarbor offline mode is hard to find.",
        "# Knife sharpening\n\nWhetstone at 15 degrees, 1000 then 6000 grit.",
    ):
        manager.create_entry(session, content)
    session.commit()


def test_p1_a_name_is_matched_as_a_word_not_inside_same(client, session):
    _seed(session)
    out = _ask(client, "who is Sam", **NOTES_ONLY)
    assert "Same breakfast" not in out["text"]
    assert any(f"{lead}“Sam”." in out["text"] for lead in composer.phrase_options("none_found"))


@pytest.mark.parametrize("message", ["hello", "thanks", "ok", "what is your name", "what can you do", "are you an AI"])
def test_p2_small_talk_is_answered_when_answering_from_notes(ai_client, session, message):
    _seed(session)
    out = _ask(ai_client, message, **NOTES_ONLY)
    assert out["text"].strip(), out
    assert "newest notes" not in out["text"]


def test_p3_a_sum_is_worked_out_even_when_retrieval_fell_back_to_the_newest(client, session):
    _seed(session)
    out = _ask(client, "what is 12 * 7", **NOTES_ONLY)
    assert out["text"].startswith("12 * 7 is 84"), out["text"]


@pytest.mark.parametrize("question", ["the knife note and the kitchen", "what about knives in the kitchen"])
def test_p4_the_route_says_no_repetition_for_a_sentence_in_one_note(ai_client, session, question):
    """`ai_client`'s stand-in embedder rates every two sentences alike, as the
    probe's run did (the 77 showcase notes): the echo count must not follow it."""
    import json

    showcase = Path(__file__).parent / "fixtures" / "composer" / "showcase_725.json"
    for note in json.loads(showcase.read_text(encoding="utf-8"))["notes"]:
        manager.create_entry(session, note["content"])
    session.commit()
    out = _ask(ai_client, question, **NOTES_ONLY)
    assert out["text"].strip()
    assert "say this" not in out["text"], out["text"]


def test_p5_a_count_of_notes_on_a_subject_keeps_its_subject(client, session):
    _seed(session)
    out = _ask(client, "how many notes are about Harbor", **NOTES_ONLY)
    assert not out["text"].startswith("You have ")
    assert "Harbor" in out["text"]


def test_p5_a_count_of_all_notes_is_still_the_count(client, session):
    _seed(session)
    assert _ask(client, "how many notes do I have", **NOTES_ONLY)["text"] == "You have 5 notes."


@pytest.mark.parametrize("question", ["what did I write last week", "when did I last write about the boiler"])
def test_p6_time_words_are_never_the_subject(client, session, question):
    _seed(session)
    out = _ask(client, question, **NOTES_ONLY)
    assert "“last”" not in out["text"] and "“week”" not in out["text"]


def test_p6_time_words_are_not_subject_terms():
    assert composer.subject_terms("when did I last write about running") == ["running"]
    assert composer.subject_terms("what did I write last week") == []


def test_p7_a_subject_with_no_note_is_said_to_be_missing_not_answered_with_the_newest(client, session):
    _seed(session)
    out = _ask(client, "summarise my gym notes", **NOTES_ONLY)
    assert "newest notes" not in out["text"]
    assert "“gym”" in out["text"]


def test_p7_what_i_write_most_about_is_measured(client, session):
    _seed(session)
    out = _ask(client, "what did I write most about", **NOTES_ONLY)
    assert "newest notes" not in out["text"]
    assert "“harbor” (2 notes)" in out["text"], out["text"]


def test_p8_the_first_answer_does_not_import_the_embedding_stack():
    """0.6 to 1.8 s on the first call: `grounding.paragraph_ordinal` imported
    `embeddings` (the model manager, the database models, SQLAlchemy)."""
    code = (
        "import sys, time; from datetime import date; from tessellate.ai import composer; "
        "t = time.perf_counter(); "
        "composer.compose('when is the dentist', [{'id': 1, 'content': '# Dentist\\n\\nCheck-up booked for the 21st.', 'created_at': '2026-10-01'}], today=date(2026, 10, 6)); "
        "print('tessellate.ai.embeddings' in sys.modules, 'sqlalchemy' in sys.modules, round(time.perf_counter() - t, 3))"
    )
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root, env={"PYTHONPATH": str(root / "src")}, check=True)
    embeddings, sqlalchemy, _seconds = out.stdout.split()
    assert (embeddings, sqlalchemy) == ("False", "False"), out.stdout


@pytest.mark.parametrize(("word", "stem"), [("same", "same"), ("news", "news"), ("hiring", "hire"), ("writing", "write"), ("boxes", "box"), ("opening", "open")])
def test_p1_the_stemmer_keeps_a_word_with_no_suffix_whole(word, stem):
    assert composer._stem(word) == stem
    assert composer._stem("same") != composer._stem("sam")
