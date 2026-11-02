"""The agent and the skills (CHAT_PLAN section 2, the agent row): the
recogniser, the utilities and the validators offered to the model as tools,
so a small model computes nothing itself; a model answer with an unsourced
number caught at 1.0 (`source_check`, on `fixtures/composer/unsourced_1010.json`);
and a model's act proposed through the registry (`propose_act`, decision 53)."""

from __future__ import annotations

import json

import pytest
from pathlib import Path

from tessellate.ai import acts, tools, validate
from tessellate.core.database import Reminder

#: Importing `acts` registers propose_act's runner on the act registry (act_registry.py).
ACTS_LOADED = acts.__name__

ROOT = Path(__file__).resolve().parents[1]
SET = json.loads((ROOT / "tests/fixtures/composer/unsourced_1010.json").read_text(encoding="utf-8"))


def test_an_unsourced_number_is_caught_at_one_with_no_false_catch():
    caught = missed = false = 0
    for row in SET["rows"]:
        got = validate.check_model_answer(row["answer"], [SET["sources"][k] for k in row["sources"]])["unbacked"]
        numbers = [g for g in got if any(c.isdigit() for c in g)]
        for want in row["unsourced"]:
            if want in numbers:
                caught += 1
            else:
                missed += 1
        false += len([n for n in numbers if n not in row["unsourced"]])
    assert missed == 0 and false == 0, (caught, missed, false)
    assert caught == sum(len(r["unsourced"]) for r in SET["rows"])


def test_the_model_is_handed_the_apps_working(session):
    assert tools.TOOLS["calculate"].handler(session, {"question": "15% of 240"})["answer"] == "15% of 240 is 36."
    assert tools.TOOLS["calculate"].handler(session, {"question": "12 * 18.50"})["answer"] == "12 * 18.50 is 222."
    assert "error" in tools.TOOLS["calculate"].handler(session, {"question": "the meaning of life"})
    read = tools.TOOLS["read_text"].handler(session, {"text": "5 km on friday"})["read"]
    assert {r["kind"] for r in read} >= {"quantity", "date"}
    checked = tools.TOOLS["check_answer"].handler(session, {"answer": "You paid 45", "sources": ["Paid 40"]})
    assert checked["unsourced"] == ["45"] and checked["ok"] is False


def test_a_number_question_offers_the_working_tools():
    names = {t["function"]["name"] for t in tools.tool_specs_for("what is 15% of 240", agent_mode=True)} if hasattr(tools, "tool_specs_for") else None
    if names is not None:
        assert {"calculate", "read_text", "check_answer"} <= names
    groups = [names for names, _cues in tools.TOOL_GROUPS]
    assert any({"calculate", "read_text", "check_answer"} <= set(g) for g in groups)


def test_a_models_act_waits_for_confirm(session):
    before = session.query(Reminder).count()
    got = tools.TOOLS["propose_act"].handler(session, {"sentence": "remind me to call Sam on Friday at 9"})
    assert got["act_card"]["proposed"] is True and got["act_card"]["steps"]
    assert session.query(Reminder).count() == before, "a proposal writes nothing"
    assert "error" in tools.TOOLS["propose_act"].handler(session, {"sentence": "what a lovely day"})
    assert tools.TOOLS["propose_act"].ends_turn


def test_the_agent_draws_the_proposed_card():
    from tests._help_text import agent_text

    src = agent_text()
    assert 'if result.get("act_card"):' in src and 'yield result["act_card"]' in src



def test_propose_act_hands_over_as_a_proposal_the_loop_draws():
    """It ends the turn like ask_user, but its card needs the session, so the
    handover only names the sentence and the loop runs the handler."""
    event = tools.handoff_event("propose_act", {"sentence": "  pin the dentist note "})
    assert event == {"type": "act_proposal", "sentence": "pin the dentist note"}
    with pytest.raises(tools.ToolError):
        tools.handoff_event("propose_act", {})


def test_the_loop_draws_a_models_act_card_and_stops(ai_client, fake_ollama):
    """Before the handover row, the loop ended the turn without running the
    handler, so the card never drew."""
    from tests.test_ask_user import _events

    fake_ollama.tool_script = [
        [{"name": "propose_act", "arguments": {"sentence": "remind me to call Sam on Friday at 9"}}],
        [{"name": "create_note", "arguments": {"content": "should never be created"}}],
    ]
    events = _events(ai_client, "set that up for me", use_tools=True)
    assert any(e.get("proposed") is True and e.get("steps") for e in events), [e["type"] for e in events]
    assert not any(e["type"] == "answer" for e in events)
