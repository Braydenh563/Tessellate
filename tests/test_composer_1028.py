"""Composer audit 1028 (rows E6, E7, E11, E12, E30, E31), each tested over
several phrasings, including ones the fixes were not designed around (INBOX
1357: fix the class, not the case). Fixed clock: Wednesday 28 October 2026,
10:00. No model runs."""

from __future__ import annotations

import datetime as dt
import os
import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Entry
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 28, 10, 0, 0)

NOTES = [
    ("# Dentist\n\nDentist appointment on 3 November at 2pm. Bring the insurance card.", "Personal", dt.datetime(2026, 10, 20, 9)),
    ("# Gym log\n\nFriday deadlift 100kg for five reps. Squat 80kg on Monday.", "Health", dt.datetime(2026, 10, 10, 18)),
    ("# Calculus\n\nProblem set 6 is due 2 November. Revise integration by parts.", "Uni", dt.datetime(2026, 10, 15, 9)),
    ("# History essay\n\nThe essay is due 3 December. Sources to read:\n- [ ] Hobsbawm chapter 2\n- [ ] Evans chapter 4", "Uni", dt.datetime(2026, 10, 12, 9)),
    ("# Biology exam\n\nBiology exam on 12 November. Covers cells, mitosis and enzymes.", "Uni", dt.datetime(2026, 10, 18, 9)),
    ("# Biology notes\n\nA cell is the basic unit of life. Mitosis is the division of a cell into two identical cells. An enzyme is a protein that speeds up a reaction. Osmosis is the movement of water across a membrane.", "Uni", dt.datetime(2026, 10, 19, 9)),
    ("# Presentation\n\nGroup presentation on 20 November. Slides need finishing.", "Uni", dt.datetime(2026, 10, 21, 9)),
    ("# Pasta recipe\n\nFry garlic in oil, add tomatoes and simmer for twenty minutes.", "Food", dt.datetime(2026, 10, 25, 9)),
    ("# Study plan\n\nMonday biology, Tuesday calculus, Wednesday history. Two hours each evening.", "Uni", dt.datetime(2026, 10, 26, 9)),
]

_DUMP = os.environ.get("COMPOSER_1028_DUMP")


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, category, when in NOTES:
        entry = manager.create_entry(session, text, category)
        entry.created_at = entry.updated_at = when
    session.commit()

    def go(question: str) -> str:
        text = _ask(client, question, notes_only=True, answer_from="notes", history=[])["text"]
        if _DUMP:
            with open(_DUMP, "a", encoding="utf-8") as fh:
                fh.write(f"### {question}\n{text}\n\n")
        return text

    return go


def _titles(session) -> dict[str, Entry]:
    return {e.title: e for e in session.query(Entry).all()}


# E6: a day asked about is also a day a note says, and "when was X written" is the note's own date

WEEKDAY_LIFT = [
    "how much did I lift on friday",
    "what did I deadlift on friday",
    "how heavy was my deadlift on friday",
    "what weight did I do on friday",
    "friday lifts",
]


@pytest.mark.parametrize("question", WEEKDAY_LIFT)
def test_a_weekday_finds_the_note_that_says_it(ask, question):
    said = ask(question)
    assert "100kg" in said and "Gym log" in said, said
    assert "wrote nothing" not in said and "couldn't find" not in said


DATE_QS = [
    "what do I have on 3 November",
    "what's on 3rd of november",
    "anything on november 3",
    "what is happening on 3 Nov",
    "do I have anything on the 3rd of November",
]


@pytest.mark.parametrize("question", DATE_QS)
def test_a_date_finds_the_note_that_mentions_it(ask, question):
    said = ask(question)
    assert "Dentist" in said and "2pm" in said, said
    assert "nothing" not in said.lower()


def test_what_did_i_write_on_a_day_stays_about_creation(ask):
    said = ask("what did I write on friday")
    assert "nothing" in said.lower() and "Gym log" not in said


