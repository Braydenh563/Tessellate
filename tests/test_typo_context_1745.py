"""INBOX 1745: the typo repair reads a slip in context, for every writer, not for one.

The owner: "different spelling mistakes and ways of writing stuff may be interpreted differently or be intended to
be different words depending on the rest of the sentence and the topic", and "other people may write differently to
me so dont just base it off how I would say it". So the fixtures are many writers (US and UK spelling and date
order, second-language English, texting shorthand, no punctuation, all caps, dialect, voice-typed run-ons), each
with the reading the writer meant, and every rule is held against the whole set (`test_rule_*`), not one sentence.

What chooses between readings (`ai/typo_context.py`): (1) the rest of the sentence, (2) the notebook's own
vocabulary (titles, tags, people, list names) and the topic of its notes, (3) the previous turn's subject. When two
readings stay close the likelier is answered and the other is offered as a chip ("Did you mean ...?"). Dates are
fixed at Tuesday 10 November 2026; the order of "11/09" follows the app's locale setting (`recognise`).
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tessellate.ai import question_noise, recognise, typo_context

NOW = datetime(2026, 11, 10, 9, 0)

#: Notebooks: (title, content, tags) rows.
NOTEBOOKS = {
    "empty": [],
    "skills": [("Skills", "Python skill and guitar skill, levels per skill.", ["learning"]), ("Gym", "Leg day.", ["fitness"])],
    "skull": [("Skull mask", "The skull mask for halloween, papier mache skull.", ["halloween"]), ("Gym", "Leg day.", [])],
    "dairy": [("Dairy", "Milk, cheese, butter and yoghurt.", ["shopping"])],
    "diary": [("Diary", "Dear diary, today was a long day.", ["journal"])],
}


class Case:
    def __init__(self, writer: str, typed: str, meant: str, *, nb: str = "empty", before: str = "", offer: str | None = None) -> None:
        self.writer, self.typed, self.meant, self.nb, self.before, self.offer = writer, typed, meant, nb, before, offer

    def __repr__(self) -> str:
        return f"{self.writer}:{self.typed}"


CASES = [
    # "form" is "from" beside a date, a name or a source, and stays a form beside "the" or "fill".
    Case("us", "show me notes form last week", "show me notes from last week"),
    Case("us", "what did I write form Anna yesterday", "what did I write from Anna yesterday"),
    Case("uk", "show me the messages form 2025", "show me the messages from 2025"),
    Case("uk", "where did i write down the recipe form mum", "where did i write down the recipe from mum"),
    Case("us", "fill in the form", "fill in the form"),
    Case("uk", "where is the tax form", "where is the tax form"),
    Case("us", "i hate this form", "i hate this form"),
    # A note's own word is not a typo: "skull" is this notebook's topic, "skill" another notebook's.
    Case("us", "show me my skull", "show me my skull", nb="skull"),
    Case("us", "what did i write about the skull", "what did i write about the skull", nb="skull"),
    Case("uk", "what do i know about my skull", "what do i know about my skull", nb="skull"),
    Case("us", "show me my skull levels", "show me my skill levels", nb="skills"),
    Case("uk", "what skull did i add", "what skill did i add", nb="skills"),
    Case("us", "which skull should i learn", "which skill should i learn", nb="skills"),
    # The last turn's subject breaks a tie, and the other reading is offered.
    Case("us", "show me my skull", "show me my skill", before="You have 3 notes about skills you are learning.", offer="skull"),
    # Real words that a slip lands on: "not" and "note", "dairy" and "diary".
    Case("us", "add a not about the dentist", "add a note about the dentist"),
    Case("uk", "pls add not called gym", "please add note called gym"),
    Case("us", "i am not sure about the dentist", "i am not sure about the dentist"),
    Case("uk", "it is not on my list", "it is not on my list"),
    Case("us", "whats in my diary", "what is in my diary", nb="diary"),
    Case("us", "whats in my dairy", "what is in my dairy", nb="dairy"),
    Case("uk", "what did i buy from the dairy aisle", "what did i buy from the dairy aisle", nb="dairy"),
    Case("us", "show me my dairy entries", "show me my diary entries", nb="diary"),
    # then and than; lest, list and last.
    Case("us", "show me notes more then ten words", "show me notes more than ten words"),
    Case("uk", "what did i do and then what did i eat", "what did i do and then what did i eat"),
    Case("uk", "when was the lest time i went to the gym", "when was the last time i went to the gym"),
    Case("us", "what is on my lest for tomorrow", "what is on my list for tomorrow"),
    Case("uk", "show me my lest of films", "show me my list of films"),
    # US and UK spelling are both words: neither is a slip.
    Case("us", "what color is my favorite sweater", "what color is my favorite sweater"),
    Case("uk", "what colour is my favourite jumper", "what colour is my favourite jumper"),
    Case("us", "whats on my calender for the weekend", "what is on my calendar for the weekend"),
    # Second-language English.
    Case("esl", "i want to see the notes form yesterday please", "i want to see the notes from yesterday please"),
    Case("esl", "can you show me what i wrote about the gym", "can you show me what i wrote about the gym"),
    Case("esl", "how much skills i have", "how much skills i have"),
    Case("esl", "show me what my fiend jake said", "show me what my friend jake said"),
    # Texting shorthand.
    Case("sms", "pls remind me 2moro", "please remind me tomorrow"),
    Case("sms", "did u write abt the gym rn", "did you write about the gym right now"),
    Case("sms", "whats on my list tmrw", "what is on my list tomorrow"),
    Case("sms", "show me notes form yday", "show me notes from yesterday"),
    # No punctuation, all caps.
    Case("nopunct", "what did i write form anna on monday", "what did i write from anna on monday"),
    Case("caps", "SHOW ME NOTES FORM LAST WEEK", "show me notes from last week"),
    Case("caps", "WHAT IS ON MY LEST FOR TOMORROW", "what is on my list for tomorrow"),
    Case("caps", "FILL IN THE FORM", "fill in the form"),
    # Dialect: words that are not slips.
    Case("dialect", "i reckon its gonna rain am i keen to go", "i reckon its going to rain am i keen to go"),
    Case("dialect", "im keen to go to the gym can u remind me", "I am keen to go to the gym can you remind me"),
    Case("dialect", "whats on my lest this arvo", "what is on my list this afternoon"),
    # Voice-typed run-ons.
    Case("voice", "so um what did i write form anna yesterday and then what did i eat", "so um what did i write from anna yesterday and then what did i eat"),
    Case("voice", "add a not about the dentist and then show me my lest", "add a note about the dentist and then show me my list"),
]


def _context(nb: str, before: str) -> typo_context.Context:
    notes = [{"title": t, "content": c, "tags": tags} for t, c, tags in NOTEBOOKS[nb]]
    return typo_context.of_notes(notes, previous=before)


def read(typed: str, nb: str = "empty", before: str = "") -> tuple[str, list[dict]]:
    token = typo_context.CTX.set(_context(nb, before))
    try:
        chips: list[dict] = []
        return question_noise.repair(question_noise.tidy(typed), chips), chips
    finally:
        typo_context.CTX.reset(token)


@pytest.mark.parametrize("case", CASES, ids=repr)
def test_each_writer_is_read_as_meant(case):
    reading, chips = read(case.typed, case.nb, case.before)
    assert reading == case.meant
    if case.offer:
        assert [c["alternative"] for c in chips] == [case.offer]


# --- rules, each held against the whole set ---------------------------------------


def test_rule_a_reading_is_stable():
    """Reading a reading again changes nothing, for every writer."""
    for case in CASES:
        once, _ = read(case.typed, case.nb, case.before)
        assert read(once, case.nb, case.before)[0] == once, case


def test_rule_shouting_and_punctuation_do_not_change_the_reading():
    """The same words in capitals, or with a question mark, are read the same."""
    for case in CASES:
        if case.writer == "caps":
            continue
        base = read(case.typed, case.nb, case.before)[0].lower()
        assert read(case.typed.upper(), case.nb, case.before)[0].lower() == base, case
        assert read(case.typed + "?", case.nb, case.before)[0].lower().rstrip("?") == base, case


def test_rule_no_offer_when_the_sentence_is_sure():
    """A chip appears only for a reading that stays close; a sure one is answered without a "Did you mean"."""
    for case in (c for c in CASES if c.offer is None):
        assert read(case.typed, case.nb, case.before)[1] == [], case


def test_rule_the_notebooks_own_word_is_never_read_as_another_without_a_cue():
    """A word that is a title or tag here stays itself where the sentence has no cue for the other reading."""
    for word, other, nb in (("skull", "skill", "skull"), ("dairy", "diary", "dairy")):
        for frame in ("show me my {}", "what did i write about the {}", "how many {} notes"):
            assert other not in read(frame.format(word), nb)[0], (frame, nb)


def test_rule_the_notebook_decides_where_the_sentence_has_no_cue():
    """The same sentence is read one way in one notebook and another way in another."""
    assert read("show me my skull levels", "skills")[0].endswith("skill levels")
    assert read("show me my skull", "skull")[0].endswith("skull")
    assert read("show me my skull", "skills")[0].endswith("skill")


@pytest.mark.parametrize(("locale", "first"), [
    ("en-US", date(2026, 11, 9)), ("en-GB", date(2026, 9, 11)), ("en-AU", date(2026, 9, 11)), ("en-CA", date(2026, 11, 9)), (None, date(2026, 9, 11)),
])
@pytest.mark.parametrize("sentence", ["what did i write around 11/09 of this year", "what did i do near 11/09", "notes from the week of 11/09"])
def test_a_slash_date_follows_the_apps_locale_and_the_other_order_is_kept(locale, first, sentence):
    """11/09 is 9 November for a month-first locale and 11 September for the rest (`recognise`); the other order
    stays a reading, so it can be offered. It is never a rating without a rating word."""
    assert "out of" not in question_noise.tidy(sentence)
    found = recognise._numeric_dates(sentence, NOW.date(), locale, "past")[0][2]  # noqa: SLF001
    assert found[0][0] == first
    assert {d for d, _ in found} == {date(2026, 11, 9), date(2026, 9, 11)}


@pytest.mark.parametrize("sentence", [
    "i went and saw the minecraft movie and I reckon int was around a 9/10", "i rated the film 9/10", "the movie was a 9/10 mate",
    "gave it a 9/10 for sure", "it is a solid 9/10 tbh",
])
def test_a_rating_word_reads_a_fraction_as_a_rating_for_every_writer(sentence):
    assert "9 out of 10" in question_noise.tidy(sentence)
