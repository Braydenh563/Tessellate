"""composer5: a realistic uni notebook (Biology 101, WW1, Maths problem sets,
reminders) asked with no model. Fixed clock, fixed notes."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)
BIO = (
    "# Biology 101: Cell respiration\n\n"
    "Cell respiration releases energy from glucose. The **Krebs cycle** happens in the mitochondrial matrix and makes NADH and FADH2.\n\n"
    "## Glycolysis\n\nGlycolysis splits glucose into two pyruvate and makes 2 ATP.\n\n"
    "## Electron transport\n\nThe electron transport chain makes about 32 ATP.\n\n"
    "```python\natp = 2 + 2 + 32\nprint(atp)\n```\n\n- [ ] Read chapter 4\n- [ ] Revise the Krebs cycle diagram\n"
)
WW1 = (
    "# History: Causes of WW1\n\n"
    "The main causes were militarism, alliances, imperialism and nationalism.\n\n"
    "## Alliances\n\nThe Triple Entente and the Triple Alliance split Europe in two.\n\n"
    "## The spark\n\nThe assassination of Franz Ferdinand in Sarajevo on 28 June 1914 started the crisis.\n"
)
MATHS = (
    "# Maths: Problem set 5\n\nProblem set 5 covers integration by parts.\n\n"
    "- [ ] Finish problem set 5\n\nExam on 12 November, hall B.\n"
)
NOTES = [(BIO, dt.datetime(2026, 10, 20, 9), "Lecture notes"), (WW1, dt.datetime(2026, 10, 19, 9), "Lecture notes"), (MATHS, dt.datetime(2026, 10, 18, 9), "Maths")]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when, cat in NOTES:
        manager.create_entry(session, text, cat).created_at = when
    session.add(Reminder(text="Exam", due_at=dt.datetime(2026, 11, 12, 9, 0)))
    session.add(Reminder(text="Call the landlord", due_at=dt.datetime(2026, 10, 28, 17, 0)))
    session.commit()

    def go(question: str, notes_only: bool = True, **body) -> str:
        extra = {"answer_from": "notes"} if notes_only else {}
        return _ask(client, question, notes_only=notes_only, history=[], **extra, **body)["text"]

    return go


@pytest.mark.parametrize("q", ["what is the Krebs cycle", "what caused ww1", "when was the assassination"])
def test_item1_no_unrelated_reminder_offer(ask, q):
    said = ask(q)
    assert "Remind you" not in said, said
    #: Nor a closer about a note the answer never used.
    if q == "what caused ww1":
        assert "Biology" not in said, said


@pytest.mark.parametrize("asked,on", [
    ("what is the Krebs cycle", False),
    ("explain glycolysis", False),
    ("what do I still need to do", True),
    ("when is problem set 5 due", True),
    ("when do I read chapter 4", True),
    ("when was the assassination", False),
])
def test_item1_a_reminder_is_offered_only_for_a_question_about_the_task(asked, on):
    from tessellate.ai import composer_digest
    assert composer_digest._on_topic("read chapter 4", asked) is on


@pytest.mark.parametrize("q", ["when is my exam", "what date is my exam", "when do I have my exam", "when's the exam"])
def test_item2_when_is_my_exam_names_the_reminder_and_the_note(ask, q):
    said = ask(q)
    assert "Exam" in said and "12 November" in said and "09:00" in said, said
    assert "hall B" in said and "Problem set 5" in said, said


@pytest.mark.parametrize("q", ["how long ago was 1 september", "when is my exam", "what's due this week", "what are my reminders"])
def test_item3_no_false_grounding_warning(ask, q):
    assert "Heads up" not in ask(q, notes_only=False), q


def test_item3_computed_dates_times_and_reminder_fields_are_not_claims():
    import json

    from tessellate.ai.source_check import sources_from_messages, unbacked_claims

    reminders = json.dumps([{"text": "Exam", "due_at": "2026-11-12T09:00:00"}, {"text": "Call the landlord", "due_at": "2026-10-30T17:00:00"}])
    listed = [
        {"role": "system", "content": "You are a notebook assistant."},
        {"role": "user", "content": "what are my reminders"},
        {"role": "tool", "content": reminders},
    ]
    sources = sources_from_messages(listed)
    assert unbacked_claims("You have an Exam on 12 November at 09:00 and Call the landlord on 30 October at 17:00.", sources) == []
    computed = sources_from_messages([{"role": "user", "content": "how long ago was 1 september"}])
    assert unbacked_claims("It was 50 days ago, on Tuesday 1 September 2026, 7 weeks and 1 day back.", computed) == []
    assert unbacked_claims("How long ago was it? About 14 days.", sources_from_messages([{"role": "user", "content": "hello"}])) == ["14"]
    #: A name is still a claim even on a date question.
    assert unbacked_claims("It was 50 days ago, when Robert Hughes called.", computed) == ["Robert Hughes"]


def test_item3_a_model_dates_answer_gets_no_heads_up_through_the_route(ai_client, fake_ollama, session):
    manager.create_entry(session, WW1, "Lecture notes")
    session.commit()
    fake_ollama.librarian_reply = "It was 50 days ago, on Tuesday 1 September 2026, 7 weeks and 1 day back."
    said = _ask(ai_client, "how long ago was 1 september", use_tools=False)["text"]
    assert "Heads up" not in said, said


#: The same Biology note as a student really types it: the code pasted three
#: ways (tilde fence, indented, bare lines), a to-do list, and an empty bullet.
BIO_CODE_VARIANTS = {
    "tilde": "~~~python\natp = 2 + 2 + 32\nprint(atp)\n~~~\n",
    "indented": "    atp = 2 + 2 + 32\n    print(atp)\n",
    "bare": "atp = 2 + 2 + 32\nprint(atp)\n",
    "quoted": "> ```python\n> atp = 2 + 2 + 32\n> print(atp)\n> ```\n",
}


@pytest.mark.parametrize("variant", sorted(BIO_CODE_VARIANTS))
def test_item4_pasted_code_is_never_summarised_and_no_stray_dash(variant):
    from tessellate.ai import study

    note = (
        "# Biology 101: Cell respiration\n\nCell respiration releases energy from glucose. Glycolysis makes 2 ATP.\n\n"
        "## To do\n\n- [ ] Read chapter 4\n- [ ] Revise the Krebs cycle\n\n"
        + BIO_CODE_VARIANTS[variant]
        + "\n-\n\n## Electron transport\n\nThe electron transport chain makes about 32 ATP.\n\n- \n"
    )
    for level in (-1, 0, 1):
        flat = " ".join(" ".join(s) for _t, s in study.summary(note, level))
        assert "atp =" not in flat.lower() and "print(" not in flat, (variant, level, flat)
        assert not any(p.strip(" -*+") == "" for _t, s in study.summary(note, level) for p in s), (variant, level)
        assert " - " not in " " + flat + " " or "- " not in flat.replace("Points: ", ""), (variant, level, flat)
    assert "Glycolysis" in flat and "electron transport" in flat.lower()


def test_item4_a_maths_equation_on_its_own_line_is_kept():
    from tessellate.ai import study

    note = "# Maths: Problem set 5\n\nIntegration by parts splits an integral in two.\n\nu dv = uv - v du\n\nThe sign flips when you swap them.\n"
    assert "uv" in " ".join(" ".join(s) for _t, s in study.summary(note, 1))


def test_item4_summarise_my_lecture_notes_covers_every_note_in_that_category(ask):
    said = ask("summarise my lecture notes")
    assert "#/notes/1)" in said and "#/notes/2)" in said and "#/notes/3)" not in said, said
    assert "Cell respiration" in said and "Causes of WW1" in said, said
    assert "Problem set 5" not in said, said
    assert "print(atp)" not in said and "atp = 2" not in said, said
    assert not said.rstrip().endswith("-"), said


def test_item5_a_code_block_in_a_biology_note_is_not_software(session):
    from tessellate.ai import tagging

    manager.create_entry(session, BIO, "Lecture notes")
    session.commit()
    tags = [t.lower() for t in tagging.new_topics(session, BIO, [])]
    assert "software" not in tags and "education" not in tags, tags


def test_item5_a_maths_problem_set_is_mathematics_not_education(session):
    from tessellate.ai import tagging

    tags = [t.lower() for t in tagging.new_topics(session, MATHS, [])]
    assert "mathematics" in tags and "education" not in tags and "learning" not in tags, tags


def test_item5_education_is_kept_when_the_note_names_nothing_more_specific(session):
    from tessellate.ai import tagging

    note = "# Admin\n\nThe exam timetable is out. Remember the problem set deadline and the lecture room change."
    assert "education" in [t.lower() for t in tagging.new_topics(session, note, [])]


def test_item5_a_note_that_is_mostly_code_is_still_about_code():
    from tessellate.ai import lexical_filing

    code = "# Script\n\n```python\nimport numpy\ndef main():\n    print(numpy.zeros(3))\n    return 0\n```\n"
    assert "numpy" in lexical_filing.clean(code)
    assert "print" not in lexical_filing.clean(BIO) and "python" not in lexical_filing.clean(BIO)
