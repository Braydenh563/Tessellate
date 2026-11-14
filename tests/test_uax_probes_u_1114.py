"""CHAT_PLAN Understanding rows U1 to U15 (LEDGER L-chat-65 to 77): one probe each, the plan line's own
phrasing asked of the audit-1031 notebook (clock fixed at Saturday 31 October 2026, 11:30) with no model.
A probe that stays a gap names it in the LEDGER row, not here."""

from __future__ import annotations

from datetime import date

import pytest

from tests import _seed_1031c as seed
from tests.test_composer_688 import TODAY as TODAY688, _note

TODAY = date(2026, 10, 10)


@pytest.fixture
def ask(client, session, monkeypatch):
    seed.seed(session)
    go = seed.asker(client, monkeypatch)

    def turn(question: str, history: list | None = None) -> str:
        return go(question, history=history)[0]

    return turn


def _talk(ask, *questions: str) -> str:
    history: list[dict] = []
    said = ""
    for q in questions:
        said = ask(q, history)
        history.append({"question": q, "answer": said})
    return said


# --- U1: names typed wrong join the vocabulary -----------------------------------------------------

@pytest.mark.parametrize(("typed", "meant"), [("Pryia", "priya"), ("Preya", "priya"), ("Lisbn", "lisbon")])
def test_u1_a_name_typed_wrong_is_read_as_the_notebooks_name(ask, typed, meant):
    said = ask(f"what do I know about {typed}").lower()
    assert meant in said and "none of your notes" not in said, said


def test_u1_a_word_a_note_holds_is_never_rewritten():
    from tessellate.ai import question_noise

    assert "lisbn" in question_noise.repair("what about lisbn", known=frozenset({"lisbn"}))


# --- U3: verb and noun say one thing ----------------------------------------------------------------

def test_u3_a_verb_finds_its_noun():
    from tessellate.ai import composer, composer_ask, composer_tables

    assert ("travel", "trip") in [p[:2] for p in composer_tables.EXTRA_SYNONYM_GROUPS] or composer._stem("trip") in composer_ask._alternatives(composer._stem("travel"))
    assert composer._stem("decision") in composer_ask._alternatives(composer._stem("decide"))


# --- U4: a fragment leans on the turn before ------------------------------------------------------

def test_u4_a_window_alone_asks_the_last_question_again(ask):
    said = _talk(ask, "what did I write about running", "and last week?")
    assert "last week" in said.lower() and "run" in said.lower(), said


def test_u4_a_new_subject_alone_replaces_the_subject(ask):
    said = _talk(ask, "what did I write about running", "and Sara?")
    assert "sister" in said.lower() and "squat" not in said.lower(), said


# --- U5: Monday and Tuesday are one window -------------------------------------------------------

def test_u5_two_days_are_one_question_two_questions_are_two():
    from tessellate.ai import composer

    assert composer.split_parts("what did I do on Monday and Tuesday") == ["what did I do on Monday and Tuesday"]
    assert composer.split_parts("what did I write in March and in April") == ["what did I write in March and in April"]
    assert composer.split_parts("what did I do on Monday and what did I eat on Tuesday") == ["what did I do on Monday", "what did I eat on Tuesday"]


# --- U6: two notes that tie ask which one -------------------------------------------------------

def test_u6_two_close_notes_on_different_topics_ask_which():
    from tessellate.ai import composer

    notes = [_note(1, "# Boiler service\n\nThe boiler service is due in March.", 5), _note(2, "# Boiler pressure\n\nThe boiler pressure was low this morning.", 3)]
    text = composer.compose("What about the boiler?", notes, today=TODAY688)["text"].rstrip()
    assert text.endswith(("Did you mean **Boiler service** or **Boiler pressure**?", "Did you mean **Boiler pressure** or **Boiler service**?")), text
    assert composer.CLARIFY_RATIO == 0.85  # the plan's 15 percent


# --- U9: sixty phrasings of a time, read as the past ------------------------------------------------

