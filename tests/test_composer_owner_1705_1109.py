"""The owner's model-off answers (INBOX 1705), from the exact questions: Atlas speaks as
Atlas and lists what it does; the subject of a rambling ask is "eating your homework";
and an answer never quotes tofu, a cut or unclosed quote, a raw arrow or inline bold, a
reported clause with a capital, or a "More loosely related" heading with nothing after it."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_clean
from tessellate.entry import manager

HOMEWORK = "alright, uhh, I think i wrote a note about eating my homework to smth, it was a joke"


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    for content, category in [
        ("# Eating my homework\n\nWhy did the student eat his homework? Because the teacher said it was a piece of cake.", "Fun"),
        ("something -> found it during school and thought the website was funny.", "Fun"),
        ("🎉1😀 😀0🎉!", "Fun"),
        ("Homework: I ate my homework to something funny, a joke at school.", "Diary"),
    ]:
        manager.create_entry(session, content, category_name=category)
    session.commit()
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("said", ["hey! what can you do??", "alright, what can you do", "what can you do"])
def test_a_what_can_you_do_lists_it_and_atlas_speaks_as_atlas(go, said):
    text, _ = go(said)
    assert "Atlas's assistant" not in text and "Atlas" in text, text
    assert "**Ask:**" in text and "reminder" in text.lower(), text


def test_the_subject_is_the_thing_asked_about(go):
    text, _ = go(HOMEWORK)
    first = text.split("\n\n")[0]
    assert "eating your homework" in first, text
    for noise in ("smth", "something, it was a joke", "uhh", "I think", "my homework"):
        assert noise not in first, first
    # L102 (1d5df7da0) added a "Your Fun notes go together: ..." line that names the
    # scarecrow note by title near the top, so order is read on the quoted lines, which
    # is what the owner meant: the asked-about note is said before the unrelated one.
    asked, other = text.find("You wrote “Why did the student eat his homework"), text.find("You wrote “Why did the scarecrow")
    assert asked >= 0 and (other < 0 or asked < other), text


def test_no_tofu_arrow_or_inline_bold_in_the_answer(go):
    text, _ = go(HOMEWORK)
    assert "🎉" not in text and "->" not in text and "**Joke:**" not in text, text


@pytest.mark.parametrize("line", ["You wrote “🎉1😀 😀0🎉!”.", "You wrote “□□ □□”."])
def test_a_quote_of_mostly_symbols_is_not_said(line):
    assert composer_clean.line(line) == ""


@pytest.mark.parametrize("line", ["The picture in your Leafeon note is described as “A vibrant.", "It is described as “A vibrant.”", "You wrote “Walk to the shop and then"])
def test_a_cut_or_unclosed_quote_is_not_said(line):
    assert composer_clean.line(line) == ""


def test_a_whole_quote_stays():
    assert composer_clean.line("You wrote “Walk to the shop.”") == "You wrote “Walk to the shop.”"


def test_an_arrow_and_inline_bold_are_plain_words():
    assert composer_clean.line("You wrote that something -> found it at school.") == "You wrote that something: found it at school."
    assert composer_clean.line("Back in September, **Joke:** Why did it win?") == "Back in September, Joke: Why did it win?"


def test_headings_and_citations_keep_their_bold():
    for kept in ("**Tom**\n- Met in June. [**Tom**]", "Two notes. [**Lisbon trip**]", "- **Bold** item"):
        assert composer_clean.line(kept) == kept


@pytest.mark.parametrize("said, fixed", [
    ("You said that What your notes leave out is how.", "You said that what your notes leave out is how."),
    ("You wrote that The boiler is due.", "You wrote that the boiler is due."),
    ("You noted that Tom is away.", "You noted that Tom is away."),
    ("You said that I am late.", "You said that I am late."),
])
def test_reported_speech_lowers_its_first_word(said, fixed):
    assert composer_clean.line(said) == fixed


def test_a_loosely_related_heading_needs_something_after_it():
    heading = "More loosely related to eating your homework."
    assert composer_clean.paragraphs(["A.", heading]) == ["A."]
    assert composer_clean.paragraphs([heading, heading, "B."]) == [heading, "B."]
    assert composer_clean.paragraphs(["A.", heading, "B."]) == ["A.", heading, "B."]
