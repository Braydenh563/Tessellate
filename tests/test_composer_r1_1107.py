"""Composer round 1, 2026-11-07: findings from a fresh drive of the no-model
answer writer on a 53-note seed (docs/roadmap/agent-remaining/composer-r1-1107.md).
Fake transport throughout; the clock is fixed."""

from __future__ import annotations

import datetime as dt

import pytest

from tessellate.ai import acts, commands, notebook_stats
from tessellate.entry import manager
from tessellate.core import deps
from tessellate.core.database import Entry


def _note(session, content):
    entry = Entry(content=content, tags="[]")
    session.add(entry)
    session.flush()
    return entry


def test_d5_the_longest_note_is_ranked_by_words_and_named_by_its_title(client):
    with deps.get_db().session() as session:
        few = _note(session, "# Lisbon trip\n\n" + "Extraordinarily-long-hyphenated-compound-word " * 4)
        many = _note(session, "# Banana bread\n\n" + "cup of flour " * 12)
        session.commit()
        answer = notebook_stats.answer("what is my longest note", session)
    assert [f["id"] for f in answer.facts] == [many.id, few.id], answer.facts
    assert answer.facts[0]["label"] == "Banana bread"
    assert answer.text.startswith("Your longest note is “Banana bread”, about 36 words."), answer.text
    assert ".”." not in answer.text and "..." not in answer.text


# --- D3: "tick X" without "off" ticks ----------------------------------------------------




NOW = dt.datetime(2026, 11, 7, 10, 0, 0)


@pytest.mark.parametrize("sentence", ["tick the charger", "tick charger", "please tick the charger"])
def test_d3_a_bare_tick_names_the_task_it_completes(sentence):
    got = commands.read(sentence, NOW)
    assert got and got["intent"] == "complete" and got["about"] == "charger", got


@pytest.mark.parametrize("sentence", ["tick", "check the dentist note", "what does tick mean", "how do i cross link two topics", "strike a balance", "cross the road"])
def test_d3_other_ticks_and_crosses_are_left_alone(sentence):
    got = commands.read(sentence, NOW)
    assert (got or {}).get("intent") != "complete", got


def test_d3_the_bare_tick_ticks_the_checklist_line(session):
    manager.create_entry(session, "# Lisbon packing list\n\n- [x] Passport\n- [ ] Charger\n- [ ] Sunscreen")
    session.commit()
    planned = acts.preview(session, acts.parse("tick the charger", NOW))
    step = planned["card"]["steps"][0]
    assert planned.get("run") and "- [x] Charger" in step["arguments"]["content"], planned
