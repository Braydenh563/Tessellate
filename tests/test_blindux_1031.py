"""Blind test 2026-10-31 (blind-1031.md, friction items 3 to 10): each test pins a class."""

from __future__ import annotations

import json

import pytest

from tessellate.ai import composer_digest
from tests._objmove_node import JS, needs_node, run
from tessellate.entry import manager


def _ask(client, question: str) -> dict:
    text, mode = "", None
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        for line in response.iter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "answer":
                text += event["delta"]
            elif event["type"] == "meta":
                mode = event.get("search_mode")
    return {"text": text, "mode": mode}


@pytest.fixture
def trip(session):
    manager.create_entry(session, "# Things to do\n\nOn the trip, see the castle and the tram.", category_name="Journal")
    manager.create_entry(session, "# Flight\n\nTP 303 from Gatwick at 7:45.", category_name="Journal")
    manager.create_entry(session, "# Hotel\n\nBooked near the river for three nights.", category_name="Journal")


@pytest.mark.parametrize("question", [
    "what do I know about my trip?",
    "What do I know about the trip?",
    "tell me about my trip",
])
def test_i3_a_words_only_search_never_claims_the_only_note(client, trip, question):
    got = _ask(client, question)
    assert got["mode"] == "keyword", got
    said = got["text"].lower()
    assert "only note" not in said and "just the one note" not in said, said
    #: Worded in turn like the claim it replaces (INBOX 870 variants).
    assert "those words" in said and "search by meaning" in said, said


def test_i3_every_voice_of_the_only_note_line_is_known():
    lines = composer_digest.only_note_lines()
    assert "So far this is your only note on it." in lines
    assert "This is the only note on that." in lines
    assert all(isinstance(line, str) and line for line in lines)


def _function_body(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start)]


def test_i3_every_way_to_a_note_opens_it_out_and_focuses_it():
    """Item 3: "Open note" lands on the note itself (its row opened out, focus on
    it as a click leaves it), not the list with a two-second flash."""
    from tests._app_js import app_js_text

    body = _function_body(app_js_text(), "flashEntry")
    assert "expandedRows.add(id)" in body
    assert "card.focus(" in body


@needs_node
def test_i4_the_move_rows_have_icons_and_lead_the_menu_in_custom_order():
    out = run(["obj-ref.js", "obj-clip.js", "obj-drag.js", "obj-order.js", "obj-reorder.js"], """
    globalThis.$ = () => null;
    const moves = OBJ_MENU_ROWS.filter((r) => r.moves).map((r) => [r.label, r.icon]);
    __out({ moves, hint: OBJ_ORDER_HINT });
    """)
    assert out["moves"] == [["Move up", "arrow-up"], ["Move down", "arrow-down"]]
    assert "Drag" in out["hint"] and "Alt+Up" in out["hint"] and "Alt+Down" in out["hint"]
    assert "\u2014" not in out["hint"] and "!" not in out["hint"]


def test_i4_the_folded_more_button_is_named_sort_and_view():
    text = (JS / "phone-shell.js").read_text(encoding="utf-8")
    body = _function_body(text, "nameFoldedButton")
    assert '"Sort and view"' in body and "aria-label" in body
    assert "nameFoldedButton(menu" in _function_body(text, "foldZoneIntoMenu")


@pytest.mark.parametrize(("question", "topic"), [
    ("Where do I see questions my notes leave open?", "open-questions"),
    ("where are the questions my notes leave open", "open-questions"),
    ("which questions are still unanswered in my notes", "open-questions"),
    ("What questions have I left unanswered?", "open-questions"),
    ("How do I put my notes in my own order?", "object-move"),
    ("put my notes in my own order", "object-move"),
    ("can I arrange my notes my own way", "object-move"),
    ("How do I make a diagram?", "make-a-diagram"),
    ("make a diagram of my trip", "make-a-diagram"),
    ("how can I draw a diagram without a model", "make-a-diagram"),
])
def test_i5_the_guide_answers_the_blind_testers_three_goals(client, question, topic):
    """`client` boots the app, which installs the act reader: "put my notes in
    my own order" read as the append act ("put X in Y") only with it."""
    from tessellate.ai import help_chat

    assert help_chat.topics_for(question)[0]["id"] == topic, [t["id"] for t in help_chat.topics_for(question)]


@needs_node
def test_i6_read_notes_now_says_what_it_read_and_found():
    out = run(["questions-view.js"], """
    __out([questionsReadSummary(3, 2), questionsReadSummary(1, 1), questionsReadSummary(0, 0), questionsReadSummary(4, -1)]);
    """)
    assert out == ["Read 3 notes, found 2 new questions.", "Read 1 note, found 1 new question.",
                   "Read 0 notes, found 0 new questions.", "Read 4 notes, found 0 new questions."]


def test_i6_the_empty_state_says_a_question_mark_is_what_counts():
    text = (JS / "questions-view.js").read_text(encoding="utf-8")
    assert "end in a question mark" in text and "A to-do is not a question" in text
    assert "toast(questionsReadSummary(" in text


@needs_node
def test_i7_housekeeping_that_worked_is_not_a_bell_row_but_its_failure_is():
    out = run(["chat-tasks.js"], """
    globalThis.QUIET_TASK_KINDS = new Set(["job-warm", "job-warm-filing", "reindex"]);
    const ended = (kind, outcome) => taskEndingIsUpkeep({ kind, outcome });
    __out([ended("warm", "completed"), ended("warm", "failed"), ended("reindex", "completed"), ended("import", "completed"), ended("", "completed")]);
    """)
    assert out == [True, False, True, False, False]


@needs_node
def test_i7_the_filings_to_check_line_needs_a_running_model():
    out = run(["notes-lazy.js"], """
    const wanted = (status) => { globalThis.modelStatus = status; return reviewNudgeWanted(); };
    __out([wanted(null), wanted({ ollama_running: false }), wanted({ ollama_running: true })]);
    """)
    assert out == [False, False, True]


@needs_node
def test_i8_a_greeting_made_for_an_empty_notebook_is_not_kept_once_notes_exist():
    source = _function_body((JS / "dashboard.js").read_text(encoding="utf-8"), "greetingCacheSlot") + "\n}\n"
    out = run([], source + """
    globalThis.prefsCache = { display_name: "Sam" };
    const when = new Date(2026, 9, 31, 9, 0);
    const slot = (count) => { globalThis.allEntries = Array.from({ length: count }, () => ({})); return greetingCacheSlot(when); };
    __out([slot(0) === slot(0), slot(0) === slot(3), slot(3) === slot(9), slot(1) === slot(3)]);
    """)
    assert out == [True, False, True, False]


def test_i9_the_tidy_button_says_what_its_number_counts_and_most_used_says_what_x4_is():
    tidy = (JS / "tidy.js").read_text(encoding="utf-8")
    assert '${count.textContent} ${body.total === 1 ? "thing" : "things"} to look at' in tidy
    status = (JS / "status.js").read_text(encoding="utf-8")
    assert "Opened or asked about" in status and "count.title" in status
