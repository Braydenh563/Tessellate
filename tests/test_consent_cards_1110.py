"""A typed yes or no reaches the page cards too ("Run the skill / Not now", "Run the plan"), not
only a press (owner order, 2026-11-10: every act needs consent, by button or typed in any way).
The server parks the hand-over event under a consent id like any other waiting card."""

from __future__ import annotations

from pathlib import Path

import pytest

from tessellate.ai import consent, consent_store
from tessellate.api import chat_agent
from tests.test_composer_route_688 import _ask


def _waiting(first, event):
    return [{"question": "q", "answer": first["text"] or "Waiting.", "pending_act": event["ask_label"], "pending_id": event["consent_id"]}]


@pytest.mark.parametrize("said", ["yes", "ok go ahead", "sure, please do"])
def test_a_typed_yes_starts_the_skill_the_card_waits_for(client, session, said):
    first = _ask(client, "run the daily review skill")
    event = first["run_skill"][0]
    assert event["consent_id"] and event["ask_label"].startswith("Run the skill")
    second = _ask(client, said, history=_waiting(first, event))
    started = second["run_skill"][0]
    assert started["skill"] == event["skill"] and started["consented"] is True and not started.get("consent_id")
    assert second["act"][0]["settle"] is True and second["act"][0]["consent_id"] == event["consent_id"]
    again = _ask(client, said, history=_waiting(first, event))
    assert not again.get("run_skill") and "no longer open" in again["text"]


def test_a_typed_no_drops_the_skill_card_and_starts_nothing(client, session):
    first = _ask(client, "run the daily review skill")
    event = first["run_skill"][0]
    second = _ask(client, "no thanks", history=_waiting(first, event))
    assert not second.get("run_skill") and second["act"][0]["cancel"] is True and second["act"][0]["consent_id"] == event["consent_id"]
    assert "Nothing was changed" in second["text"]


def test_a_typed_yes_starts_the_plan_the_card_waits_for():
    plan = {"type": "run_plan", "goal": "Tidy the garden notes", "steps": ["Find them", "Merge them"], "label": "ph:compass Planned 2 steps: Tidy the garden notes"}
    attached = consent.attach(dict(plan))
    assert attached["consent_id"] and attached["ask_label"] == "Tidy the garden notes"
    found = consent.read("yes", [{"question": "q", "answer": "a", "pending_act": attached["ask_label"], "pending_id": attached["consent_id"]}])
    events = chat_agent.consent_events(None, found)
    started = next(e for e in events if e["type"] == "run_plan")
    assert started["consented"] is True and started["steps"] == plan["steps"] and not started.get("consent_id")
    assert consent_store.take(attached["consent_id"]) is None


def test_a_consented_hand_over_is_not_parked_again():
    again = consent.attach({"type": "run_skill", "skill": "x", "consented": True})
    assert "consent_id" not in again


def test_the_page_marks_the_handoff_card_open_and_starts_on_a_typed_yes():
    text = Path("frontend/js/chat-turn.js").read_text(encoding="utf-8")
    block = text[text.index("if (t.handoff) {"):][:2600]
    assert "consented" in block and "ask_label" in block, block
    kit = Path("frontend/js/answer-kit.js").read_text(encoding="utf-8")
    card = kit[kit.index("function planProposalCard"):][:1800]
    assert "pendingAct" in card and "consentId" in card, card
