"""The realiser's rule tables (CHAT_PLAN Phase 6 step 3, decision 33): each
rule a table of input and expected output, and the pairs that show a rule
does not change what a sentence means."""

from __future__ import annotations

from datetime import date

import pytest

from tessellate.ai import realise

TODAY = date(2026, 10, 6)


@pytest.mark.parametrize(
    ("said", "shifted"),
    [
        ("I am going", "you are going"),
        ("I was late", "you were late"),
        ("I've booked it", "you have booked it"),
        ("my notes", "your notes"),
        ("Sam and I met", "you and Sam met"),
        ("am I late", "are you late"),
        ("I went to the gym on Monday and did squats.", "you went to the gym on Monday and did squats."),
        ("I like the morning sessions best.", "you like the morning sessions best."),
        ("I'm not sure about my plan.", "you're not sure about your plan."),
        ("I wasn't there.", "you weren't there."),
        ("I'll call the plumber myself.", "you will call the plumber yourself."),
        ("Priya told me the date.", "Priya told you the date."),
        ("Me and Sam went.", "You and Sam went."),
        ("The bike is mine.", "The bike is yours."),
        ("Was I right?", "Were you right?"),
        ("My plan is simple.", "Your plan is simple."),
        ("We decided to go with Lisbon.", "We decided to go with Lisbon."),
        ("Our flat needs a new boiler.", "Our flat needs a new boiler."),
        # One companion named before "we" in the sentence: the two of them (L-chat-39).
        ("I ran into a uni friend at the stop and we caught the next one.",
         "you ran into a uni friend at the stop and the two of you caught the next one."),
        ("Met my sister and we had lunch.", "Met your sister and the two of you had lunch."),
        ("My sister and her kids came, and we had lunch.", "Your sister and her kids came, and we had lunch."),
        # Someone else's words are theirs.
        ('Sam wrote: "I am not sure we should ship it."', 'Sam wrote: "I am not sure we should ship it."'),
        ('I said "my turn" and left.', 'you said "my turn" and left.'),
        ("Priya said: I need the deck by Friday.", "Priya said: I need the deck by Friday."),
        # Idioms and numerals are not the writer.
        ("Let me know if it slips.", "Let me know if it slips."),
        ("Oh my, the roof leaks.", "Oh my, the roof leaks."),
        ("World War I history reading.", "World War I history reading."),
        ("Fix the I/O error first.", "Fix the I/O error first."),
        ("Part I is done; my notes are in Part II.", "Part I is done; your notes are in Part II."),
    ],
)
def test_shift_person(said, shifted):
    assert realise.shift_person(said) == shifted


def test_a_quoted_fact_is_never_shifted():
    assert realise.shift_person("I am sure", quoted=True) == "I am sure"


def test_first_person_says_whether_anything_would_change():
    assert realise.first_person("I went") and not realise.first_person("Let me know.")


@pytest.mark.parametrize(
    ("text", "due", "said"),
    [
        ("you plan to go on Friday.", date(2026, 10, 2), "you planned to go on Friday."),
        ("you are going again next week.", date(2026, 9, 28), "you were going again next week."),
        ("you will call the plumber.", date(2026, 10, 1), "you were going to call the plumber."),
        ("you want to repaint the shed.", date(2026, 9, 1), "you wanted to repaint the shed."),
        # Still to come, or no day known: unchanged.
        ("you plan to go on Friday.", date(2026, 10, 9), "you plan to go on Friday."),
        ("you plan to go.", None, "you plan to go."),
        # Not a plan: unchanged whatever the day.
        ("you went to the gym.", date(2026, 9, 1), "you went to the gym."),
    ],
)
def test_past_plan(text, due, said):
    assert realise.past_plan(text, due, TODAY) == said


@pytest.mark.parametrize(
    ("day", "said"),
    [
        (date(2026, 10, 6), "today"),
        (date(2026, 10, 5), "yesterday"),
        (date(2026, 10, 2), "on Friday"),
        (date(2026, 9, 29), "last week"),
        (date(2026, 9, 22), "two weeks ago"),
        (date(2026, 9, 8), "four weeks ago"),
        (date(2026, 3, 3), "on 3 March"),
        (date(2025, 3, 3), "on 3 March 2025"),
        (date(2026, 10, 7), "tomorrow"),
        (date(2026, 10, 9), "on Friday"),
        (date(2026, 10, 14), "next week"),
    ],
)
def test_relative_day(day, said):
    assert realise.relative_day(day, TODAY) == said


