"""Composer rows closed 2026-11-12 (ledger L21 to L44, L116, L117, L120, L191).

Fixed clock: the showcase fixture's own day (`tests/fixtures/composer/showcase_725.json`).
Rows that were already built or did not reproduce keep a test here so they stay so.
"""

from __future__ import annotations

import re
import pytest

from tessellate.ai import composer, composer_select, composer_tables, factgraph
from tests import _composer_eval as ev

DATA = ev.load()
TODAY = ev.today(DATA)


def _ask(question: str, **kwargs) -> dict:
    entry = next(q for q in DATA["questions"] if q["question"] == question)
    notes = ev.notes_for(entry, DATA)
    result = composer.compose(question, notes, today=TODAY, **kwargs)
    assert ev.trace_failures(result, question, notes, TODAY) == []
    return result


# --- L28, L116: a note about the subject is quoted past its first sentence -------------


def test_a_note_named_for_the_subject_is_quoted_beyond_one_sentence():
    text = _ask("What do I know about sourdough?")["text"]
    #: Sourdough log is named for it: its second sentence comes too.
    assert "Loaf 6: 78% hydration, 20 hour cold proof. Best crumb yet, still pale underneath." in text
    #: Pizza night only mentions it in passing: one sentence.
    assert text.count("From your **Pizza night** note") == 1
    assert "48 hour dough" not in text


# --- L29: the harbor launch date is the dated sentence of the plan --------------------


def test_one_line_for_when_is_the_harbor_launch_quotes_the_dated_sentence():
    from tessellate.ai import composer_voice

    entry = next(q for q in DATA["questions"] if q["question"] == "What is the Harbor launch plan?")
    line = composer_voice.one_line("when is the harbor launch?", ev.notes_for(entry, DATA), today=TODAY)
    assert "on the 14th of next month" in line["text"]
    assert line["grounding"][0]["note_id"] == 1


# --- L32: a count of things is a count, a measure is a quantity -----------------------


def _kinds(content: str) -> dict:
    return {f.kind: f.attrs for f in factgraph.facts({"id": 1, "content": content, "created_at": "2026-10-01T09:00:00"}) if f.kind in ("quantity", "count")}


@pytest.mark.parametrize(("content", "kind"), [
    ("# N\n\nDid 5 sets of squats.", "count"),
    ("# N\n\nThere were 5 people there.", "count"),
    ("# N\n\nRan 5 km before work.", "quantity"),
    ("# N\n\nLifted 80 kg.", "quantity"),
])
def test_a_counted_thing_is_a_count_and_a_unit_is_a_quantity(content, kind):
    assert kind in _kinds(content)
    assert ({"quantity", "count"} - {kind}).isdisjoint(_kinds(content))


def test_a_plural_looking_word_that_is_no_thing_is_not_counted():
    assert _kinds("# N\n\nWalked 10 minutes across the park, 2 less than before.") == {}


# --- L39: a titled note's name lends only two sentences ---------------------------------


def test_a_note_named_for_the_subject_keeps_two_sentences_that_score_on_its_name_alone():
    note = {
        "id": 1,
        "content": "# Dentist visits\n\nBooked for 3 March. Cleaning on 9 April. Follow-up on 14 May. Crown fitting on 2 June. X-ray on 20 June.",
        "created_at": "2026-01-01T09:00:00",
        "tags": [],
        "category": "health",
    }
    kept = composer.brief("when is the dentist appointment", [note])["notes"][0]["content"]
    assert kept.count(" on ") + kept.count("Booked") == 2, kept
    assert composer_select.TITLE_ONLY_PER_NOTE == 2


# --- L117, L191: endings and chips -------------------------------------------------------


def test_no_showcase_answer_ends_in_a_bracketed_note_and_date():
    for entry in DATA["questions"]:
        text = composer.compose(entry["question"], ev.notes_for(entry, DATA), today=TODAY)["text"]
        assert not re.search(r"\[your note,[^\]]*\]\s*$", text), text


def test_a_yes_or_no_question_does_not_offer_its_own_predicate_as_a_subject():
    entry = next(q for q in DATA["questions"] if q["question"] == "Does Harbor work offline?")
    result = composer.compose(entry["question"], ev.notes_for(entry, DATA), today=TODAY)
    assert not any("work offline" in chip for chip in result["next"]), result["next"]


# --- L27: no fixed frame has a plain slip -----------------------------------------------


def _frames() -> set[str]:
    found: set[str] = set()

    def walk(value) -> None:  # noqa: ANN001
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, (list, tuple, set)):
            for v in value:
                walk(v)

    walk(composer.PHRASES)
    for name in dir(composer_tables):
        if name.isupper():
            walk(getattr(composer_tables, name))
    #: A pattern (a regex the frames table also holds) is not a sentence.
    return {s for s in found if len(s) > 3 and not s.startswith("^") and "(?" not in s}


SLIPS = [
    (re.compile(r"\ban (?=[bcdfgjklmnpqrstvwxz]\w)", re.I), "an before a consonant"),
    (re.compile(r"\ba (?=[aeiou]\w)(?!(?:one|use|user|unit|uni|usual|european)\b)", re.I), "a before a vowel"),
    (re.compile(r"\b(\w+) \1\b", re.I), "a word twice"),
    (re.compile(r"[a-z]  +[a-z]"), "a double space"),
    (re.compile(r" [,;:!?]"), "a space before a mark"),
    (re.compile(r"\b(?:1|one) notes\b|\bthey has\b|\bit have\b", re.I), "agreement"),
]


def test_no_fixed_answer_frame_has_a_plain_grammar_slip():
    bad = [(why, s) for s in sorted(_frames()) for rx, why in SLIPS if rx.search(s)]
    assert bad == []


# --- L43, L44: the day's notes are listed whole, never "From today:" or "it has ... and it has" ----


def test_a_days_notes_are_listed_without_a_from_today_line_or_joined_fragments():
    notes = [
        {"id": 1, "content": "# Sourdough log\n\nLoaf 6: 78% hydration. Best crumb yet. Next time the stone goes lower.", "created_at": "2026-10-06T09:00:00", "tags": [], "category": "cooking"},
        {"id": 2, "content": "# Gym\n\nWent to the gym this morning. Did squats and deadlifts.", "created_at": "2026-10-06T10:00:00", "tags": [], "category": "fitness"},
    ]
    for question in ("summarise today", "what did I write today", "summarise my notes from today"):
        text = composer.compose(question, notes, today=TODAY)["text"]
        assert "From today" not in text, text
        assert not re.search(r"\bit has [^.]* and it has\b", text), text
