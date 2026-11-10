"""INBOX 1729: the composer holds a conversation, with no model.

The owner's two turns (`/yesterday`, then "any other diagrams you can show
me?") and the statistics pair ("statistics", then "what are those distinct
tags??"), then ten scripted dialogues (`fixtures/composer/conversations_1729.json`)
each turn of which is asserted to use the turn before: it names what the last
answer showed, differs from it, and ends with Next chips. Fixed clock: Tuesday
10 November 2026, 09:00."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from tessellate.ai import composer_dialogue, composer_talk, notebook_stats
from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core.database import Category, Document
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "composer" / "conversations_1729.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["now"])
STUMPED = ("has me stumped", "Not sure what you mean", "did not catch what")


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)


def _seed(session) -> None:
    for made, category, tags, content in FIXTURE["notes"]:
        entry = manager.create_entry(session, content, category_name=category, tags=tags)
        entry.created_at = entry.updated_at = datetime.fromisoformat(made)
    for title in FIXTURE["documents"]:
        session.add(Document(title=title, content="text"))
    session.commit()


def _asks_of(offer: dict) -> list[str]:
    own = list(offer.get("asks") or []) if offer.get("kind") == "ask" else []
    return own + [a for other in offer.get("also") or [] for a in _asks_of(other)]


def _chips(events: dict) -> list[str]:
    asks = [a for e in events.get("offer", []) for a in _asks_of(e["offer"])]
    return asks + [n for e in events.get("grounding", []) for n in e.get("next") or []]


def _titles(events: dict) -> list[str]:
    return [e["chart"]["title"] for e in events.get("chart", [])] + [e["title"] for e in events.get("panel", []) if e.get("title")]


def test_the_owners_empty_day_and_other_diagrams(client, session):
    _seed(session)
    first = _ask(client, "/yesterday", history=[])
    assert first["text"].startswith("Nothing went into your notes yesterday")
    assert len(_chips(first)) >= 2, "an empty day ends with Next chips"
    again = _ask(client, "any other diagrams you can show me?", history=[{"question": "/yesterday", "answer": first["text"]}])
    assert not any(s in again["text"] for s in STUMPED)
    assert _titles(again) == ["Notes per tag"]


def test_those_distinct_tags_lists_the_tags_and_does_not_repeat_the_overview(client, session):
    _seed(session)
    first = _ask(client, "statistics", history=[])
    assert len(_chips(first)) >= 2
    again = _ask(client, "what are those distinct tags??", history=[{"question": "statistics", "answer": first["text"]}])
    assert again["text"] != first["text"]
    assert "- study (4)" in again["text"] and "10 distinct tags" in again["text"]


def test_a_demonstrative_with_its_noun_keeps_the_noun():
    history = [{"question": "statistics", "answer": "You have 9 notes.\n\nOpen Statistics for the full picture?"}]
    assert composer_dialogue.follow_on("what are those distinct tags??", history) is None
    assert composer_dialogue.follow_on("list that month", history) is None


def test_the_overview_and_the_card_count_alike(session):
    _seed(session)
    session.add(Category(name="Unused"))
    manager.create_entry(session, "# Old\n\nArchived thing.", category_name="Old").archived_at = NOW
    session.commit()
    facts = {f["label"]: f["count"] for f in notebook_stats._general_stats(session).facts}  # noqa: SLF001
    card = notebook_stats._notebook_block(session, NOW)  # noqa: SLF001
    assert facts["notes"] == card["notes"] and facts["categories"] == card["categories"]
    assert session.query(Category).count() > card["categories"], "an empty category is not 'in' any"


@pytest.mark.parametrize("dialogue", [pytest.param(d, id=d["name"]) for d in FIXTURE["dialogues"]])
def test_each_turn_uses_the_turn_before(client, session, dialogue):
    _seed(session)
    history: list[dict] = []
    before: dict | None = None
    for turn in dialogue["turns"]:
        events = _ask(client, turn["ask"], history=list(history))
        text = events["text"]
        where = f"{dialogue['name']}: {turn['ask']!r} -> {text[:200]!r}"
        assert text.strip(), where
        assert turn["ask"] == "blorpity zzq" or not any(s in text for s in STUMPED), where
        for want in turn.get("has", []):
            assert want in text, f"{want!r} missing: {where}"
        if turn.get("chart"):
            assert any(e["chart"]["by"] == turn["chart"] for e in events.get("chart", [])), where
        if turn.get("chart_or_panel"):
            assert events.get("chart") or events.get("panel"), where
        chips = _chips(events)
        assert chips, f"no Next chips: {where}"
        for want in turn.get("chips_have", []):
            assert want in chips, f"{want!r} not in {chips}: {where}"
        if before is not None:
            assert text != before["text"], f"repeats the answer before: {where}"
            if turn.get("uses"):
                seen = "\n".join([before["text"], *_chips(before), *_titles(before)])
                assert turn["uses"] in seen, f"{turn['uses']!r} not in the turn before: {where}"
        history.append({"question": turn["ask"], "answer": text})
        before = events


def test_the_stumped_line_offers_the_previous_subjects_acts(session):
    _seed(session)
    history = [{"question": "statistics", "answer": "You have 9 notes.\n\nOpen Statistics for the full picture?"}]
    assert "Which tags do I use most?" in composer_talk.stumped_asks(session, history, NOW.date())
