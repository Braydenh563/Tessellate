"""Composer round 2, 2026-11-07 (audit-1107-composer-r2.md): table rows, negation,
pronoun follow-ons, undo, ordinals, accents. Every question runs through
`composer.compose` over `_seed_r2_1107`; no model (fake transport), fixed clock."""

from __future__ import annotations

import pytest

from tests._seed_r2_1107 import ask, chain


@pytest.mark.parametrize("question", ["how much is bread", "how much is the bread"])
def test_e1_a_table_row_answers_the_price_it_holds(question):
    said = ask(question)
    assert "2.50" in said and "only a title" not in said, said


def test_e1_a_note_with_a_table_is_never_called_only_a_title():
    for question in ("shopping", "what is in the Shopping note", "milk"):
        assert "only a title" not in ask(question, only=("Shopping",)), question



TRIPS = ("Tokyo trip", "Packing for Tokyo", "Lisbon trip", "Lisbon packing list", "Lisbon dinner", "coriander")


@pytest.mark.parametrize("question", ["notes about Tokyo but not Lisbon", "what do I know about Tokyo, not Lisbon", "notes about Tokyo without Lisbon"])
def test_e2_but_not_keeps_the_first_subject_and_drops_the_second(question):
    said = ask(question, only=TRIPS)
    assert "Tokyo trip" in said and "Packing for Tokyo" in said, said
    assert "Lisbon" not in said.replace("not Lisbon", "").replace("without Lisbon", ""), said
    assert "“not”" not in said, said


@pytest.mark.parametrize("question", ["nothing about Lisbon", "which notes are not about Lisbon", "what notes do I have that don't mention Lisbon"])
def test_e2_a_negative_ask_names_the_notes_that_leave_the_word_out(question):
    said = ask(question, only=TRIPS)
    assert "Tokyo trip" in said and "coriander" in said, said
    assert "Lisbon trip" not in said and "“nothing”" not in said and "“not”" not in said, said



def test_e20_a_note_without_the_property_says_it_has_none():
    assert ask("what is the password for the bank") == "Your Bank note has no password."
    assert ask("what is the address for the bank") == "Your Bank note has no address."


def test_e4_number_asks_for_the_phone_and_leads_with_it():
    assert ask("what is the landlord's number").startswith("Phone 020 7946 0999")
    assert ask("what is the dentist's phone number").startswith("Phone 020 7946 0011")


def test_e4_a_pronoun_follow_on_keeps_the_subject_and_never_wanders():
    said = chain(["what do I know about José", "what is his number", "and his address"], ("José García", "Jokes", "Dentist"))
    assert said[1].startswith("Phone 020 7946 0999"), said[1]
    assert said[2] == "Your José García note has no address.", said[2]


# --- E21: a state asked with no list named, and the shortest note --------------------------

CHECKLISTS = ("Todo", "Lisbon packing list")


@pytest.mark.parametrize("question", ["what is not done", "what haven't I finished", "what is left to do", "what is unticked", "which tasks are open"])
def test_e21_the_open_items_of_every_checklist_when_no_list_is_named(question):
    got = ask(question, only=CHECKLISTS)
    assert got.startswith("Six items still open across two notes:"), got
    assert "Book MOT, in Todo" in got and "Charger, in Lisbon packing list" in got
    assert "Pay council tax" not in got and "Nothing comes up" not in got and "don't mention" not in got


@pytest.mark.parametrize("question", ["what did I tick", "what have I ticked off"])
def test_e21_what_was_ticked_lists_the_ticked_items(question):
    got = ask(question, only=CHECKLISTS)
    assert got.startswith("You have ticked off two items across two notes:"), got
    assert "Passport, in Lisbon packing list" in got


def test_e21_unpacked_still_names_the_packing_list_only():
    got = ask("what's unpacked", only=CHECKLISTS)
    assert got.startswith("3 still to do on Lisbon packing list:") and "Book MOT" not in got, got


def test_e21_the_shortest_note_is_named_with_its_words(client):
    from tessellate.ai import notebook_stats
    from tessellate.core import deps
    from tessellate.core.database import Entry

    with deps.get_db().session() as session:
        for text in ("# Lisbon trip\n\nFlights cost four hundred pounds return in May.", "# Hi\n\nhi", "# Long\n\n" + "word " * 30):
            session.add(Entry(content=text, tags="[]"))
        session.commit()
        answer = notebook_stats.answer("what is my shortest note", session)
    assert answer is not None and answer.text.startswith("Your shortest note is “Hi”"), answer
    assert [f["label"] for f in answer.facts][:2] == ["Hi", "Lisbon trip"]


# --- E26: another language's function words are never a missing topic ---------------------


@pytest.mark.parametrize("question", ["what do I know sobre Tokyo", "qué sé sobre Tokyo", "was ist mein Tokyo trip"])
def test_e26_a_foreign_function_word_is_not_reported_missing(question):
    got = ask(question)
    assert "Tokyo trip" in got, got
    for word in ("sobre", "“mein”", "“que”"):
        assert f"mention {word}" not in got and f"omit {word}" not in got, got
    assert "None of these notes mention" not in got, got


