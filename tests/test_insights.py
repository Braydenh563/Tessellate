"""Insights (CHAT_PLAN Phase 6 step 6, decision 32): measurements with a fixed
hedge, never claims; each rule fires only on its threshold, and every slot
is a count, a date, the subject or the person's own words."""

from __future__ import annotations

import json
import re
import string
from datetime import date
from pathlib import Path

import pytest

from tessellate.ai import composer, composer_tables, factgraph, insights
from tests import _composer_eval

SEED = json.loads((Path(__file__).parent / "fixtures" / "composer" / "phase6_seed.json").read_text(encoding="utf-8"))
TODAY = date.fromisoformat(SEED["today"])
NOTES = SEED["notes"]
GOLF = [n for n in NOTES if n["id"] in (3, 4, 5, 6)]


def _note(i, content, day, tags=()):
    return {"id": i, "content": content, "created_at": day, "tags": list(tags)}


def test_every_template_slot_is_typed():
    for rule, template in composer_tables.INSIGHT_TEMPLATES.items():
        slots = {name for _lit, name, _spec, _conv in string.Formatter().parse(template) if name}
        assert slots, rule
        assert slots <= set(composer_tables.INSIGHT_SLOTS), (rule, slots - set(composer_tables.INSIGHT_SLOTS))


def _slot_ok(name, value, notes):
    kind = composer_tables.INSIGHT_SLOTS[name]
    if kind == "count":
        return isinstance(value, (int, float))
    if kind == "date":
        return bool(re.fullmatch(r"\d{1,2} [A-Z][a-z]+(?: \d{4})?", value))
    if kind == "span":
        return any(value in n["content"] for n in notes)
    if kind == "hedge":
        return value in composer_tables.INSIGHT_HEDGES.values()
    if kind == "clause":
        return value == "" or re.fullmatch(r", [a-z]+ of them after work", value)
    return isinstance(value, str) and value


def test_every_fired_insight_fills_its_slots_with_their_kind():
    notes = [
        *NOTES,
        _note(30, "# Desk\n\nI like the standing desk.", "2026-08-01"),
        _note(31, "# Desk again\n\nI don't like the standing desk any more.", "2026-09-30"),
        _note(32, "# Shed\n\nI plan to repaint the shed fence.", "2026-08-02"),
    ]
    fired = [*insights.notebook(notes, TODAY, limit=10), *insights.drift(notes, TODAY), *insights.contrast(notes, TODAY)]
    assert {i.rule for i in fired} >= {"recurrence", "load", "drift", "contrast"}
    for found in fired:
        for name, value in found.slots.items():
            assert _slot_ok(name, value, notes), (found.rule, name, value)


def test_recurrence_fires_at_three_notes_across_three_weeks_only():
    assert insights.recurrence("golf", GOLF, TODAY).text == (
        "You have written about golf 4 times since 5 September, three of them after work; that may be a hobby forming."
    )
    assert insights.recurrence("golf", GOLF[:2], TODAY) is None
    same_week = [_note(i, "# Chess\n\nChess club tonight.", f"2026-09-0{i}") for i in (1, 2, 3)]
    assert insights.recurrence("chess", same_week, TODAY) is None


def test_the_hedge_is_a_hobby_only_with_a_leisure_word():
    notes = [_note(i, "# Boiler\n\nThe boiler pressure dropped again.", day) for i, day in ((1, "2026-09-01"), (2, "2026-09-10"), (3, "2026-09-20"))]
    assert insights.recurrence("boiler", notes, TODAY).text.endswith("that keeps coming up.")


def test_a_streak_needs_consecutive_weeks_to_now():
    weekly = [_note(i, "# Run\n\nA run by the river.", day) for i, day in ((1, "2026-09-21"), (2, "2026-09-28"), (3, "2026-10-05"))]
    assert insights.streak("run", weekly, TODAY).text == "You have written about run 3 weeks running."
    assert insights.streak("golf", GOLF, TODAY) is None


def test_a_question_about_regularity_gets_the_streak_and_a_plain_one_the_count():
    weekly = [_note(i, "# Run\n\nA run by the river.", day) for i, day in ((1, "2026-09-21"), (2, "2026-09-28"), (3, "2026-10-05"))]
    assert insights.for_subject("run", weekly, TODAY, "any patterns in my run notes")[0].rule == "streak"
    assert insights.for_subject("run", weekly, TODAY, "tell me about my runs")[0].rule == "recurrence"
    assert insights.for_subject("golf", GOLF, TODAY, "any habits around golf")[0].rule == "recurrence"


def test_a_plan_with_a_later_note_is_not_drift():
    plan = _note(1, "# Fence\n\nI plan to repaint the shed fence.", "2026-08-01")
    done = _note(2, "# Fence done\n\nRepainted the shed fence green.", "2026-08-20")
    assert insights.drift([plan], TODAY) and not insights.drift([plan, done], TODAY)


def test_a_recent_plan_is_never_drift():
    assert not insights.drift([_note(1, "# Fence\n\nI plan to repaint the fence.", "2026-09-30")], TODAY)


def test_a_broad_answer_closes_with_the_insight_and_stays_grounded():
    result = composer.compose("tell me about golf", GOLF, today=TODAY)
    measures = [p[1] for p in result["parts"] if p[0] == "measure"]
    found = insights.recurrence("golf", GOLF, TODAY)
    #: After a lead that said the count, the short form (decision 52).
    assert found.text in measures or insights.after_lead(found) in measures
    assert not _composer_eval.trace_failures(result, "tell me about golf", GOLF, TODAY)


def test_the_insight_question_leads_with_the_measurement():
    result = composer.compose("any patterns in my golf notes", GOLF, today=TODAY)
    assert result["parts"][0] == ("measure", insights.recurrence("golf", GOLF, TODAY).text)


def test_an_insight_is_never_a_fact():
    facts = [f for n in GOLF for f in factgraph.facts(n)]
    assert not any("hobby" in f.text for f in facts)


@pytest.mark.parametrize("rule", sorted(composer_tables.INSIGHT_TEMPLATES))
def test_every_template_follows_the_copy_rules(rule):
    text = composer_tables.INSIGHT_TEMPLATES[rule]
    assert "!" not in text and chr(0x2014) not in text and text[0].isupper()


def test_the_patterns_route(client, session):
    from tessellate.entry import manager

    for content in ("# Golf\n\nGolf after work, a good round.", "# Golf two\n\nGolf range session.", "# Golf three\n\nGolf again."):
        manager.create_entry(session, content)
    session.commit()
    body = client.get("/insights/patterns").json()
    #: Three notes written today are one week: no recurrence, and silence.
    assert body == {"patterns": []}


def test_the_today_line_route_composes_and_rotates(client, session):
    from tessellate.entry import manager

    #: An empty notebook is welcomed in words (CHAT_PLAN 1353), not left blank.
    empty = client.get("/insights/today-line").json()
    assert empty["kind"] == "welcome" and empty["text"] and "Spice drawer" not in empty["text"]
    for content in ("# Boiler\n\nRing the landlord about the boiler.", "# Spice drawer\n\nSort the spice drawer."):
        manager.create_entry(session, content)
    session.commit()
    lines = {client.get(f"/insights/today-line?seed={s}").json()["text"] for s in range(20)}
    assert len(lines) >= 4
    assert all("**" not in line and ("Spice drawer" in line or "Boiler" in line) for line in lines)
    assert client.get("/insights/today-line?seed=2").json() == client.get("/insights/today-line?seed=2").json()
