"""One table of 36 phrasings for the no-model composer (owner, 2026-10-25:
"very mediocre", "responses are exactly the same").

Each row is a way a person asks, with what the reply must hold and must not.
The clock is fixed (Wednesday 21 October 2026) and the notes carry fixed
dates, so the table reads the same on any day. Intents: how-to questions
about the app (answered from the Guide's topics), counts, "what did I do"
over a day or a week, comparing two notes, defining a term from the notes."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import notebook_stats
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)
NOTES = [
    ("# Harbor launch plan\n\nShip the mobile app on 14 November. Three gates first: beta feedback, onboarding, pricing. Owner is Ana.", "Work", dt.datetime(2026, 10, 20, 9)),
    ("# Dentist\n\nCheck-up booked for the 21st. Ask about the night guard.", "Health", dt.datetime(2026, 10, 14, 9)),
    ("# Sourdough log\n\nHydration 75 percent. Starter doubled in four hours. Levain means a portion of starter built up before the dough.", "Cooking", dt.datetime(2026, 10, 20, 18)),
    ("# Garden jobs\n\nPrune the roses. Buy compost. Mulch is a layer of material spread over soil to hold moisture.", "Home", dt.datetime(2026, 10, 19, 8)),
    ("# Trip to Lisbon\n\nFlights booked for 3 December. Hotel near the river. Pack a rain jacket.", "Travel", dt.datetime(2026, 10, 9, 8)),
    ("# Trip to Porto\n\nTrain from Lisbon on 6 December. Hotel by the station. Try the port cellars.", "Travel", dt.datetime(2026, 10, 10, 8)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    monkeypatch.setattr(notebook_stats, "utcnow", lambda: NOW)
    for text, category, when in NOTES:
        manager.create_entry(session, text, category).created_at = when
    session.commit()

    def go(question: str, **body) -> str:
        return _ask(client, question, notes_only=True, answer_from="notes", **body)["text"]

    return go


#: (question, must match, must not match)
ROWS = [
    # --- how-to questions about the app, from the Guide's topics -----------
    ("how do I add a reminder", r"Reminders", r"couldn't find"),
    ("how can I pin a note", r"pin", r"couldn't find"),
    ("where do I change the theme", r"Appearance", r"couldn't find"),
    ("how do you link two notes", r"\[\[", r"couldn't find"),
    ("how do I turn on web search", r"[Ww]eb", r"couldn't find"),
    ("how do I make a private note", r"[Pp]rivate", r"couldn't find"),
    # --- counts and stats ---------------------------------------------------
    ("how many notes do I have", r"\b6 notes\b", r""),
    ("how many notes did I write this week", r"\b3 notes\b", r""),
    ("how many travel notes do I have", r"\b2 notes\b.*Travel|Travel.*\b2\b", r"\b6 notes\b"),
    ("how many notes are in Work", r"\b1 note\b", r"\b6 notes\b"),
    ("how many notes per category", r"Travel \(?2\)?.*Work|Travel.*2", r"You have 5 categories\.$"),
    ("which category has the most notes", r"Travel", r""),
    ("how many words have I written", r"words", r""),
    # --- what did I do over a day or a week ---------------------------------
    ("what did I do yesterday", r"Sourdough log.*Harbor launch plan|Harbor launch plan.*Sourdough log", r"Dentist"),
    ("what did I write yesterday", r"Sourdough log", r"Dentist"),
    ("what did I do last week", r"Dentist", r"\*\*Sourdough"),
    ("what did I write on Monday", r"Garden jobs", r"Dentist"),
    ("anything I added on Monday", r"Garden jobs", r"couldn't find"),
    ("what did I do last month", r"[Nn]othing|no notes|none|didn't|did not|haven't", r""),
    # --- compare two notes --------------------------------------------------
    ("compare Trip to Lisbon and Trip to Porto", r"3 December.*6 December|6 December.*3 December", r""),
    ("what is the difference between the Lisbon trip and the Porto trip", r"3 December.*6 December|6 December.*3 December", r""),
    ("compare my notes on Lisbon and Porto", r"3 December.*6 December|6 December.*3 December", r""),
    ("Lisbon vs Porto", r"3 December.*6 December|6 December.*3 December", r""),
    ("how does the Lisbon trip differ from the Porto trip", r"3 December.*6 December|6 December.*3 December", r""),
    # --- define a term from the notes ---------------------------------------
    ("define levain", r"portion of starter", r"do not mention|“define”"),
    ("what does mulch mean in my notes", r"layer of material", r"do not mention"),
    ("what does levain mean", r"portion of starter", r"do not mention"),
    ("meaning of levain", r"portion of starter", r"do not mention"),
    ("define mulch", r"layer of material", r"do not mention|“define”"),
    ("what is mulch", r"layer of material", r"do not mention"),
    # --- facts the notes hold, and small talk ---------------------------------
    ("when is the dentist", r"21st", r""),
    ("what is the harbor launch plan", r"14 November", r""),
    ("what are the three gates", r"beta feedback", r""),
    ("hello", r"\?|help|look|find|ask", r"couldn't find"),
    ("thanks", r".", r"couldn't find"),
    ("how are you", r".", r"couldn't find"),
]


@pytest.mark.parametrize(("question", "must", "must_not"), ROWS, ids=[r[0] for r in ROWS])
def test_the_phrasing_is_answered(ask, question, must, must_not):
    text = ask(question)
    assert re.search(must, text, re.S), text
    if must_not:
        assert not re.search(must_not, text, re.S), text


def test_the_table_is_at_least_thirty_phrasings():
    assert len(ROWS) >= 30


def test_replies_to_different_questions_do_not_all_end_alike(ask):
    """The next-step line was the same sentence under every answer."""
    tails = {
        ask(q).strip().splitlines()[-1]
        for q in ("when is the dentist", "what is the harbor launch plan", "what are the three gates", "what is hydration", "what is the Lisbon trip")
    }
    assert len(tails) >= 3, tails


def test_a_retry_words_the_answer_anew(ask):
    texts = {ask("what is the harbor launch plan", attempt=n) for n in range(4)}
    assert len(texts) >= 2


def test_fixed_phrases_come_in_variants(ask):
    """"It's your only note on that so far" is one of several wordings."""
    said = {
        line
        for q in ("what is the harbor launch plan", "when is the dentist", "what is hydration", "what are the three gates", "what is the Lisbon trip", "what is the Porto trip")
        for line in ask(q).splitlines()
        if "only note" in line or "only one" in line
    }
    assert len(said) >= 2, said


def test_a_question_about_my_own_doings_never_goes_to_the_web():
    """The owner, 2026-10-26: "what did I do last week?" (the composer's own
    suggestion) went to web search and reported SearXNG down."""
    from tessellate.ai import personal

    asked = [personal.about_own_notes(q) for q in ("what did I do last week?", "what did I edit yesterday", "show my history")]
    general = [personal.about_own_notes(q) for q in ("what's the capital of France", "how do I do a backflip")]
    assert asked == [True, True, True] and general == [False, False]


def test_persona_cues_are_whole_words_and_formal_reads_the_professional_lines():
    from tessellate.ai import composer_compose, composer_tables

    assert composer_compose.persona_cue("an expert in functional programming and directory layouts") == ""
    assert composer_compose.persona_cue("a witty, fun pirate") == "playful"
    assert composer_tables.voice_of("formal") == "professional"


def test_when_is_next_is_linear_on_a_run_of_spaces():
    import time

    from tessellate.ai import composer_plan

    start = time.perf_counter()
    composer_plan._WHEN_IS_NEXT.match("a" + " " * 20000 + "x")
    assert time.perf_counter() - start < 0.5


def test_own_doings_need_a_time_word_or_the_question_shape():
    from tessellate.ai import personal

    for q in ("what did I do last week?", "what did I edit yesterday", "show my history", "notes I edited today"):
        assert personal.about_own_notes(q), q
    for q in ("my work visa rules", "what changed in Python since we added type hints", "how is my day in Tokyo time"):
        assert not personal.about_own_notes(q), q


def test_a_note_opening_on_its_own_day_is_dated_once_and_reported():
    """The owner, 2026-10-26: "on september 21 is repeated twice" and "I had
    work not have"."""
    from tessellate.ai import composer_digest

    said, _ = composer_digest._dated_line(
        "on 21 September, you have work. You need to finish your IT assignment, which is due on Friday.",
        "21 September", 1,
        dt.date(2026, 10, 26), dt.date(2026, 9, 21), dt.date(2026, 9, 5),
    )
    assert said.count("21 September") == 1
    assert "you had work" in said and "you have work" not in said
    #: "it was due that friday, not this friday".
    assert "You needed to finish" in said and "was due that Friday" in said


def test_every_invitation_offers_an_ask():
    """The hello row above failed once the rotation landed on an invite that
    named the note but asked nothing ("Carry on from your latest note with
    ..."): every invite, in both voices, now says what to ask."""
    from tessellate.ai import composer

    for voice, lines in composer.INVITES.items():
        for line in lines:
            assert re.search(r"\?|help|look|find|ask", line), (voice, line)