WRITTEN_WHEN = [
    ("when was my gym log written", "Saturday 10 October"),
    ("when did I write the dentist note", "Tuesday 20 October"),
    ("when did I make the pasta recipe", "Sunday 25 October"),
    ("what day was my biology exam note created", "Sunday 18 October"),
    ("what date did I start my calculus note", "Thursday 15 October"),
    ("when was the study plan written?", "Monday 26 October"),
]


@pytest.mark.parametrize(("question", "day"), WRITTEN_WHEN)
def test_when_was_a_note_written_says_its_date_not_a_quote(ask, question, day):
    said = ask(question)
    assert day in said, said
    assert "kg" not in said and "appointment" not in said.lower()


def test_when_did_i_last_write_about_is_not_a_note_day(ask):
    assert "was written on" not in ask("when did I last write about biology")


# E30: not installed is not "still loading"

def test_a_missing_search_engine_is_not_loading(app_state, monkeypatch):
    from tessellate.ai import embeddings

    monkeypatch.setattr(embeddings, "_package_present", lambda: False)
    monkeypatch.setattr(embeddings, "warmup_running", lambda: True)
    assert routes_chat._meaning_loading() is False


@pytest.mark.parametrize("question", ["what is my wifi password", "tell me about quantum chess", "who is my landlord"])
def test_a_miss_never_says_to_ask_again_for_an_engine_that_is_not_there(ask, question):
    said = ask(question)
    assert "ask again in a few seconds" not in said


# E7: a title alone names the note for the verbs only a note can take

from tessellate.ai import commands  # noqa: E402

_NOW = dt.datetime(2026, 10, 28, 10, 0, tzinfo=dt.timezone.utc)

BARE_READS = [
    # (phrasing, intent, about)
    ("tag my gym log with fitness", "tag", "gym log"),
    ("tag the history essay with uni", "tag", "history essay"),
    ("tag my pasta recipe as food", "tag", "pasta recipe"),
    ("add the tag fitness to the gym log", "tag", "gym log"),
    ("add tag fitness to my gym log", "tag", "gym log"),
    ("give the gym log the tag fitness", "tag", "gym log"),
    ("please tag the dentist appointment with health", "tag", "dentist appointment"),
    ("rename my gym log to Training log", "rename", "gym log"),
    ("rename the history essay as Essay draft", "rename", "history essay"),
    ("retitle my pasta recipe to Quick pasta", "rename", "pasta recipe"),
    ("change the title of my gym log to Training log", "rename", "gym log"),
    ("can you rename the study plan to Revision plan?", "rename", "study plan"),
    ("pin the history essay", "pin", "history essay"),
    ("pin my gym log to the top", "pin", "gym log"),
    ("star the dentist appointment", "pin", "dentist appointment"),
    ("favorite the study plan", "pin", "study plan"),
    ("unpin the history essay", "unpin", "history essay"),
    ("unstar my gym log", "unpin", "gym log"),
    ("delete the pasta recipe", "delete", "pasta recipe"),
    ("bin my gym log", "delete", "gym log"),
    ("please get rid of the study plan", "delete", "study plan"),
    ("erase the dentist appointment", "delete", "dentist appointment"),
    ("throw out my pasta recipe", "delete", "pasta recipe"),
    ("move my gym log to Fitness", "move", "gym log"),
]


@pytest.mark.parametrize(("text", "intent", "about"), BARE_READS)
def test_a_bare_title_names_the_note(text, intent, about):
    found = commands.read_typed(text, _NOW)
    assert found is not None, text
    assert found["intent"] == intent and found["about"].lower() == about, found


NOT_ACTS = [
    "delete all my data",
    "delete my account",
    "delete the chat history",
    "pin it",
    "delete the reminder for problem set 6",
    "delete the tag urgent",
    "rename the category Uni to Study",
    "delete 3 notes",
    "what does it mean to delete a note",
    "how do I delete the pasta recipe?",
    "did I pin the history essay",
    "bin day is on thursday",
]


@pytest.mark.parametrize("text", NOT_ACTS)
def test_what_is_not_a_note_is_not_read_as_an_act_on_one(text):
    found = commands.read_typed(text, _NOW)
    assert found is None or not found.get("bare"), found


