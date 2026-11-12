"""Readers and comparisons of the chat plan (ledger 1112): L105, L-chat-6, L209. No model, fixed day."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import composer, composer_extra, composer_study

TODAY = dt.date(2026, 11, 10)


def _note(i: int, content: str, day: str) -> dict:
    return {"id": i, "content": content, "category": "Work", "tags": [], "created_at": f"{day}T10:00:00Z"}


NOTES = [
    _note(1, "Release alpha\nShip on 3 December 2026.", "2026-10-01"),
    _note(2, "Release beta\nShip on 20 December 2026.", "2026-10-05"),
    _note(3, "Release gamma\nShip on 11 January 2027.", "2026-10-09"),
    _note(6, "Shopping\n- [ ] milk\n- [ ] eggs", "2026-09-01"),
    _note(7, "Todo\n- [ ] call dentist", "2026-10-02"),
]


def lead(question: str) -> str:
    return composer.compose(question, NOTES, today=TODAY)["text"].split("\n")[0]


@pytest.mark.parametrize("question", [
    "which of alpha, beta and gamma is the newest", "which of alpha, beta or gamma is newest",
    "which of the Release alpha, beta and gamma notes is the newest",
])
def test_l105_which_of_three_names_is_the_newest(question):
    text = lead(question)
    assert text.startswith("**Release gamma** is the newest:"), text
    assert "5 October" in text and "1 October" in text, text


def test_l105_the_oldest_of_three_and_the_first_of_three_trips():
    assert lead("which of alpha, beta or gamma is the oldest").startswith("**Release alpha** is the oldest:")
    assert lead("which of alpha, beta and gamma comes first").startswith("**Release alpha** comes first:")


def test_l105_two_names_after_of_still_compare():
    assert lead("which of Release alpha or Release beta is newer").startswith("**Release beta** is newer:")


def test_l105_a_question_with_no_names_is_not_a_comparison():
    assert not lead("which of my notes is the newest").startswith("**")


@pytest.mark.parametrize("question", ["which is oldest, Shopping or Todo", "which is the oldest, Shopping or Todo"])
def test_l_chat_6_two_list_notes_are_compared_by_their_days(question):
    text = lead(question)
    assert text.startswith("**Shopping** is the oldest: 1 September against 2 October for **Todo**"), text


def test_l209_who_is_older_reads_a_birth_year_and_an_age():
    notes = [_note(4, "Anna\nAnna was born in 1990. Gift: scarf.", "2026-10-01"), _note(5, "Tom\nTom is 41. Gift: book", "2026-10-02")]
    ctx = composer_study.Ctx(question="who is older, Anna or Tom", notes=notes, now=dt.datetime(2026, 11, 10, 10), seed="s", asked="who is older, Anna or Tom")
    assert composer_extra.answer(ctx).text == "Tom is older: 41 against born 1990 for Anna."


# --- the route: the seeded notebook (a Todo note, dentist, passport, Atlas) --------

import tests._seed_1031c as seed_c  # noqa: E402


@pytest.fixture
def go(client, session, monkeypatch):
    from datetime import datetime

    from tessellate.entry import manager

    seed_c.seed(session)
    entry = manager.create_entry(session, "# Shopping\n\n- [ ] milk\n- [ ] eggs", category_name="Home", tags=[])
    entry.created_at = entry.updated_at = datetime.fromisoformat("2026-09-01T10:00:00")
    session.commit()
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("question", ["which is oldest, Shopping or Todo", "which is the oldest, Shopping or Todo"])
def test_l_chat_6_shopping_or_todo_is_a_date_comparison_not_the_checklist(go, question):
    text = go(question)[0]
    assert text.startswith("**Shopping** is the oldest: 1 September against 26 October for **Todo**"), text


@pytest.mark.parametrize("question", [
    "which is the oldest, the dentist, the passport renewal or the atlas beta",
    "which of the dentist, the passport renewal and the atlas beta is the oldest",
])
def test_l_chat_5_three_notes_with_little_in_common_are_all_compared(go, question):
    text = go(question)[0]
    assert text.startswith("**Passport** is the oldest: 12 October against 15 October for **Project Atlas** and 18 October for **Dentist**"), text
    assert "nothing mentions" not in text, text
