"""Output forms (CHAT_PLAN decision 59, step 2; Brief 84): the realiser
draws an answer as a chart, a table, a card or a list, chosen by the data,
through the chat's existing blocks: the Markdown renderer's table, list and
callout, and the Ask box's chart (`drawAskChart`). Rows:
`tests/fixtures/composer/forms_1010.json`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tessellate.ai import realise, tools
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((Path(__file__).parent / "fixtures" / "composer" / "forms_1010.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", DATA["rows"], ids=lambda r: str(r["form"]))
def test_the_data_chooses_the_form(row):
    assert realise.form_of(row["data"]) == row["form"]


def test_a_table_is_the_renderers_pipe_table():
    text = realise.render([{"Reminder": "call | mum", "When": "today"}, {"Reminder": "rent", "When": None}])["text"]
    lines = text.splitlines()
    assert lines[0] == "| Reminder | When |" and lines[1] == "| --- | --- |"
    assert "call / mum" in lines[2] and len(lines) == 4


def test_a_card_is_a_callout_and_a_list_is_bullets():
    assert realise.render({"Notes": 3, "Tags": ""}, title="Your notebook")["text"] == "> [!note] Your notebook\n> - Notes: 3"
    assert realise.render(["a", "b"])["text"] == "- a\n- b"


def test_a_chart_is_the_ask_chart_shape():
    got = realise.render([{"name": "health", "notes": 4}, {"name": "home", "notes": 2}], title="Notes per tag", by="tag")
    assert got["text"] == "" and got["chart"] == {
        "title": "Notes per tag", "kind": "bar", "by": "tag", "total": 6,
        "rows": [{"label": "health", "value": 4}, {"label": "home", "value": 2}],
    }


def _seed(session):
    for text, tags, cat in (("Boiler pressure", ["home"], "House"), ("Gym plan", ["health", "gym"], "Health"), ("Run 5k", ["health"], "Health")):
        tools.execute_tool(session, "create_note", {"content": text, "tags": tags, "category": cat})
    tools.execute_tool(session, "set_reminder", {"text": "call mum", "when": "tomorrow at 9"})
    tools.execute_tool(session, "set_reminder", {"text": "pay rent", "when": "in 3 days at 10am"})


def test_each_no_model_read_says_one_line_and_draws_its_form(session):
    _seed(session)
    today = date.today()
    forms = {}
    for tool in ("list_tags", "list_categories", "count_notes", "notebook_overview", "notebook_structure",
                 "list_reminders", "list_notes", "list_skills"):
        said = realise.tool_answer(tool, tools.execute_tool(session, tool, {}), today)
        assert said is not None and said["text"].split("\n")[0].endswith("."), tool
        assert "!" not in said["text"].replace("[!note]", "") and chr(0x2014) not in said["text"]
        forms[tool] = said["form"]
    assert forms == {
        "list_tags": "chart", "list_categories": "chart", "count_notes": "chart", "notebook_overview": "card",
        "notebook_structure": "card", "list_reminders": "table", "list_notes": "list", "list_skills": "table",
    }
    assert realise.tool_answer("list_documents", tools.execute_tool(session, "list_documents", {}), today)["text"] == "You have no documents yet."


def _stream(client, question):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def test_chat_with_no_model_runs_the_read_and_sends_the_chart(ai_client, fake_ollama, session):
    fake_ollama.running = False
    _seed(session)
    session.commit()
    events = _stream(ai_client, "list my tags")
    assert next(e for e in events if e["type"] == "meta")["raw_results"] == []
    answer = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    #: Every tag named while they are few (INBOX 1357, class I), most used first.
    assert answer.startswith("You have three tags: #health (2), "), answer
    charts = [e["chart"] for e in events if e["type"] == "chart"]
    assert charts and charts[0]["by"] == "tag" and charts[0]["total"] == 4
    table = "".join(e.get("delta", "") for e in _stream(ai_client, "what reminders do I have") if e["type"] == "answer")
    assert "| Reminder | When |" in table and "call mum" in table


def test_the_chat_draws_a_chart_event_with_the_ask_chart_drawer():
    code = app_js_text()
    assert 'event.type === "chart" && onChart' in code
    assert "function drawAskChart(host, chart)" in (ROOT / "frontend" / "js" / "ask-chart.js").read_text(encoding="utf-8")
    assert "onChart:" in (ROOT / "frontend" / "js" / "chat-attach.js").read_text(encoding="utf-8")