@pytest.mark.parametrize(
    ("text", "step"),
    [
        ("pin the history essay", "pin_note"),
        ("pin my study plan", "pin_note"),
        ("delete the pasta recipe", "delete_note"),
        ("bin my gym log", "delete_note"),
        ("tag my gym log with fitness", "tag_note"),
        ("add the tag fitness to the gym log", "tag_note"),
        ("rename my gym log to Training log", "edit_note"),
    ],
)
def test_a_bare_title_act_plans_a_step_on_that_note(session, text, step):
    from tessellate.ai import acts

    for content, category, _when in NOTES:
        manager.create_entry(session, content, category)
    session.commit()
    planned = acts.preview(session, acts.parse(text, _NOW))
    steps = (planned.get("card") or {}).get("steps") or planned.get("steps") or []
    assert [s["name"] for s in steps] == [step], planned
    titles = {e.id: e.content.splitlines()[0] for e in session.query(Entry).all()}
    wanted = text.split(" the ")[-1].split(" my ")[-1].split(" to ")[0].split(" with ")[0].lower()
    args = steps[0]["arguments"]
    note_id = args.get("note_id") or (args.get("note_ids") or [None])[0]
    assert wanted in titles[note_id].lower(), planned


def test_an_unknown_title_asks_which_note(session):
    from tessellate.ai import acts

    manager.create_entry(session, "# Gym log\n\nSquats", "Health")
    session.commit()
    planned = acts.preview(session, acts.parse("delete the sourdough starter", _NOW))
    assert "sourdough starter" in (planned.get("line") or "") and "gym" not in planned.get("line", "").lower(), planned


# E12: an instruction is not a subject, and a note linked only by rank is never cited

QUOTES_UNRELATED = re.compile(r"fry garlic|deadlift 100kg|biology exam on 12", re.I)

UNFINISHED_ACTS = [
    "rename my gym log",
    "tag my gym log",
    "please rename the history essay",
    "i want to rename the history essay",
]


@pytest.mark.parametrize("question", UNFINISHED_ACTS)
def test_an_act_missing_its_other_half_says_how_to_finish_it(ask, question):
    said = ask(question)
    assert "say it like this" in said, said
    assert not QUOTES_UNRELATED.search(said), said
    assert "None of these" not in said


NO_SUCH_LIST = [
    "add milk to my shopping list",
    "add eggs to my shopping list",
    "put bread on the shopping list",
    "add oat milk to the groceries list",
    "append call mum to my errands log",
]


@pytest.mark.parametrize("question", NO_SUCH_LIST)
def test_an_act_on_a_note_that_is_not_there_never_quotes_another(ask, question):
    said = ask(question)
    assert not QUOTES_UNRELATED.search(said), said
    assert "From what you've written" not in said and "You captured this" not in said


def test_an_instruction_word_is_not_evidence(ask):
    from tessellate.ai import composer

    assert "add" not in composer.plan("add milk to my shopping list").terms
    assert "rename" not in composer.plan("rename my gym log").terms
    assert "delete" not in composer.plan("delete my old wifi password").terms
    assert "add" in composer.plan("what did I add to the pasta").terms


# E11: the commonest student asks gather the whole category, not one note

ALL_UNI_DATES = ["problem set 6", "3 december|essay", "12 november|exam", "20 november|presentation"]
DUE_FOR_UNI = [
    "what is due for uni",
    "what's due in uni",
    "whats due for uni this term",
    "what deadlines do I have for uni",
    "what do I have coming up for uni",
    "uni deadlines",
    "anything due for uni",
    "show me what is due for my uni notes",
]


@pytest.mark.parametrize("question", DUE_FOR_UNI)
def test_due_for_a_category_lists_every_dated_item_in_it(ask, question):
    said = ask(question)
    for needle in ["2 November", "12 November", "20 November", "3 December"]:
        assert needle in said, (needle, said)
    assert "Dentist" not in said and "Pasta" not in said and "dentist" not in said.lower(), said
    lines = [line for line in said.splitlines() if line.startswith("- ")]
    assert [re.match(r"- (\d+ \w+)", line).group(1) for line in lines] == ["2 November", "12 November", "20 November", "3 December"], said


