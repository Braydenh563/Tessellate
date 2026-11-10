"""W10 (2026-11-10): composer compare, summary and lists, rows B30 to B36. One test per row, probed first and fixed
as a class. Clock fixed: the r9 and bt seeds are Monday 9 November 2026, the r5 seed Saturday 7 November."""

from __future__ import annotations

import pytest

import tests._seed_bt_1109 as bt
import tests._seed_r9_1109 as r9
from tessellate.ai import composer_frame, study
from tessellate.entry import manager
from tests._r5_1108 import driver


@pytest.fixture
def r9ask(client, session, monkeypatch):
    r9.seed(session)
    r9.fix_clock(monkeypatch)
    return lambda q: r9.ask(client, q, notes_only=True)["text"]


@pytest.fixture
def btask(client, session, monkeypatch):
    bt.seed(session)
    bt.fix_clock(monkeypatch)
    return lambda q: bt.ask(client, q, notes_only=True)["text"]


@pytest.fixture
def r5(client, session, monkeypatch):
    go = driver(client, session, monkeypatch)
    return lambda q: go(q)["text"]


# --- B30 summary keeps the dated sentence; a recipe keeps its method; the composer's own lead is a comparison ------

@pytest.mark.parametrize("question", ["summarise my kitchen renovation", "summarize the kitchen renovation note", "boil down the kitchen renovation note"])
def test_a_summary_keeps_the_start_date_over_a_phone_number(r9ask, question):
    text = r9ask(question)
    assert "Work starts 16 November" in text and "07700" not in text, text


def test_a_month_inside_a_name_is_not_a_date():
    # "Marek" begins "mar", "Decker" begins "dec": a name is no reason to prefer its sentence.
    assert study._WHEN.search("Marek said Decker called") is None
    assert study._WHEN.search("Work starts 16 November.")
    assert study._WHEN.search("due 5 Dec")


def test_a_date_outranks_a_phone_number_and_a_phone_is_last():
    rest = ["Builder is Marek, phone 07700 900456.", "Work starts 16 November.", "Worktops will be oak."]
    assert study._worth(rest, 1) == ["Work starts 16 November."]
    assert study._worth(["Phone 07700 900123.", "Likes tea."], 1) == ["Phone 07700 900123."]


def test_a_recipe_summary_has_the_method_not_only_the_ingredients(btask):
    text = btask("summarise the recipe")
    assert "300g arborio rice" in text and "Toast the rice" in text, text


def test_a_team_sync_summary_keeps_its_agenda(btask):
    text = btask("summarise the team sync")
    assert "Tuesday 10 November" in text and "hiring a designer" in text, text


@pytest.mark.parametrize("question", [
    "Among these notes, one mentions Priya and one mentions Marcus.",
    "Of the notes found, one mentions Priya and two mention Marcus",
])
def test_the_composers_own_compare_lead_said_back_is_a_comparison(btask, question):
    text = btask(question)
    assert "**Priya**" in text and "**Marcus**" in text and "do not mention" not in text, text


def test_a_compare_lead_said_back_names_both_sides_on_the_r5_seed(r5):
    text = r5("Among the notes found, one mentions the Lisbon trip and one mentions the Project Atlas.")
    assert "**Lisbon trip**" in text and "**Project Atlas**" in text and "“found”" not in text, text


# --- B31 dead ends where the notebook can answer --------------------------------------------------------------

@pytest.mark.parametrize("question", ["show my done items", "show me my completed tasks"])
def test_done_items_are_the_ticked_ones(r9ask, question):
    text = r9ask(question)
    assert "Pay council tax" in text and "Coffee beans" in text, text


@pytest.mark.parametrize("question", ["what are my favourites", "show my favourite notes"])
def test_favourites_are_the_pinned_notes(r9ask, question):
    assert "pinned" in r9ask(question)


def test_a_persons_favourite_colour_is_not_the_pinned_list(r9ask):
    assert "pinned" not in r9ask("what is Sara's favourite colour")


@pytest.mark.parametrize("question", ["which notes are linked", "which notes have links"])
def test_linked_notes_are_answered_from_the_links(client, session, monkeypatch, question):
    r9.seed(session)
    r9.fix_clock(monkeypatch)
    manager.create_entry(session, "# Trip plan\n\nSee [[Japan]] and [[Portugal]] for ideas.", category_name="Uncategorised")
    session.commit()
    text = r9.ask(client, question, notes_only=True)["text"]
    assert "Trip plan" in text and "2 links" in text, text


def test_no_linked_notes_says_none(r9ask):
    assert "None of your notes have links to other notes." in r9ask("which notes are linked")


# --- B32 a list row does not end with the default filing -------------------------------------------------------

@pytest.mark.parametrize("question", ["which notes mention the boiler", "what is my oldest note"])
def test_a_list_row_does_not_end_uncategorised(r9ask, question):
    assert "Uncategorised" not in r9ask(question)


# --- B36 an imperative one-liner is named plain, as every other title --------------------------------------------

def test_an_imperative_one_line_note_is_named_plain(r9ask):
    text = r9ask("what do I know about the plumber")
    assert "The other is Call plumber." in text and "“Call plumber”" not in text, text


def test_a_lower_case_or_long_order_is_still_quoted():
    assert composer_frame.name_of({"content": "call mum about christmas plans"}).startswith("“")
    assert composer_frame.name_of({"content": "Call plumber"}) == "Call plumber"
    assert composer_frame.name_of({"content": "Call the plumber about the leak today"}).startswith("“")
