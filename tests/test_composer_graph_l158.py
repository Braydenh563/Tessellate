"""L158 (Brief 97, INBOX 1847): the composer is the graph maker where the
person already asks. "chart this: Mon 3, Tue 5" and "chart my notes on
running" answer with the ```chart fence the / menu's chart maker saves, so
Chat and Ask draw it (with Save as SVG and CSV) and Save as a note keeps it.

Measured before (scratch probe, 12 graph-shaped asks, no model): pasted
values got "Not sure what you mean", "chart my notes about running" got
"Notes per month, all time, 3 in all." with no subject, and none drew."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import composer_graph
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

ROOT = Path(__file__).resolve().parents[1]
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _fence(text: str) -> list[str]:
    start = text.index("```chart\n") + len("```chart\n")
    return text[start : text.index("\n```", start)].splitlines()


# --- what is asked ----------------------------------------------------------------


@pytest.mark.parametrize("question", [
    "chart this: Mon 3, Tue 5, Wed 4",
    "chart this\nMon 3\nTue 5",
    "graph this",
    "make a bar chart of Mon 3, Tue 5, Wed 4",
    "plot my notes on running",
    "chart my notes about running",
    "graph my notes about running",
    "make a line graph of my running notes",
    "can you chart my running times",
    "make a chart",
])
def test_a_chart_or_graph_asked_for_is_read_as_one(question):
    assert composer_graph.asks(question), question


@pytest.mark.parametrize("question", [
    "what is a bar chart",
    "how do I make a chart",
    "chart my notes per month",
    "show notes per tag",
    "how many notes did I write each week",
    "notes about the org chart",
    "make a flowchart of the move",
    "draw a mind map of my notes on running",
    "graph how my notes about running link",
])
def test_a_question_about_charts_or_a_counted_chart_is_not(question):
    assert not composer_graph.asks(question), question


# --- values given ------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Mon 3, Tue 5, Wed 4",
    "Mon 3\nTue 5\nWed 4",
    "Mon: 3\nTue: 5\nWed: 4",
    "Mon, 3\nTue, 5\nWed, 4",
    "| Day | Hours |\n| --- | --- |\n| Mon | 3 |\n| Tue | 5 |\n| Wed | 4 |",
    "- Mon 3\n- Tue 5\n- Wed 4",
    "Mon 3 Tue 5 Wed 4",
])
def test_values_read_in_every_pasted_shape(text):
    assert composer_graph.rows_of(text) == [("Mon", 3), ("Tue", 5), ("Wed", 4)]


def test_a_table_header_names_the_chart_and_commas_in_numbers_read():
    assert composer_graph.rows_of("Rent paid late 1,200\nGym $45") == [("Rent paid late", 1200), ("Gym", 45)]
    title = composer_graph.table_title("| Month | Spend |\n| --- | --- |\n| Jan | 4 |\n| Feb | 5 |")
    assert title == "Spend per month"


def test_pasted_values_answer_with_the_fence_the_maker_saves():
    out = composer_graph.pasted("chart this: Mon 3, Tue 5, Wed 4")
    assert out["text"].startswith("Here are your 3 values as a bar chart.")
    assert _fence(out["text"]) == ["title: Chart", "kind: bar", "Mon, 3", "Tue, 5", "Wed, 4"]
    line = composer_graph.pasted("make a line graph: Jan 2.5\nFeb 3\nMar 4")
    assert _fence(line["text"])[:3] == ["title: Chart", "kind: line", "Jan, 2.5"]


def test_this_means_the_answer_before_when_nothing_is_pasted():
    out = composer_graph.pasted("chart this", previous="Your spend:\n\n- Food 120\n- Rent 900\n- Bus 40")
    assert _fence(out["text"])[2:] == ["Food, 120", "Rent, 900", "Bus, 40"]


def test_a_label_never_carries_the_makers_separators():
    out = composer_graph.pasted("chart this:\nRent; paid, late 1200\nGym 45")
    assert _fence(out["text"])[2] == "Rent paid late, 1200"


def test_a_bare_ask_says_the_two_ways():
    out = composer_graph.pasted("make a chart")
    assert "chart this: Mon 3, Tue 5" in out["text"] and "chart my notes on running" in out["text"]
    assert "```" not in out["text"] and "\u2014" not in out["text"]


def test_one_value_is_not_a_chart():
    out = composer_graph.pasted("chart this: Mon 3")
    assert "```" not in out["text"] and "two or more" in out["text"]


@node
def test_the_fence_parses_back_in_the_chart_maker():
    out = composer_graph.pasted("chart this:\n| Day | Hours |\n|---|---|\n| Mon | 7 |\n| Tue | 6.5 |")
    body = "\n".join(_fence(out["text"]))
    runner = (
        'const fs=require("fs"),vm=require("vm");const win={};'
        'vm.runInNewContext(fs.readFileSync(process.argv[1],"utf8"),{window:win,document:{},getComputedStyle:()=>({})});'
        'process.stdout.write(JSON.stringify(win.drawAskChart.maker.parse(process.argv[2])));'
    )
    got = subprocess.run(["node", "-e", runner, str(ROOT / "frontend/js/ask-chart.js"), body], capture_output=True, text=True, check=True, timeout=30)
    chart = json.loads(got.stdout)
    assert chart == {"title": "Hours per day", "kind": "bar", "rows": [{"label": "Mon", "value": 7}, {"label": "Tue", "value": 6.5}]}


# --- from the notes ----------------------------------------------------------------


def _note(i, title, body, day, tags=("running",)):
    return {"id": i, "title": title, "content": f"# {title}\n\n{body}", "tags": list(tags), "created_at": day}


RUNS = [
    _note(2, "Long run", "Ran 8 km in 50 minutes.", "2026-11-09"),
    _note(1, "First run", "Ran 5 km in 31 minutes, felt slow.", "2026-11-02"),
    _note(3, "Tempo", "Ran 6.5km in 35 minutes.", "2026-11-12"),
    _note(4, "Shoes", "New running shoes, very comfy.", "2026-11-05"),
    _note(5, "Soup", "Lentil soup, 2 cups of stock.", "2026-11-06", tags=()),
]


def test_the_notes_shared_measure_is_drawn_one_point_a_note_oldest_first():
    out = composer_graph.from_notes("chart my notes on running", RUNS)
    rows = _fence(out["text"])
    assert rows == ["title: Running: km per note", "kind: line", "First run, 5", "Long run, 8", "Tempo, 6.5"]
    assert out["text"].startswith("Your 3 notes on running, charted by km, oldest first. 1 other note on it names no km.")


def test_the_question_picks_the_measure():
    rows = _fence(composer_graph.from_notes("chart my running times", RUNS)["text"])
    assert rows[:3] == ["title: Running: minutes per note", "kind: line", "First run, 31"]


def test_notes_with_no_shared_measure_are_a_mind_map_said_so():
    notes = [_note(1, "Shoes", "New running shoes.", "2026-11-05"), _note(2, "Route", "The river loop for running.", "2026-11-06")]
    out = composer_graph.from_notes("graph my notes about running", notes)
    assert out["text"].startswith("Your 2 notes on running hold no numbers with a shared unit to chart, so here they are as a mind map.")
    assert "```mermaid\nmindmap" in out["text"]


def test_a_subject_no_note_names_is_left_to_the_ordinary_answer():
    assert composer_graph.from_notes("chart my notes on cycling", RUNS) is None


# --- the routes ---------------------------------------------------------------------


def _seed_runs(session):
    for title, body, day in (("First run", "Ran 5 km in 31 minutes.", 2), ("Long run", "Ran 8 km in 50 minutes.", 9), ("Tempo", "Ran 6 km in 35 minutes.", 12)):
        entry = manager.create_entry(session, f"# {title}\n\n{body}", category_name="Health", tags=["running"])
        entry.created_at = entry.updated_at = datetime(2026, 11, day, 9)
    session.commit()


def test_chat_charts_pasted_values_with_no_model(client):
    out = _ask(client, "chart this: Mon 3, Tue 5, Wed 4", use_tools=False)
    assert _fence(out["text"])[2:] == ["Mon, 3", "Tue, 5", "Wed, 4"]


def test_pasted_values_are_charted_with_a_model_on_too(ai_client, fake_ollama):
    before = len(fake_ollama.chat_models)
    out = _ask(ai_client, "chart this\nMon 3\nTue 5", use_tools=False)
    assert _fence(out["text"])[2:] == ["Mon, 3", "Tue, 5"]
    assert len(fake_ollama.chat_models) == before


def test_ask_charts_the_notes_measure(client, session):
    _seed_runs(session)
    out = _ask(client, "chart my notes on running", notes_only=True, use_tools=False, answer_from="notes")
    assert _fence(out["text"]) == ["title: Running: km per note", "kind: line", "First run, 5", "Long run, 8", "Tempo, 6"]


def test_the_counted_charts_are_unchanged(client, session):
    _seed_runs(session)
    counted = _ask(client, "chart my notes per month", use_tools=False)
    assert counted["text"].startswith("Here are your notes per week.") and "```" not in counted["text"]
    assert "```" not in _ask(client, "how many notes did I write each week", use_tools=False)["text"]


def test_the_help_topic_names_the_composer_way():
    from tessellate.ai import help_topics_more

    topic = next(t for t in help_topics_more.MORE_TOPICS if t["id"] == "chart-maker")
    assert "chart this:" in topic["body"] and "chart my notes on running" in topic["body"]


def test_a_diagram_of_notes_on_a_subject_finds_them_by_tag_and_title():
    """Before: "draw a mind map of my notes about running" over notes tagged running that say "Ran 5 km" drew nothing."""
    from tessellate.ai import composer_mermaid

    notes = [_note(1, "First run", "Ran 5 km.", "2026-11-02"), _note(2, "Long run", "Ran 8 km.", "2026-11-09")]
    out = composer_mermaid.answer("draw a mind map of my notes about running", notes)
    assert out and "```mermaid\nmindmap" in out["text"]
