"""L236: a joke names the note it came from as the person wrote its title, and a
note's backlinks are reachable by the words a person uses ("what backlinks does
orchard have"), not only "what links to"."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.api import chat_said, chat_turn, routes_chat
from tessellate.core import clock
from tessellate.core.database import EntryLink
from tessellate.entry import manager
import tests._seed_composer_1110 as seed

NOW = seed.NOW


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    for module in (routes_chat, chat_said, chat_turn):
        monkeypatch.setattr(module, "user_now", lambda _config: NOW)
    monkeypatch.setattr(clock, "today", lambda: NOW.date())


def _post(client, question, **extra):
    body = {"question": question, "history": [], "use_tools": False, **extra}
    with client.stream("POST", "/chat/stream", json=body) as response:
        events = [json.loads(line) for line in response.iter_lines() if line.strip()]
    return "".join(e.get("delta", "") for e in events if e.get("type") == "answer")


@pytest.fixture
def notes(session):
    ids = []
    for content in ("Orchard\n\nPick the apples before the frost", "Orchard jokes\n\nWhy did the apple go to school? To get a little cider"):
        entry = manager.create_entry(session, content, category_name="Fun", tags=["jokes"])
        entry.created_at = entry.updated_at = datetime(2026, 10, 2, 10)
        ids.append(entry.id)
    session.add(EntryLink(source_entry_id=ids[1], target_entry_id=ids[0], reason="same trees"))
    session.commit()
    return ids


def test_a_joke_names_the_note_by_its_own_title(client, notes):
    said = _post(client, "tell me a joke")
    assert "cider" in said and "Orchard jokes" in said and "orchard jokes" not in said, said


@pytest.mark.parametrize(
    "question",
    ["what links to orchard", "what backlinks does orchard have", "show the backlinks of orchard", "what are the backlinks for the orchard note"],
)
def test_backlinks_are_asked_in_the_words_people_use(client, notes, question):
    said = _post(client, question)
    assert "linked to [**Orchard**]" in said and "Orchard jokes" in said and "same trees" in said, said
