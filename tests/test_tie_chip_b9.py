"""One clarifying chip, only on a tie (CHAT_PLAN B9).

"python" in two categories that share no word past it is two readings; the
newer is answered, the other named, with one chip to ask about it. A
subject spread unevenly, or sharing words across its categories, is one
subject and gets no chip.
"""

from datetime import date

from tessellate.ai import composer_digest as digest

TODAY = date(2026, 10, 11)


def _notes(rows):
    return [
        {"id": i + 1, "content": c, "created_at": f"2026-09-{i + 1:02d}T10:00:00", "category": cat, "tags": []}
        for i, (c, cat) in enumerate(rows)
    ]


TIE = _notes([
    ("Python: list comprehensions are neat.", "Coding"),
    ("Python decorators wrap a function.", "Coding"),
    ("Fed the python two mice on Sunday.", "Pets"),
    ("The python shed its skin.", "Pets"),
])


def _tie_chips(reply: dict) -> list[str]:
    """The chips that offer the other reading. Since INBOX 1466 an answer also
    carries its shape's own follow-ups ("What's the latest on X?"), which are
    not what these tests are about."""
    return [chip for chip in reply["next"] if chip.startswith("What have I saved about")]


def test_a_tie_answers_the_newer_reading_and_offers_one_chip():
    r = digest.answer("what have I saved about python?", TIE, today=TODAY)
    assert "shed its skin" in r["text"] and "decorators" not in r["text"]
    assert "Python also comes up in Coding: two notes on something else." in r["text"]
    assert _tie_chips(r) == ["What have I saved about python in Coding?"]


def test_the_chip_asks_the_other_reading_and_gets_it():
    r = digest.answer("What have I saved about python in Coding?", TIE, today=TODAY)
    assert "decorators" in r["text"] and "skin" not in r["text"]
    assert _tie_chips(r) == []


def test_no_chip_when_the_split_is_uneven():
    notes = _notes([
        ("Python: list comprehensions are neat.", "Coding"),
        ("Python decorators wrap a function.", "Coding"),
        ("Python generators yield lazily.", "Coding"),
        ("The python shed its skin.", "Pets"),
    ])
    assert _tie_chips(digest.answer("what have I saved about python?", notes, today=TODAY)) == []


def test_no_chip_when_the_categories_share_words():
    notes = _notes([
        ("Running plan: easy five kilometres on Monday.", "Fitness"),
        ("Running loop round the park on Thursday.", "Fitness"),
        ("Signed up for the charity race running in May.", "Events"),
        ("Charity running race starts at the park gates.", "Events"),
    ])
    assert _tie_chips(digest.answer("what have I saved about running?", notes, today=TODAY)) == []


def test_one_note_on_each_side_is_not_a_tie():
    notes = _notes([
        ("Jokes for the group chat: the Kit Kat one.", "Humour"),
        ("Homework: write three jokes for the drama class.", "Courses & Study"),
    ])
    r = digest.answer("what have I saved about jokes?", notes, today=TODAY)
    assert _tie_chips(r) == [] and "comes up in" not in r["text"]