@pytest.mark.parametrize(
    ("n", "noun", "article", "said"),
    [(1, "note", False, "one note"), (2, "note", False, "two notes"), (1, "day", True, "a day"), (3, "day", False, "three days"),
     (1, "entry", True, "an entry"), (2, "entry", False, "two entries"), (14, "note", False, "14 notes")],
)
def test_count_noun(n, noun, article, said):
    assert realise.count_noun(n, noun, article=article) == said


@pytest.mark.parametrize(
    ("items", "said"),
    [
        (["milk"], "milk"),
        (["milk", "rice"], "milk and rice"),
        (["milk", "rice", "eggs"], "milk, rice and eggs"),
        (["bread", "salt", "fish and chips"], "bread, salt, and fish and chips"),
    ],
)
def test_join_items(items, said):
    assert realise.join_items(items) == said


@pytest.mark.parametrize(
    ("text", "said"),
    [("The hills are steep.", "the hills are steep."), ("Harbor ships soon.", "Harbor ships soon."), ("I went.", "I went."), ("NASA called.", "NASA called.")],
)
def test_after_comma(text, said):
    assert realise.after_comma(text) == said


@pytest.mark.parametrize(
    ("title", "limit", "said"),
    [("Harbor launch plan", 40, "Harbor launch plan"), ("Harbor launch plan for the mobile app", 20, "Harbor launch plan…"), ("Supercalifragilistic", 8, "Superca…")],
)
def test_cut_title(title, limit, said):
    assert realise.cut_title(title, limit) == said


# --- the variety floor (decision 51), measured on every build ---------------------

from tests import _composer_eval as E  # noqa: E402

#: Ten of the showcase questions, one of each answer shape (F0's set).
FLOOR_QUESTIONS = (
    "Who asked for a public API?",
    "How many beta testers are active?",
    "Compare Lisbon and Porto",
    "Does Harbor work offline?",
    "What do I know about sourdough?",
    "How do I sharpen my knife?",
    "What is my half marathon training plan?",
    "How much will the trip cost?",
    "What is the status of the onboarding rewrite?",
    "Which dinners take under 30 minutes?",
)
HELP_QUESTIONS = ("how do I set a reminder", "how do I export my notes", "how do I lock the app")


def _chat(question: str, voice: str) -> list[dict]:
    from tessellate.ai import composer

    data = E.load()
    entry = next((e for e in data["questions"] if e["question"] == question), None)
    notes = E.notes_for(entry, data) if entry else []
    recent = bool(entry) and str(entry.get("search_mode") or "").endswith("recent")
    return [
        composer.compose(question, notes, today=E.today(data), recent=recent, voice=voice, salt="floor", turn=t)
        for t in range(1, realise.VARIETY_TURNS + 1)
    ]


@pytest.mark.parametrize("voice", ["natural", "professional"])
def test_variety_floor_over_a_twenty_turn_chat(voice):
    """Every question opens at least three ways over twenty turns of one chat,
    and says the same facts every turn (protected spans fixed)."""
    low = {}
    for question in FLOOR_QUESTIONS:
        seen = realise.variety(_chat(question, voice))
        assert seen["facts"] == 1, (question, seen)
        if seen["openers"] < realise.VARIETY_FLOOR:
            low[question] = seen["openers"]
    assert not low, low


def test_variety_floor_in_the_help_register():
    for question in HELP_QUESTIONS:
        results = _chat(question, "help")
        assert all(r["shape"] == "help" for r in results), question
        seen = realise.variety(results)
        assert seen["facts"] == 1 and seen["wordings"] >= realise.VARIETY_FLOOR, (question, seen)


@pytest.mark.parametrize(
    ("written", "said"),
    [
        ("I live in Perth and I work part time at the cafe.", "you live in Perth and you work part time at the cafe."),
        ("Then Sam and I left.", "Then you and Sam left."),
        ("Sam and I went to Lisbon.", "you and Sam went to Lisbon."),
        ("I went with Sam and me.", "you went with you and Sam."),
    ],
)
def test_a_place_before_and_i_is_not_a_person_beside_the_writer(written, said):
    """Found probing item 8: "I live in Perth and I work at the cafe" was
    said back as "You live in you and Perth work part time at the cafe"."""
    assert realise.shift_person(written) == said
