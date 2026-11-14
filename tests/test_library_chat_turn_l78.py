"""L78: a Library search that finds words inside a chat says which turn has them."""

from __future__ import annotations

import json

from tessellate.core.database import Conversation


def _chat(session, messages, title="Trip"):
    session.add(Conversation(title=title, messages=json.dumps(messages)))
    session.commit()


def _hits(client, q):
    return [i for i in client.get("/library", params={"q": q}).json()["items"] if i["kind"] == "chat"]


def test_a_hit_in_the_third_message_names_that_message(client, session):
    _chat(session, [
        {"role": "user", "content": "plan a trip"},
        {"role": "assistant", "content": "where to?"},
        {"role": "user", "content": "Lisbon in spring"},
        {"role": "assistant", "content": "good choice"},
    ])
    [hit] = _hits(client, "lisbon")
    assert hit["turn"] == 2


def test_a_title_only_hit_or_no_query_has_no_turn(client, session):
    _chat(session, [{"role": "user", "content": "hello"}], title="Lisbon notes")
    [hit] = _hits(client, "lisbon")
    assert hit["turn"] is None
    [plain] = _hits(client, "")
    assert plain["turn"] is None


def test_the_frontend_opens_the_turn_and_rings_it():
    from tests._app_js import app_js_text

    from pathlib import Path

    library = (Path(__file__).resolve().parents[1] / "frontend/js/library.js").read_text()
    assert "openConversation(item.id, item.turn)" in library
    js = app_js_text()
    assert "async function openConversation(id, turn = null)" in js