#: (phrase, first day, last day) on Saturday 10 October 2026; the one reader every past window goes through.
WINDOWS = [
    ("yesterday", "2026-10-09", "2026-10-09"), ("last friday", "2026-10-09", "2026-10-09"), ("three weeks ago", "2026-09-19", "2026-09-19"),
    ("last week", "2026-09-28", "2026-10-04"), ("last month", "2026-09-01", "2026-09-30"), ("2 days ago", "2026-10-08", "2026-10-08"),
    ("since March", "2026-03-01", "2026-10-10"), ("between 3 March and 9 March", "2026-03-03", "2026-03-09"),
    ("the past 3 days", "2026-10-07", "2026-10-10"), ("in October", "2026-10-01", "2026-10-31"), ("in 2025", "2025-01-01", "2025-12-31"),
    ("on Tuesday last week", "2026-09-29", "2026-09-29"), ("Friday of last week", "2026-10-02", "2026-10-02"),
    ("on the Monday of last week", "2026-09-28", "2026-09-28"), ("last night", "2026-10-09", "2026-10-09"),
    ("recently", "2026-09-26", "2026-10-10"), ("the week before last", "2026-09-21", "2026-09-27"), ("on 3 March", "2026-03-03", "2026-03-03"),
    ("today", "2026-10-10", "2026-10-10"), ("this week", "2026-10-05", "2026-10-11"), ("this month", "2026-10-01", "2026-10-31"),
    ("last year", "2025-01-01", "2025-12-31"), ("over the past two weeks", "2026-09-26", "2026-10-10"), ("in the last 10 days", "2026-09-30", "2026-10-10"),
    ("on Monday", "2026-10-05", "2026-10-05"), ("last weekend", "2026-10-03", "2026-10-04"), ("this morning", "2026-10-10", "2026-10-10"),
    ("last Tuesday", "2026-10-06", "2026-10-06"), ("a week ago", "2026-10-03", "2026-10-03"), ("a month ago", "2026-09-10", "2026-09-10"),
    ("since last week", "2026-09-28", "2026-10-10"), ("since yesterday", "2026-10-09", "2026-10-10"), ("in September", "2026-09-01", "2026-09-30"),
    ("in September 2025", "2025-09-01", "2025-09-30"), ("two months ago", "2026-08-10", "2026-08-10"), ("the day before yesterday", "2026-10-08", "2026-10-08"),
    ("from March to May", "2026-03-01", "2026-05-31"), ("during the last three months", "2026-07-10", "2026-10-10"), ("on 3 March 2026", "2026-03-03", "2026-03-03"),
    ("on March 3", "2026-03-03", "2026-03-03"), ("in the past week", "2026-10-03", "2026-10-10"), ("in the past month", "2026-09-10", "2026-10-10"),
    ("over the weekend", "2026-10-10", "2026-10-11"), ("the previous week", "2026-09-28", "2026-10-04"), ("last christmas", "2025-12-25", "2025-12-25"),
    ("in spring", "2026-03-01", "2026-05-31"), ("in March 2026", "2026-03-01", "2026-03-31"), ("2 weeks ago", "2026-09-26", "2026-09-26"),
    ("last Monday", "2026-10-05", "2026-10-05"), ("the last 7 days", "2026-10-03", "2026-10-10"), ("this year", "2026-01-01", "2026-12-31"),
    ("earlier this week", "2026-10-05", "2026-10-10"), ("at the end of September", "2026-09-30", "2026-09-30"), ("on the 3rd", None, None),
    ("a few days ago", "2026-10-07", "2026-10-07"), ("the other day", "2026-10-06", "2026-10-08"), ("before March", "1970-01-01", "2026-02-28"),
    ("last week on Tuesday", "2026-09-28", "2026-10-04"), ("the Tuesday of the previous week", None, None), ("this afternoon", None, None),
    ("last Sunday", "2026-10-04", "2026-10-04"),
]


def test_u9_sixty_phrasings_are_read_as_the_past():
    from tessellate.ai import composer_notes

    assert len(WINDOWS) >= 60
    wrong = []
    for phrase, first, last in WINDOWS:
        if first is None:
            continue
        got = composer_notes._window(f"what did I write {phrase}", TODAY)
        read = (got[0].isoformat(), got[1].isoformat()) if got else None
        if read != (first, last):
            wrong.append((phrase, read, (first, last)))
    assert not wrong, wrong


# --- U10: a negated constraint ------------------------------------------------------------------

def test_u10_notes_not_tagged_x_are_read_on_the_tags(ask):
    said = ask("notes not tagged work")
    assert "not tagged work" in said and "Meeting with Priya" not in said and "Project Atlas" not in said, said


def test_u10_anything_except_x_leaves_x_out(ask):
    said = ask("anything except the gym")
    assert "not mention gym" in said and "Gym log" not in said, said


def test_u10_the_query_language_negates_a_term():
    from tessellate.entry import query

    assert any(t.negate for t in query.parse("-tag:work gym"))


# --- U12: sums over one unit, listed with their sources -------------------------------------------

def test_u12_a_sum_is_over_one_unit_with_its_sources(client, session, monkeypatch):
    import tests._seed_composer_1110 as sd
    from tests import _seed_1031c as c

    sd.seed(session)
    said = c.asker(client, monkeypatch, chat=True)("total cost of the dentist and car service")[0]
    assert "$600" in said and "$180" in said and "$420" in said, said


# --- U13: the third item, how many left ------------------------------------------------------------

def test_u13_the_nth_item_and_the_count_left_read_the_list_before(ask):
    said = _talk(ask, "what is on my packing list", "the third item")
    assert "Sunscreen" in said, said
    said = _talk(ask, "what is on my packing list", "the second one", "how many are left")
    assert "Four of five" in said and "Charger" in said, said


def test_u13_open_items_are_counted_across_notes(ask):
    said = ask("what is open")
    assert "Eight unticked checklist items" in said and "Todo" in said and "Lisbon packing list" in said, said


# --- U15: why and how ---------------------------------------------------------------------------

def test_u15_why_takes_the_because_sentence_and_how_keeps_the_order():
    from tessellate.ai import composer

    notes = [_note(1, "# Bread\n\n1. Mix the flour and water.\n2. Rest for an hour.\n3. Bake at 230C.", 3),
             _note(2, "# Why\n\nI stopped running because my knee hurt. The doctor said rest.", 2)]
    why = composer.compose("why did I stop running", notes, today=TODAY688)["text"]
    assert "because your knee hurt" in why, why
    how = composer.compose("how do I make the bread", notes, today=TODAY688)["text"]
    assert how.index("Mix the flour") < how.index("Rest for an hour") < how.index("Bake at 230C"), how
