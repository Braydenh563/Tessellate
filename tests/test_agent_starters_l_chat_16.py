"""L-chat-16: the popup agent's starters are verb-plus-slot chips with the
three most recently used offered ahead of the twelve (CHAT_PLAN research
note on quick-action panels, decision 9's twelve)."""

from __future__ import annotations

import re
from pathlib import Path

#: palette.js loads after the app's last script, so `app_js_text` does not hold it.
JS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "palette.js").read_text(encoding="utf-8")


def _starters() -> list[tuple[str, str, str]]:
    block = JS.split("const AGENT_STARTERS = [", 1)[1].split("];", 1)[0]
    return re.findall(r'group: "([^"]+)", label: "([^"]+)", text: "([^"]+)"', block)


def test_decision_nine_twelve_in_five_verb_groups():
    starters = _starters()
    assert len(starters) == 12
    assert [g for g in dict.fromkeys(g for g, _, _ in starters)] == ["Capture", "Find", "Summarise", "Remind", "Do"]


def test_a_slot_chip_shows_an_ellipsis_and_leaves_the_caret_after_its_verb():
    slots = [(label, text) for _, label, text in _starters() if text.endswith(" ")]
    assert len(slots) >= 4, slots
    assert all(label.endswith("…") for label, _ in slots), slots
    assert ("Remind me to…", "Remind me to ") in slots


def test_a_full_chip_has_no_slot():
    for _, label, text in _starters():
        if not text.endswith(" "):
            assert not label.endswith("…"), label


def test_the_three_most_recent_come_ahead_of_the_twelve():
    assert "const AGENT_STARTERS_RECENT_MAX = 3;" in JS
    render = JS.split("const recent = agentStarterRecents();", 1)[1]
    assert render.index('groups.push(["Recent"') < render.index("for (const starter of [...AGENT_STARTERS")
    assert "kept.slice(0, AGENT_STARTERS_RECENT_MAX)" in JS
