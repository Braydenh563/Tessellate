"""Access (CHAT_PLAN decision 59, step 1; Brief 84): every tool in
`ai/tools` and every act in the registry is reached from one typed sentence
with no model, through the one reading (`reading.read`) and the act parser
(`acts.parse`). The sentences are `tests/fixtures/composer/access_1010.json`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import act_registry, acts, commands, reading
from tessellate.ai.tools import TOOLS

DATA = json.loads((Path(__file__).parent / "fixtures" / "composer" / "access_1010.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(DATA["now"])


def test_the_fixture_names_every_tool_and_every_act():
    assert set(DATA["tools"]) == set(TOOLS)
    assert set(DATA["acts"]) == set(act_registry.ACTS)


@pytest.mark.parametrize("tool", sorted(DATA["tools"]))
def test_each_tool_is_reached_from_a_sentence(tool):
    got = reading.read(DATA["tools"][tool], now=NOW)
    assert got.tool == tool, (DATA["tools"][tool], got.intent, got.tool)
    assert got.json()["tool"] == tool


@pytest.mark.parametrize("intent", sorted(DATA["acts"]))
def test_each_act_is_reached_from_a_sentence(intent):
    parsed = acts.parse(DATA["acts"][intent], NOW)
    assert parsed is not None and parsed["intent"] == intent


def test_every_act_tool_is_a_real_tool():
    named = set(act_registry.ACT_TOOLS.values()) | set(act_registry.UTILITY_TOOLS.values())
    named |= {tool for tool, _ in act_registry.TOOL_CUES}
    #: The task acts (cancel, snooze) run the composer's own steps, which a
    #: confirmed card runs without the tool table (commands.RUNNABLE).
    assert named <= set(TOOLS) | commands.RUNNABLE


def test_an_act_keeps_its_own_tool_on_the_act_corpus():
    data = json.loads((Path(__file__).parent / "fixtures" / "composer" / "acts_1010.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(data["now"])
    off = []
    for row in data["acts"]:
        got = reading.read(row["phrase"], now=now)
        want = act_registry.ACT_TOOLS.get(got.intent)
        if want and got.tool != want:
            off.append((row["phrase"], got.tool))
    assert off == []


def test_empty_input_reaches_no_tool():
    assert reading.read("", now=NOW).tool is None
