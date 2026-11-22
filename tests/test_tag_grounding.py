"""The "Study" bug (WORLD_CLASS_PLAN 23, decision 5): a tag is never proposed
on a note that contains none of its words.

The owner, 2026-10-10: "Study and university tags are suggested on the top
note if it has no tags no matter what the note is about". Two votes did it,
both reproduced here before the fix:

* **With no model**, `tagging.suggest` let the nearest notes vote
  for every tag they carry. In a notebook whose lecture notes all carry
  "study" and "university", a note sharing one ordinary word with them
  ("Friday", "books", "chapter") was offered both.
* **With a model**, `librarian.suggest_tags` lists the notebook's tags most
  used first and says "Prefer one of those"; a small model answers with the
  first two whatever the note says (`triage-1010.md`, line 23). That reply
  is faked here, since what a real model answers is not verified.

The fix is one rule on both paths, `tagging.grounds`: a tag is
kept only when the note says one of its words or a phrase of a topic the
tag names ("exam" backs #study, Education).
"""

from __future__ import annotations

import json

from tessellate.ai import librarian, tagging
from tessellate.entry import manager

LECTURES = (
    "Lecture notes on thermodynamics and entropy",
    "Revision timetable for the library weeks",
    "Exam prep: past papers in the library",
    "Seminar on the French revolution",
    "Dissertation outline, chapter two",
    "Library fines paid, return the books Friday",
)
#: Notes that say neither "study" nor "university", nor anything about either.
UNRELATED = (
    "Books to read on the plane: Piranesi",
    "Notes from the chapter on stoicism",
    "Friday plan: the past week in review",
)


def _notebook(session) -> None:
    for text in LECTURES:
        manager.create_entry(session, text, category_name="Uni", tags=["study", "university"])
    for i in range(2):
        manager.create_entry(session, f"Pasta night {i}: garlic, chilli, lemon", category_name="Cooking", tags=["dinner"])
    session.commit()


def test_no_model_never_offers_a_tag_the_note_has_no_word_for(session) -> None:
    _notebook(session)
    for text in UNRELATED:
        offered = tagging.suggest(session, text, have=[])
        assert not {"study", "university"} & set(offered), (text, offered)


def test_a_models_tags_are_kept_only_when_the_note_has_their_words(session, monkeypatch) -> None:
    from tessellate.entry import tag_suggestions

    _notebook(session)
    entry = manager.create_entry(session, "Lentil dal with cumin and a tin of tomatoes", category_name="Cooking")
    session.commit()
    monkeypatch.setattr(librarian, "suggest_tags", lambda text, have, *a, vocabulary=None, **k: list(vocabulary or [])[:2])
    tag_suggestions.keep_suggestions(session, entry, "llm")
    kept = json.loads(entry.suggested_tags)
    assert not {"study", "university"} & set(kept), kept


def test_a_tag_the_note_has_a_word_for_is_still_offered_and_explained(session) -> None:
    _notebook(session)
    offered = tagging.suggest(session, "Exam prep for Friday: past papers in the library", have=[])
    assert "study" in offered, offered
    assert tagging.reason("study", "Exam prep for Friday") == "It mentions \u201cexam\u201d."
    assert tagging.reason("university", "Study plan for the university library").startswith("It says")
    assert tagging.reason("study", "Pasta night") == ""


def test_at_most_three_tags_are_offered(session) -> None:
    for text in ("Lecture on entropy and heat", "Lecture on entropy and work"):
        manager.create_entry(session, text, category_name="Uni", tags=["entropy", "heat", "lecture", "physics", "work"])
    session.commit()
    offered = tagging.suggest(session, "Lecture on entropy, heat, work and physics", have=[])
    assert len(offered) == tagging.TAG_LIMIT == 3, offered
