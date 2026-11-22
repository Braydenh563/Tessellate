"""L118: every other tab's starter (palette.js AGENT_TAB_STARTERS) is answered by the engine with no model, never by a
nothing-found line; a starter that needs the open note, board or answer is given one."""

from __future__ import annotations

import re

import pytest

from tests.test_starter_acts import FALLBACK, ROOT, _events, notebook  # noqa: F401

JS = (ROOT / "frontend" / "js" / "palette.js").read_text("utf-8")
TABS = JS[JS.index("const AGENT_TAB_STARTERS = {") : JS.index("//: Which tab the palette is floating over")]
STARTERS = sorted(set(re.findall(r'label: "([^"]+)", text: "([^"]+)"', TABS)), key=lambda p: p[1])
#: The ones that read the open note, so the page sends it (`note_ids`), or the conversation before.
OPEN = re.compile(r"open|this conversation|last answer|linked to")


def test_the_tab_starters_were_found():
    assert len(STARTERS) >= 10


@pytest.mark.parametrize("label,text", STARTERS, ids=[t for _, t in STARTERS])
def test_each_tab_starter_runs_with_no_model(client, notebook, label, text):  # noqa: F811
    body = {}
    if OPEN.search(text):
        body["note_ids"] = [notebook[0]]
    if re.search(r"last answer|this conversation", text):
        body["history"] = [{"question": "What is due?", "answer": "One reminder due today."}]
    if text.endswith(" "):
        text = text + "call the bank"
    events = _events(client, text, **body)
    answer = "".join(e.get("delta", "") for e in events if e.get("type") == "answer").strip()
    acted = any(e.get("type") in ("act", "tool") for e in events)
    assert (answer or acted) and not FALLBACK.search(answer), (text, answer)
