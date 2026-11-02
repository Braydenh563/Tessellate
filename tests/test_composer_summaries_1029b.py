"""Summaries and the digest on notes with settings or lists (audit 1029 rank 55; C35, X19).

The class: a summary or a digest was cut from the raw note text, so a note's
settings block ("---", "tags: [meeting]") was quoted as its content, a title
was said again as the summary, a bare label ("Actions:") stood where its text
was cut, label lines ran into the next sentence, and a note that is only a
list had "too little in it" or a pile of items. Each rule runs over the shapes
of its class, in Ask (`notes_only`) with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import composer, composer_study, study
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_frames_1029 import FAMILIES, _notes
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

FRONT = "---\ntags: [meeting]\ndate: 2026-10-27\n---\n"
EXTRA = [
    ("Todo", D(2026, 10, 22, 9)),
    (FRONT + "# Standup\n\nShipped the beta. Next up is the review.", D(2026, 10, 27, 9)),
    ("---\ntags: [meeting]\n---\nRecording transcript: we agreed to ship on Friday.", D(2026, 10, 26, 9)),
    ("---\ntags: [idea]\naliases: [shower thought]\n---\n# Graph by theme\n\nWhat if the graph clustered by theme? It could use the tags.", D(2026, 10, 20, 9)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when in [*_notes(FAMILIES[0]), *EXTRA]:
        entry = manager.create_entry(session, text, "Personal")
        entry.created_at = entry.updated_at = when
    session.commit()
    return lambda question: _ask(client, question, notes_only=True, answer_from="notes")["text"]


# --- X19: a settings block is never the note's words ----------------------------------------

SETTINGS = re.compile(r"^---\s*$|\btags:|\bdate: 20|\baliases:|\btags note\b", re.M)


@pytest.mark.parametrize("question", [
    "summarise the standup note", "sum up the standup", "give me a summary of standup", "tl;dr the standup note",
    "what did the meeting recording say", "what was agreed in the meeting", "tell me about the standup",
    "what do I have on the recording transcript", "what did I write about the graph", "summarise graph by theme",
])
def test_a_settings_block_is_never_quoted(ask, question):
    said = ask(question)
    assert not SETTINGS.search(said), f"{question}\n{said}"


@pytest.mark.parametrize(("content", "title"), [
    (FRONT + "# Standup\n\nShipped.", "Standup"),
    ("---\ntags: [a]\n---\nPlain first line\n\nMore.", "Plain first line"),
    ("# No settings\n\nBody.", "No settings"),
])
def test_the_title_comes_after_the_settings_block(content, title):
    assert study.title_of(content) == title


def test_a_note_view_starts_its_body_after_the_settings_block():
    view = composer.read_note({"id": 1, "content": FRONT + "# Standup\n\nShipped the beta.", "created_at": "2026-10-27T09:00:00", "category": "Personal", "tags": []}, 0)
    assert view.title == "Standup"
    assert not any("tags" in s.text or s.text.strip() == "---" for s in view.sentences), [s.text for s in view.sentences]


def test_the_summary_sections_skip_the_settings_block():
    texts = [t for _h, sents in study.summary(FRONT + "# Standup\n\nShipped the beta. Next up is the review.") for t in sents]
    assert texts and not any("tags" in t or "---" in t for t in texts), texts


# --- C35: a title is not a summary, a label is not a sentence ---------------------------------


@pytest.mark.parametrize("content", [
    "Todo", "# Todo", "# Todo\n\nTodo", "Todo\n\nTodo.", "# Notes\n\n## Notes\n\nNotes",
])
def test_a_title_is_never_the_summary(content):
    assert study.summary(content) == [], study.summary(content)


@pytest.mark.parametrize("pick", ["Actions:", "- Attendees:", "**Decisions**:", "Next steps:", "  Notes:  "])
def test_a_bare_label_is_not_a_sentence(pick):
    assert not study._says_something(pick, set())


@pytest.mark.parametrize("pick", ["Attendees: Sara, Tom, Priya", "Shipped the beta.", "Decision: ship the beta by 15 December"])
def test_a_label_with_its_text_is_kept(pick):
    assert study._says_something(pick, set())


def test_a_sentence_equal_to_the_title_is_dropped():
    assert study._says_something("Standup", {"standup"}) is False
    assert study._says_something("Standup notes for Friday.", {"standup"}) is True


@pytest.mark.parametrize(("sents", "said"), [
    (["Attendees: Sara, Tom, Priya", "Decisions: ship the beta by 15 December"], "Attendees: Sara, Tom, Priya. Decisions: ship the beta by 15 December."),
    (["Shipped the beta.", "Next up is the review?"], "Shipped the beta. Next up is the review?"),
    (["One", "Two!", "Three…"], "One. Two! Three…"),
    (["Ends with a label:"], "Ends with a label:"),
])
def test_label_lines_are_not_glued_to_the_next_sentence(sents, said):
    assert composer_study._stopped(sents) == said


def test_the_kickoff_summary_does_not_glue_its_labels(ask):
    said = ask("summarise the Project Atlas kickoff meeting")
    assert not re.search(r"Priya Decisions|Tom, Priya\s+Decisions", said), said
    assert "Attendees: Sara, Tom, Priya." in said, said


# --- a note that is only a list --------------------------------------------------------------


@pytest.mark.parametrize(("content", "gist"), [
    ("# Gear\n\n- [ ] tent\n- [ ] stove\n- [ ] torch", ("checklist", ["tent", "stove", "torch"], 0)),
    ("# Chores\n\n- [x] sweep\n- [ ] mop\n- [X] bins", ("checklist", ["sweep", "mop", "bins"], 2)),
    ("# Chores\n\n- [x] sweep\n- [x] mop", ("checklist", ["sweep", "mop"], 2)),
    ("# Films\n\n- Alien\n- Heat", ("list", ["Alien", "Heat"], 0)),
    ("Reading list\n\nThe Overstory\nDune", ("list", ["The Overstory", "Dune"], 0)),
    (FRONT + "# Gear\n\n- [ ] tent", ("checklist", ["tent"], 0)),
])
def test_list_gist_reads_the_shapes_of_a_list_note(content, gist):
    assert study.list_gist(content) == gist


@pytest.mark.parametrize("content", [
    "Todo", "# Standup\n\nShipped the beta. Next up is the review.", "# Film\n\n- Alien", "# Plan\n\nBuild up to a half marathon by March.\nThen rest.",
])
def test_list_gist_is_none_for_a_note_that_says_something_else(content):
    assert study.list_gist(content) is None


def test_a_checklist_note_is_summarised_by_its_items_and_counts(ask):
    said = ask("summarise the Atlas follow-ups")
    assert "checklist of 3 items, none ticked" in said and "too little" not in said, said
    said = ask("summarise the Lisbon packing list")
    assert "passport" in said and "too little" not in said, said


def test_a_bare_list_note_is_summarised_by_its_items(ask):
    said = ask("summarise Reading list")
    assert "list of 2 items" in said and "Thinking, Fast and Slow" in said and "The Overstory" in said, said


def test_a_title_only_note_has_too_little_to_summarise(ask):
    assert "too little in it to summarise" in ask("summarise the Todo note")


@pytest.mark.parametrize(("items", "ticked", "said"), [
    (["a", "b", "c"], 0, "none ticked"), (["a", "b", "c"], 3, "all ticked"), (["a", "b", "c"], 1, "1 ticked"), (["a"], 0, "1 item,"),
])
def test_the_list_summary_counts_what_is_ticked(items, ticked, said):
    rows = "\n".join(f"- [{'x' if i < ticked else ' '}] {item}" for i, item in enumerate(items))
    out = composer_study._list_said({"id": 3, "title": "Gear", "content": f"# Gear\n\n{rows}"})
    assert said in out, out


def test_a_long_list_is_cut_and_says_how_many_more():
    rows = "\n".join(f"- [ ] item {i}" for i in range(9))
    out = composer_study._list_said({"id": 3, "title": "Gear", "content": f"# Gear\n\n{rows}"})
    assert "9 items" in out and "and 3 more" in out and "item 8" not in out, out
