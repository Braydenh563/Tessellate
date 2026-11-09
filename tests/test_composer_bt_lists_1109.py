"""bt-compcomp-1109 items 5, 6, 9: a property asked of each kind of note, a comparison that names each note once,
and plain "- " lines under a to-do title as tasks. Seed: `tests/_seed_bt_1109.py` (Monday 9 November 2026)."""

from __future__ import annotations

import time

import pytest

import tests._seed_bt_1109 as sd
from tessellate.ai import composer_each, study


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)
    return lambda q: sd.ask(client, q, notes_only=True)["text"]


def test_the_budget_of_each_project_is_one_line_a_project(ask):
    text = ask("what is the budget for each project")
    assert "4,500" in text and "12,000" in text, text
    assert "Orchard project" in text and "Harbour project" in text and "Team sync" not in text, text


@pytest.mark.parametrize("said, got", [
    ("what is the budget for each project", ("budget", "project")),
    ("What are the deadlines of every project?", ("deadlines", "project")),
    ("what is the budget for the project", None),
    ("what is the budget for each", None),
    ("tell me the budget for each project please", None),
])
def test_each_ask_is_read_by_words(said, got):
    assert composer_each._asked(said) == got


def test_a_long_question_is_read_in_bounded_time():
    for text in ("what is the " + "budget " * 20_000 + "for each project", " " * 50_000 + "what is the budget for each project", "what is the budget for each " + "x" * 50_000):
        start = time.perf_counter()
        composer_each._asked(text)
        assert time.perf_counter() - start < 0.5


def test_a_comparison_names_each_note_where_its_lines_begin(ask):
    text = ask("compare Orchard and Harbour")
    assert text.count("[**Orchard project**]") == 1 and text.count("[**Harbour project**]") == 1, text
    assert "4,500" in text and "12,000" in text, text


def test_plain_bullets_under_a_todo_title_are_the_todos(ask):
    text = ask("list my todos")
    assert "Call the dentist" in text and "Clean the bike" in text and "Nothing is open" not in text, text


def test_what_should_i_do_today_lists_them(ask):
    text = ask("what should I do today")
    assert "Water the plants" in text and "No open tasks" not in text, text


@pytest.mark.parametrize("content, tasks", [
    ("Weekend todo\n\n- Call the dentist\n- Buy paper", ["Call the dentist", "Buy paper"]),
    ("Things to do\n\n- Water the plants", ["Water the plants"]),
    ("Shopping ideas\n\n- Call the dentist", []),
    ("Todo\n\n- [x] Done thing\n- [ ] Open thing", ["Open thing"]),
])
def test_only_a_todo_titled_note_has_plain_tasks(content, tasks):
    assert study.open_tasks(content) == tasks