@pytest.mark.parametrize("question", ["what exams do I have", "which exams are coming up", "any exams coming up?", "do I have any exams"])
def test_a_kind_of_deadline_lists_just_that_kind(ask, question):
    said = ask(question)
    assert "12 November" in said and "Biology exam" in said, said
    assert "problem set" not in said.lower() and "presentation" not in said.lower(), said


@pytest.mark.parametrize(
    ("question", "inside", "outside"),
    [
        ("what is due for uni this week", ["2 November"], ["12 November"]),
        ("what is due for uni in the next 20 days", ["2 November", "12 November"], ["20 November", "3 December"]),
        ("what's due for uni before december", ["2 November", "12 November", "20 November"], ["3 December"]),
        ("what is due for uni by 15 november", ["2 November", "12 November"], ["20 November"]),
    ],
)
def test_due_for_a_category_in_a_window_keeps_the_window(ask, question, inside, outside):
    said = ask(question)
    for needle in inside:
        assert needle in said, (needle, said)
    for needle in outside:
        assert needle not in said, (needle, said)


STILL_TO_READ = [
    "what do I still need to read for history",
    "what do I need to read for history",
    "what is left to read for history",
    "what have I got left to read for the history essay",
    "what do I still have to read for uni",
]


@pytest.mark.parametrize("question", STILL_TO_READ)
def test_still_to_do_reads_the_open_checklist_of_what_is_named(ask, question):
    said = ask(question)
    assert "Hobsbawm chapter 2" in said and "Evans chapter 4" in said, said


@pytest.mark.parametrize(
    "question",
    ["what do I still need to read for biology", "what do I need to read for biology", "what is left to read for the biology exam"],
)
def test_still_to_do_for_a_subject_with_no_checklist_says_so_instead_of_quoting_another(ask, question):
    said = ask(question)
    assert "Hobsbawm" not in said and "Sources to read" not in said, said
    assert re.search(r"nothing|no (?:open|unticked|checklist)|isn't|is no|not", said, re.I), said


STUDY_BIO = ["flashcards from my biology notes", "make flashcards from my biology notes", "quiz me on my biology notes", "flashcards for biology"]


@pytest.mark.parametrize("question", STUDY_BIO)
def test_study_aids_for_a_subject_use_the_notes_about_it(ask, question):
    said = ask(question)
    assert "Study plan" not in said and "no definitions" not in said, said
    assert re.search(r"mitosis|enzyme|osmosis|cell|biology", said, re.I), said


@pytest.mark.parametrize("question", ["summarise my biology notes", "summarize my biology notes", "give me a summary of my biology notes", "sum up my biology notes"])
def test_a_summary_of_a_subject_covers_every_note_on_it(ask, question):
    said = ask(question)
    assert "Mitosis" in said or "mitosis" in said, said
    assert "Osmosis" in said or "osmosis" in said or "enzyme" in said.lower(), said
    assert "12 November" in said, said


def test_dump(ask):
    if not _DUMP:
        pytest.skip('dev dump')
    for q in DUMP_QS:
        ask(q)


DUMP_QS = ["quiz me on my biology notes", "summarise my biology notes", "summarize my biology notes", "flashcards from my biology notes"]


@pytest.mark.parametrize("instruction", ["get rid of the old stuff please", "delete all the junk", "bin whatever is left", "remove everything from last year", "trash the rest"])
def test_a_vague_object_is_not_a_note_title(instruction):
    from tessellate.ai import acts

    assert acts.parse(instruction, _NOW) is None or "bare" not in str(acts.parse(instruction, _NOW))


@pytest.mark.parametrize("question", ["what are the deadlines for the tax return", "what is due for the boiler", "what is the upcoming iPhone release"])
def test_a_due_question_about_a_name_no_note_is_filed_under_is_answered_as_before(ask, question):
    assert "Nothing in your" not in ask(question) or "has a day" not in ask(question)
