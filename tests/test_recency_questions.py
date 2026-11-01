"""Carry-over wrapup-0927 10 (n), the owner at release: "Show me my last
entry" answered with an older note. A recency question lists the newest
notes, and every note in the prompt carries the day it was written (and
edited)."""

import time
from pathlib import Path

from tessellate.search import search_manager


def test_a_recency_question_is_read_as_an_order():
    for q in (
        "show me my last entry",
        "what was my latest note?",
        "my most recent notes",
        "what did I write last?",
        "newest note about the garden",
    ):
        assert search_manager.is_recency_ask(q), q
    for q in ("the last time I went running", "notes about my entry visa", "what did I write about bread"):
        assert not search_manager.is_recency_ask(q), q


def test_the_newest_note_is_first(client, session):
    for text in ("an older note about entries and logs", "the middle one", "the newest thought"):
        client.post("/entries", json={"content": text, "category": "Misc"})
        time.sleep(0.01)
    entries, mode = search_manager.retrieve(session, "show me my last entry", None, 5)
    assert mode == "recent"
    assert "newest thought" in entries[0].content


def test_the_prompt_dates_each_note():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from tessellate.api import routes_chat

    entry = SimpleNamespace(
        created_at=datetime(2026, 9, 3, 10, tzinfo=timezone.utc),
        edited_at=datetime(2026, 9, 25, 10, tzinfo=timezone.utc),
    )
    text = routes_chat._note_dates(entry, timezone.utc)
    assert text == "Thursday 3 September 2026, 10:00, edited Friday 25 September 2026, 10:00"
    entry.edited_at = None
    assert routes_chat._note_dates(entry, timezone.utc) == "Thursday 3 September 2026, 10:00"


def test_the_newest_is_marked_in_the_prompt():
    from tessellate.ai import librarian

    notes = [
        {"content": "the newest", "category": "Misc", "written": "Saturday 3 October 2026, 09:56", "newest": True},
        {"content": "older", "category": "Misc", "written": "Friday 2 October 2026, 18:00"},
    ]
    messages = librarian.build_messages("show me my last entry", notes)
    user = messages[-1]["content"]
    assert "(written Saturday 3 October 2026, 09:56) (my newest note)" in user
    assert user.index("the newest") < user.index("older")


def test_the_recency_pattern_stays_linear_on_long_whitespace():
    # CodeQL 443: `\s*[?.!]?\s*$` backtracked polynomially on a run of tabs.
    import time

    from tessellate.search.search_manager import _RECENCY_ASK, is_recency_ask

    # CodeQL 445: the same after "what did I add lately" and a run of tabs.
    for hostile in ("wrote last" + "\t" * 20000 + "x", "what\tdid\ti\tadd\tlately" + "\t" * 20000 + "x"):
        started = time.perf_counter()
        is_recency_ask(hostile)  # its 300-character slice drops the "x"
        assert not _RECENCY_ASK.search(hostile)
        assert time.perf_counter() - started < 0.5
    assert is_recency_ask("what did I write last  ?  ")
    assert is_recency_ask("What have I saved recently?!")


def test_saved_recently_is_a_recency_question():
    """INBOX 441: "What have I saved recently?" went to a topic search for the
    word "saved", and the answer said the notes said nothing about saving."""
    for q in (
        "What have I saved recently?",
        "what did I write lately",
        "What have I been writing recently?",
        "what have I added recently",
    ):
        assert search_manager.is_recency_ask(q), q
    for q in ("what have I written about golf recently?", "recently I saved money on bread"):
        assert not search_manager.is_recency_ask(q), q


def test_a_notes_time_words_reach_the_model_with_their_dates():
    """INBOX 441: a note written two weeks ago said "this Friday"; the app
    resolved it to Friday 25 September and showed it, the model never saw it
    and read it as this week's Friday."""
    from datetime import datetime

    from tessellate.ai import librarian

    note = {
        "category": "Academics",
        "content": "I need to finish my IT assignment, due this Friday.",
        "written": "Tuesday 22 September 2026, 10:00",
        "dates": [{"phrase": "this Friday", "at": datetime(2026, 9, 25), "precision": "day"}],
    }
    messages = librarian.build_messages("what is due?", [note])
    text = messages[-1]["content"]
    assert '"this Friday" meant Friday 25 September 2026' in text


def test_every_note_path_carries_time_words_with_their_distance():
    """INBOX 441: "make sure the other agents like the popup and chat are aware
    of time relativity as well". Ask, the chat agent, the agent's note tools
    and the digest all say what a note's time words meant, relative to today."""
    from datetime import date

    from tessellate.core.config import days_from_today

    assert days_from_today(date(2026, 9, 25), date(2026, 10, 3)) == "8 days ago"
    assert days_from_today(date(2026, 10, 4), date(2026, 10, 3)) == "tomorrow"
    from tests._help_text import agent_text

    root = Path(__file__).resolve().parent.parent / "src" / "tessellate"
    assert "librarian._dates_hint(note)" in agent_text()
    assert '"when": days_from_today(' in (root / "ai" / "tools" / "_common.py").read_text(encoding="utf-8")
    assert "days_from_today(d.at.date(), now.date())" in (root / "api" / "routes_insights.py").read_text(encoding="utf-8")
    assert '"dates": _time_words(' in (root / "api" / "routes_chat.py").read_text(encoding="utf-8")


def test_with_no_ai_a_recency_question_lists_the_newest_notes():
    """With no model, "What have I saved recently?" said the notes did not
    share enough with the question to quote; the answer is the list."""
    from tessellate.ai import extractive

    notes = [
        {"id": 3, "content": "Grocery list: milk and eggs\nfor Friday", "written": "Saturday 3 October 2026, 09:10"},
        {"id": 2, "content": "Golf practice after work", "written": "Friday 2 October 2026, 18:00"},
    ]
    out = extractive.recent(notes)
    assert out["text"].startswith("Your newest notes")
    assert "Grocery list: milk and eggs" in out["text"] and "Saturday 3 October 2026" in out["text"]
    assert [row["note_id"] for row in out["grounding"]] == [3, 2]
