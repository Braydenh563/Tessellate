"""Five classes of composer wording the audit left open (composer-1031, the
owner's INBOX 1357: fix the class, each tested several ways, on a fixed clock).

1. A measure sum (how far, how many km) names a title-less note by a short
   noun phrase, never by its whole line, and says the figure once.
2. The closing line never quotes a note's line as a place or says what the
   screen shows (that closing needs a screen).
3. No opener says "Here is the answer."
4. A title or a name keeps its capital inside a fragment ("Myers chapters").
5. "Show me my study notes" and "what do my notes say about university" are
   overviews; "list my notes oldest first" lists every note in that order; a
   month keeps its capital.

Fixed clock: Friday 30 October 2026 (`tests/_seed_1030.py`, and the
`tests/test_composer_timing_1461.py` notebook).
"""

from __future__ import annotations

import re

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer_frame, composer_lines, composer_tone
from tessellate.api import bounds, routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask
from tests.test_composer_timing_1461 import MORE, NOTES, NOW


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch)
    return lambda q: go(q)[0]


@pytest.fixture
def ask_chat(client, session, monkeypatch):
    seed_1030.seed(session)
    go = seed_1030.asker(client, monkeypatch, chat=True)
    return lambda q: go(q)[0]


@pytest.fixture
def uni(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when in NOTES + MORE:
        entry = manager.create_entry(session, text, category_name="Courses & study", tags=["university"])
        entry.created_at = entry.updated_at = when
    session.commit()
    return lambda q: _ask(client, q, use_tools=False, notes_only=True, answer_from="notes")["text"]


# 1. A title-less note is named by a noun phrase in a measure sum.

RAN = ["how far did I run", "how many km did I run", "how many kilometres have I run in total", "what is the total distance I ran",
       "how many km I ran"]


@pytest.mark.parametrize("question", RAN)
def test_a_measure_names_a_titleless_note_by_a_phrase_not_its_line(ask, question):
    said = ask(question)
    assert "your note on the run" in said, said
    assert "Felt really good" not in said and "without stopping" not in said, said
    #: The note's own "6 km" is said once, as its figure.
    assert len(re.findall(r"\b6 (?:km|kilometres)\b", said)) == 1, said
    assert re.search(r"\b19 (?:km|kilometres)\b", said), said


def test_a_measure_with_a_noun_and_a_bare_pronoun_is_the_doing_not_the_subject(ask):
    said = ask("what is the total distance I ran")
    assert " on I ran" not in said and " on i ran" not in said, said


@pytest.mark.parametrize("line, wanted", [
    ("Felt really good after the run today, 6 km without stopping", "your note on the run"),
    ("Felt great after the swim this morning, 1 km easy", "your note on the swim"),
    ("Felt tired after the ride yesterday, 30 km", "your note on the ride"),
])
def test_a_feeling_line_is_named_by_what_it_is_about(line, wanted):
    assert composer_frame.short_name({"content": line}) == wanted


# 2. The closing never quotes a line as a place.

@pytest.mark.parametrize("title", ["I just missed the bus to uni today", "Coffee with Anna on Saturday at Brunetti", "Weekly review"])
@pytest.mark.parametrize("seed", ["a", "b", "c", "d", "e", "f", "g", "h"])
@pytest.mark.parametrize("newest", [True, False])
def test_the_closing_never_says_it_can_see_or_puts_you_in_a_note(title, seed, newest):
    line = composer_tone.closing(recent=[title], seed=seed, newest=newest)
    assert line and "I can see" not in line and "you've been in" not in line and "been working on" not in line, line


def test_every_closing_wording_is_free_of_a_screen_or_a_place():
    for ability in ("close_next", "close_cited"):
        for cand in composer_lines.FRAMES[ability]:
            assert "I can see" not in cand.text and "you've been in" not in cand.text, cand.text


# 3. No "Here is the answer." opener.

def test_no_opener_is_the_bare_here_is_the_answer():
    assert not [c.text for c in composer_lines.OPENERS if "here is the answer" in c.text.lower()]


@pytest.mark.parametrize("question", ["list my work notes", "show me my baking notes", "list my notes about running", "list my travel notes"])
def test_a_list_reply_does_not_lead_with_here_is_the_answer(ask, question):
    assert "here is the answer" not in ask(question).lower()


# 4. A capital the title carries is kept inside a fragment.

@pytest.mark.parametrize("line, kept", [
    ("Myers chapters 1 to 3, the stats primer", "Myers"),
    ("Lisbon trip", "Lisbon"),
    ("Jean Piaget stages of development", "Piaget"),
    ("Dunning Kruger effect notes", "Dunning"),
])
def test_a_title_keeps_its_capital(line, kept):
    assert kept in composer_frame.short_name({"content": line})


def test_a_plain_phrase_is_still_lowered_in_a_frame():
    said = composer_frame.short_name({"content": "Watched a movie review show"})
    assert "movie review" in said and "Movie" not in said, said


@pytest.mark.parametrize("question", ["what is on my reading list", "what's on my reading list", "what did I write down about my reading list"])
def test_the_reading_list_keeps_myers(uni, question):
    said = uni(question)
    assert "Myers chapters" in said and "myers" not in said, said


# 5. Overviews, an order, a month.

@pytest.mark.parametrize("question", [
    "show me my study notes", "what do my notes say about university", "what do my notes say about uni",
    "what do the notes say about university", "give me all my study notes", "get my study notes",
])
def test_a_study_ask_reaches_the_notes_on_it(uni, question):
    said = uni(question)
    assert re.search(r"\b(?:ten|10) notes (?:about|on) (?:study|university|uni)\b", said), said
    assert "give me all" not in said, said


@pytest.mark.parametrize("question", [
    "list my notes oldest first", "show my notes oldest first", "my notes, oldest first", "list all my notes in order",
    "show me my notes in chronological order", "sort my notes by date", "list my notes from oldest to newest",
])
def test_notes_listed_oldest_first_start_at_the_oldest(ask_chat, question):
    lines = [line for line in ask_chat(question).split("\n") if line.startswith("- ")]
    assert lines and "Apartment" in lines[0] and "31 August" in lines[0], lines
    assert "nothing in your notes about" not in " ".join(lines).lower()


@pytest.mark.parametrize("question", [
    "list my notes newest first", "show my notes newest first", "my notes, newest first", "list the notes from newest to oldest",
    "list my notes in reverse order", "list my notes latest first",
])
def test_notes_listed_newest_first_start_at_the_newest(ask_chat, question):
    lines = [line for line in ask_chat(question).split("\n") if line.startswith("- ")]
    assert lines and "Weekly review" in lines[0] and "30 October" in lines[0], lines


@pytest.mark.parametrize("question", ["Notes in October", "notes in october", "list my notes in October", "show my notes from October", "NOTES IN OCTOBER"])
def test_a_month_keeps_its_capital(ask_chat, question):
    said = ask_chat(question)
    assert "October" in said and "october" not in said, said


# F14: a run of blanks in a chat request is cut before any reader sees it.

@pytest.mark.parametrize("blanks", [" ", "\t", "\n", " \n "])
def test_a_long_run_of_blanks_is_one_blank(blanks):
    squeezed = bounds.squeeze_blanks(f"where is{blanks * 5000}the bin")
    assert len(squeezed) < 40 and squeezed.startswith("where is") and squeezed.endswith("the bin"), squeezed


def test_a_short_run_and_ordinary_text_are_kept():
    text = "line one\n\nline two,   three  four"
    assert bounds.squeeze_blanks(text) == text


def test_the_chat_request_squeezes_the_question():
    request = routes_chat.ChatRequest(question="hello" + " " * 15000 + "there")
    assert request.question == "hello there"