# --- E7: a typed undo leads with the keys, not with "not something in your notes" ----------


@pytest.mark.parametrize("question", ["undo", "undo that", "undo the last change"])
def test_e7_a_typed_undo_says_how_to_undo_first(question):
    got = ask(question)
    assert got.startswith("Press Undo in the status bar, or Ctrl+Z"), got
    assert "toast" not in got and "not something in your notes" not in got


def test_e7_a_typed_redo_says_the_redo_keys_first():
    assert ask("redo").startswith("Press Redo in the status bar, or Ctrl+Shift+Z"), ask("redo")


# --- E8: the nth item of a list, and how many items it holds ------------------------------


@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("what is the third item in the Tokyo packing list", "The third item is Adapter."),
        ("what is the second item on the Tokyo packing list", "The second item is Rail pass."),
        ("what is the last item in my todo", "The last item is Buy stamps (not done)."),
        ("what is the third item in the Lisbon packing list", "The third item is Sunscreen (not done)."),
        ("how many items are in Packing for Tokyo", "Packing for Tokyo has four items."),
        ("how many items are in my todo", "Todo has four items, one of them done."),
        ("what is the ninth item in my todo", "Todo has only four items."),
    ],
)
def test_e8_a_position_or_a_count_is_said_exactly(question, said):
    got = ask(question)
    assert got == said, got


# --- E11: a one-word note is one note, however it is asked for ----------------------------


@pytest.mark.parametrize(
    ("question", "word"),
    [("what is the milk note", "milk"), ("what's in milk", "milk"), ("what do I know about hi", "hi"), ("what is the Hi note", "hi")],
)
def test_e11_a_one_word_note_answers_as_itself(question, word):
    from tests._seed_r2_1107 import _route_answer, notes

    result = _route_answer(question, notes)
    #: Intent unchanged (the note answers as itself, cited); only the wording moved: the word was said twice (L204).
    assert result["text"] == f"Your note “{word}” is just that one word.", result["text"]
    assert result["grounding"], "cited to the note"


def test_e11_what_is_a_word_without_the_note_word_still_reads_the_other_notes():
    assert ask("what is milk").startswith("Milk £1.20"), ask("what is milk")


# --- E9: "costs more" ranks the figures whichever way round it is asked --------------------


@pytest.mark.parametrize("question", ["Lisbon or Tokyo, which costs more", "which costs more, Lisbon or Tokyo", "which is more expensive, Lisbon or Tokyo"])
def test_e9_costs_more_names_the_dearer_trip_with_both_figures(question):
    got = ask(question)
    assert got.startswith("**Tokyo trip** costs more: $900 against $420 for **Lisbon trip**."), got


def test_e9_costs_less_names_the_cheaper_trip():
    assert ask("which costs less, Lisbon or Tokyo").startswith("**Lisbon trip** is cheaper: $420 against $900 for **Tokyo trip**."), ask("which costs less, Lisbon or Tokyo")


# --- E5: "it" still means the note the chain began with after a bare-verb turn ------------


def test_e5_it_keeps_the_named_trip_after_a_turn_about_packing():
    said = chain(["tell me about the Tokyo trip", "where is it", "what should I pack", "when does it start"], None)
    assert "Tokyo trip" in said[3] and "Packing for Tokyo" not in said[3], said[3]
    assert "Lisbon" not in said[3]


# --- Research row 11: a note's emphasis marks never show in a quote ------------------------


def test_row11_a_summary_quotes_without_emphasis_marks():
    from datetime import date

    from tessellate.ai import composer_digest

    note = {"id": 1, "content": "# Social\n\n**Dinner** with Priya on Friday. *Bring wine* and `cash`.", "category": "U", "tags": [], "created_at": "2026-11-01T10:00:00Z"}
    other = {"id": 2, "content": "# Social club\n\nChess night is on Tuesday at the pub.", "category": "U", "tags": [], "created_at": "2026-11-03T10:00:00Z"}
    result = composer_digest.answer("summarise my social notes", [note, other], today=date(2026, 11, 7))
    assert "Bring wine and cash" in result["text"] and "*" not in result["text"] and "`" not in result["text"], result["text"]
    assert all("*" not in row["sentence"] for row in result["grounding"])



def test_e4_a_phone_or_cell_that_is_not_asked_for_is_not_a_number_ask():
    from tessellate.ai import composer_property as cp

    for q in ("when did I get my phone??", "explain cell respiration", "my phone screen cracked", "mobile games I liked"):
        assert cp.asked(q) == "", q
    for q in ("what is the landlord's number", "what is the dentist's phone number", "what's Sam's mobile?",
              "give me the plumber's phone", "what is his cell no."):
        assert cp.asked(q) == "phone", q
