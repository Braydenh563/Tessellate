"""Audit 1029 rank 52 (X16, H11, G18, G17): copy that names the wrong place or
the wrong cause.

- the first steps said "Change it in Settings, General" for the name, which
  lives in Settings, Profile (the step even opens that pane);
- a tool switched off in Settings, Tools it can use was refused on Confirm with
  "The note or item may have changed", the sentence for a different failure;
- the graph's hover hint told a pointer to "open" what a click only shows;
- a topic chip in the graph card wore the tag chip's look and name.

The drift test is the part that lasts: a "Settings, <pane>" path in the copy is
checked against the labels the Settings nav really has, and a first step's note
against the pane its button opens.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

#: `data-section` -> the label on the nav button, read off the page.
PANES = {
    section: html.unescape(label)
    for section, label in re.findall(r'<button[^>]*data-section="([^"]+)"[^>]*>([^<]+)</button>', INDEX)
}


def test_the_settings_nav_labels_are_read_off_the_page() -> None:
    assert PANES["preferences"] == "Profile"
    assert PANES["general"] == "General"
    assert PANES["tools"] == "Tools it can use"


def test_a_first_step_names_the_pane_its_button_opens() -> None:
    """`doneNote: "... Settings, X ..."` then `openSettingsModal("pane")`: X is that pane's label."""
    text = (JS / "first-run.js").read_text(encoding="utf-8")
    pairs = re.findall(r'Settings, ([A-Za-z &]+?)\."[^}]*?openSettingsModal\("(\w+)"', text, re.S)
    assert pairs, "the steps that point at a pane were not found"
    for named, opens in pairs:
        assert named == PANES[opens], f'the copy says "Settings, {named}" and the button opens {PANES[opens]}'


def test_every_help_topic_path_into_settings_names_a_real_pane() -> None:
    text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    paths = re.findall(r'"path": "(Settings, [^"]+)"', text)
    assert len(paths) > 40
    for path in paths:
        assert any(path.startswith(f"Settings, {label}") for label in PANES.values()), path


def test_a_tool_that_is_off_is_refused_for_that_reason(ai_client) -> None:
    ai_client.put("/preferences", json={"disabled_tools": ["delete_category"]})
    reply = ai_client.post("/chat/tools/execute", json={"name": "delete_category", "arguments": {"name": "x"}})
    assert reply.status_code == 409
    assert reply.json()["detail"] == "That tool is turned off in Settings, Tools it can use."
    batch = ai_client.post(
        "/chat/tools/execute",
        json={"name": "batch", "steps": [{"tool": "delete_category", "arguments": {"name": "x"}}]},
    )
    assert batch.status_code == 409


def test_a_tool_that_is_on_still_fails_for_its_own_reason(ai_client) -> None:
    ai_client.put("/preferences", json={"disabled_tools": []})
    reply = ai_client.post("/chat/tools/execute", json={"name": "delete_category", "arguments": {"name": "No such category"}})
    assert reply.status_code == 400
    assert "may have changed" in reply.json()["detail"]


def test_the_graph_hover_hint_does_not_call_a_click_an_open() -> None:
    text = (JS / "graph-canvas.js").read_text(encoding="utf-8")
    assert "Click for details, double-click to pin" in text


def test_the_graph_topic_chip_is_not_styled_as_a_tag() -> None:
    text = (JS / "graph.js").read_text(encoding="utf-8")
    assert 'chip(`ph:circles-three ${topic.name}`, "topic", ' in text
