"""Replies the app helps draw (INBOX 1300 C06, the owner: "if I ask for stats
I want a panel with cards and icons and visualised statistics and a link to
open the statistics panel ... an interactive calculator popup that is
accessible and also link it to the /calc command as well as other unit
conversions"). The stream says which panel an answer carries (`panel`
events); one lazy renderer draws it on every surface, whoever wrote the
words (CHAT_PLAN decision 75: the panel assists, the model still leads).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tessellate.ai import tools
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _stream(client, question):
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _panels(events):
    return [e for e in events if e["type"] == "panel"]


def _seed(session):
    for text, tags in (("Boiler pressure is low", ["home"]), ("Gym plan for the week", ["health"])):
        tools.execute_tool(session, "create_note", {"content": text, "tags": tags})
    session.commit()


def test_a_stats_question_carries_the_statistics_panel(ai_client, fake_ollama, session):
    fake_ollama.running = False
    _seed(session)
    assert _panels(_stream(ai_client, "notebook stats")) == [{"type": "panel", "panel": "statistics"}]
    assert _panels(_stream(ai_client, "/stats")) == [{"type": "panel", "panel": "statistics"}]


def test_the_panel_comes_whoever_writes_the_words(ai_client, fake_ollama, session):
    fake_ollama.running = True
    _seed(session)
    assert _panels(_stream(ai_client, "notebook stats")) == [{"type": "panel", "panel": "statistics"}]


def test_a_sum_or_a_conversion_carries_the_calculator(ai_client, fake_ollama, session):
    fake_ollama.running = False
    assert _panels(_stream(ai_client, "/calc 12*(3+4)")) == [{"type": "panel", "panel": "calculator", "input": "12*(3+4)"}]
    assert _panels(_stream(ai_client, "/calc")) == [{"type": "panel", "panel": "calculator", "input": ""}]
    assert _panels(_stream(ai_client, "5 km to miles")) == [{"type": "panel", "panel": "calculator", "input": "5 km to miles"}]
    #: An answer about the notes carries no panel.
    assert _panels(_stream(ai_client, "hello")) == []


def test_the_calculator_works_out_through_the_chat_tools_reader(ai_client):
    got = ai_client.get("/utilities/work", params={"q": "5 km to miles"}).json()
    assert got["answer"] == "5 kilometres is 3.11 miles." and got["read_as"] == "5 kilometres in miles"
    assert ai_client.get("/utilities/work", params={"q": "12*(3+4)"}).json()["answer"] == "12*(3+4) is 84."
    assert "error" in ai_client.get("/utilities/work", params={"q": "banana"}).json()
    units = ai_client.get("/utilities/units").json()
    assert "kilometres" in units["length"] and "USD" in units["currency"]


def test_every_answer_surface_draws_the_panel_with_one_renderer():
    code = app_js_text()
    assert 'event.type === "panel" && onPanel' in code
    assert re.search(r'replyKit: \["/css/reply-kit-lazy\.css", "/js/reply-kit\.js"\]', code)
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "function renderReplyPanel(holder, event)" in kit
    assert "onPanel:" in (JS / "chat-attach.js").read_text(encoding="utf-8")
    #: Ask and the popup agent draw theirs once the answer is final, through one drawer.
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    assert "function drawAnswerPanels(holder, panels, before = null)" in ask and "replyDrawAll(holder, panels, before)" in ask
    assert "renderReplyPanel(holder, event)" in kit and "drawAnswerPanels(timeline.holder, [event])" in (JS / "chat-attach.js").read_text(encoding="utf-8")
    for name in ("capture-ask.js", "palette.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert "onPanel:" in source and "drawAnswerPanels(answerBox" in source, name
    #: One recipe: a reply panel is drawn by reply-kit.js and nowhere else.
    others = [p.name for p in JS.glob("*.js") if p.name != "reply-kit.js" and '"reply-panel' in p.read_text(encoding="utf-8")]
    assert not others, f"a reply panel built outside reply-kit.js: {others}"


def test_web_results_are_cards_and_a_read_page_is_a_fold():
    """INBOX 1300 C06: "a websearch shows the link as a clickable card not
    just a url, and also if it does a url fetch, it has a dropdown that opens
    a semi large panel with the extracted and formatted contents inside as
    well as a link and data"."""
    kit = (JS / "ask-compose.js").read_text(encoding="utf-8")
    assert 'item.className = "web-result-card";' in kit and "web-result-title card-open" in kit
    assert "function renderWebSources(holder, sources, { read = false } = {})" in kit
    #: The reader is the page's blocks as Markdown, with its facts line.
    assert "renderMarkdown(body, markdown)" in kit and "web-reader-facts" in kit
    for name in ("chat-attach.js", "palette.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert 'event.tool === "read_url"' in source and "read: true }]" in source, name
    css = (ROOT / "frontend" / "css" / "ask-compose-lazy.css").read_text(encoding="utf-8")
    assert "max-block-size: min(32rem, 60dvh);" in css


def test_the_calculator_is_one_sheet_reached_three_ways():
    """INBOX 1300 C06: "an interactive calculator popup that is accessible
    and also link it to the /calc command as well as other unit
    conversions"."""
    kit = (JS / "reply-kit.js").read_text(encoding="utf-8")
    assert "calculator: (event) => replyCalcPanel(event)" in kit
    assert 'function openCalculator(input = "")' in kit and 'name: "calculator"' in kit and "openSheet({" in kit
    #: Accessible: a live result, a keypad that is one Tab stop walked by the
    #: arrows, keys named for what they do, a mode switch that says which is on.
    assert 'out.setAttribute("aria-live", "polite")' in kit
    assert "key.tabIndex = i === 0 ? 0 : -1;" in kit and "ArrowDown: 4" in kit
    assert '"*": "Times"' in kit and 'modes.className = "tabs-line popup-kinds calc-modes";' in kit
    #: The same reader as /calc, and the units from the app's own tables.
    assert "/utilities/work?q=" in kit and 'apiJson("/utilities/units")' in kit
    #: "/calc" alone opens it; the palette has a row with its line of help.
    assert "if (!event.input) requestAnimationFrame(() => openCalculator());" in kit
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    row = next(line for line in panes.splitlines() if 'label: "ph:calculator Calculator"' in line)
    assert "about:" in row and 'ensureModule("replyKit").then(() => openCalculator())' in row
