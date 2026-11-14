"""L-chat-192 (the owner: 'if I click the "not about this tag, dont show this again", is there a way to undo it or
see the list of things not to show again'): the x on a suggested tag offers an Undo toast that posts the opposite
answer, the turned-down tag shows in Settings, Data's list, and both ways back (the toast's and the list's Restore)
bring the suggestion back."""

from __future__ import annotations

import re

from tests._app_js import frontend_text
from tests.test_suggestions_inbox_kg9 import _note


def test_turning_a_tag_down_offers_undo_that_restores_it():
    body = frontend_text("tag-suggest.js")
    start = body.index("async function answerSuggestedTags")
    branch = body[start : body.index("\n}\n", start)]
    turn_down = branch[branch.index("} else {\n      offerUndo(") :]
    assert re.search(r"offerUndo\(`Turned down #\$\{tag\}`.*post\(\{ restore: \[tag\] \}\), post\(body\)", turn_down), turn_down


def test_the_undo_answer_brings_the_suggestion_back_and_the_list_shows_it_meanwhile(client):
    note = _note(client, "Garden plan for the spring")
    url = f"/entries/{note['id']}/suggested-tags"
    client.post(url, json={"discard": ["garden"]})
    assert client.get(f"/entries/{note['id']}").json()["discarded_tags"] == ["garden"]
    assert any(i["label"] == "garden" for i in client.get("/suggestions/dismissed/items").json()["items"])
    client.post(url, json={"restore": ["garden"]})
    assert client.get(f"/entries/{note['id']}").json()["discarded_tags"] == []
    assert not any(i["label"] == "garden" for i in client.get("/suggestions/dismissed/items").json()["items"])
