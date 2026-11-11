"""INBOX 1767 (the owner, 2026-11-11): Ask "gym notes" with no model."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests import _gym_1767 as fx

NOW = datetime.fromisoformat(fx.NOW)


@pytest.fixture
def notebook(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    made = []
    for content, category, tags, written, edited, _links in fx.NOTES:
        entry = manager.create_entry(session, content, category, tags)
        entry.created_at = datetime.fromisoformat(written)
        entry.updated_at = datetime.fromisoformat(edited)
        manager.record_dates(session, entry, now=entry.created_at)
        made.append(entry)
    session.commit()
    for (*_rest, links), entry in zip(fx.NOTES, made, strict=True):
        for i, reason in links.items():
            manager.create_link(session, entry, made[i], reason=reason)
    session.commit()
    return made


def ask(client, question: str = "gym notes") -> dict:
    body = {"question": question, "answer_from": "notes", "notes_only": True, "use_tools": False}
    got: dict = {"text": "", "grounding": []}
    with client.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    got["text"] += event["delta"]
                elif event["type"] == "grounding":
                    got["grounding"].append(event)
    return got


def _sentences(got: dict) -> list[str]:
    return [r["sentence"] for g in got["grounding"] for r in g.get("sentences", [])]


def test_every_claim_is_cited(client, notebook):
    """(c) A cited sentence reads exactly as the row says, so its mark lands."""
    got = ask(client)
    for row in _sentences(got):
        assert row.lower() in got["text"].lower(), row


def test_one_statement_once(client, notebook):
    """(c) The link's reason is the two notes' own words ("Shared Tuesday 9pm legs training"), so the
    link line does not say it again beside the cited line that says the note."""
    text = ask(client)["text"].lower()
    assert "shared tuesday" not in text
    assert text.count("on tuesday for legs") == 1


def test_a_now_is_dated(client, notebook):
    """(b) "Now" in a note is read against the note's own date."""
    text = ask(client)["text"]
    assert "mentioned that now" not in text
    assert "you are spending the weekend" not in text
    assert "On 1 November, you" in text
    assert "you were spending the weekend relaxing" in text
    assert "haven't" in text and "havent" not in text


def test_filler_and_dangling_for(client, notebook):
    """(d) No chat filler, no "for gym" fragment."""
    text = ask(client)["text"]
    assert "lol" not in text.lower()
    assert "for gym." not in text


def test_two_steps_away_notes_are_not_matching_records(client, notebook):
    """(e) Notes with no gym content are not numbered matching records."""
    got = ask(client)
    names = json.dumps(got["grounding"])
    assert "Social Skills" not in names
    assert "Ice Breakers" not in names


def test_connected_notes_in_meta(client, notebook):
    """(e) Notes with no gym words that came by a link are not Matching records cards."""
    body = {"question": "gym notes", "answer_from": "notes", "notes_only": True, "use_tools": False}
    with client.stream("POST", "/chat/stream", json=body) as response:
        metas = [json.loads(line) for line in response.iter_lines() if line.strip() and '"type": "meta"' in line]
    titles = [r["title"] for r in metas[0]["raw_results"]]
    assert "The Complete Social Skills Guide" not in titles and "Ice Breakers" not in titles, titles


def test_more_button_keeps_focus():
    """(a) Pressing Show more must not focus a folded line (the label took a ring); the button toggles."""
    from pathlib import Path

    text = Path("frontend/js/ask-compose.js").read_text(encoding="utf-8")
    more = text[text.index("function digestMore"):text.index("//: The digest's one offer")]
    assert ".focus(" not in more and "button.remove()" not in more and "tabIndex" not in more
    assert "Show fewer" in more


def test_model_brief_carries_the_same_rule():
    """Parity (decision 75): the model-on overview brief says a note's "now" is its own day's, as the composer does."""
    from tessellate.ai import librarian

    assert "as of the day it was written" in librarian.ASK_OVERVIEW
