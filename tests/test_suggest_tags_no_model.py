"""Tag suggestions for a draft with no model (the brief's item 20).

Measured on the running app before: every keystroke pause in Capture with no
model called `librarian.suggest_tags`, which called the model client with no
model, and the route logged a WARNING with a traceback each time (three per
note typed) and offered nothing. With no model running the notebook's own
tags answer (`tagging.suggest`, the same fallback filing uses),
the model is never asked, and the server says so once, at INFO.
"""

from __future__ import annotations

import logging

from tessellate.entry import assist



def test_no_model_suggests_the_notebooks_own_tags_without_a_traceback(client, caplog):
    from tessellate.core import deps

    for text in ("Netting the beans in the garden", "Garden beds need compost", "Garden tomatoes staked"):
        client.post("/entries", json={"content": text, "tags": ["garden"]})
    assist._SAID_ONCE.discard("no-model-tags")
    caplog.set_level(logging.INFO, logger="memorymap")
    first = client.post("/entries/suggest-tags", json={"content": "beans in the garden need netting"})
    again = client.post("/entries/suggest-tags", json={"content": "the garden beans again"})
    assert first.status_code == 200 and again.status_code == 200
    assert "garden" in first.json()["suggested_tags"]
    assert deps.get_ollama().chat_calls == []
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not [r for r in caplog.records if r.exc_info]
    said = [r for r in caplog.records if "tag suggestions" in r.getMessage()]
    assert len(said) == 1 and said[0].levelno == logging.INFO


def test_a_failing_model_falls_back_to_the_notebooks_own(ai_client, fake_ollama, monkeypatch):
    for text in ("Netting the beans in the garden", "Garden beds need compost"):
        ai_client.post("/entries", json={"content": text, "tags": ["garden"]})

    def boom(*args, **kwargs):
        raise RuntimeError("model went away")

    monkeypatch.setattr(assist.librarian, "suggest_tags", boom)
    response = ai_client.post("/entries/suggest-tags", json={"content": "beans in the garden"})
    assert response.status_code == 200
    assert "garden" in response.json()["suggested_tags"]


def test_a_turned_down_tag_is_listed_and_can_be_restored(client, session):
    """The owner, 2026-10-10: "if I click the not about [this tag], don't show
    this again, is there a way to undo it or see the list of things not to
    show again". The note carries `discarded_tags`; `restore` takes one off
    that list and offers it again."""
    import json

    from tessellate.core.database import Entry

    made = client.post("/entries", json={"content": "Snapshot of the local model stack"}).json()
    row = session.get(Entry, made["id"])
    row.suggested_tags = json.dumps(["university", "study"])
    session.commit()
    after = client.post(f"/entries/{made['id']}/suggested-tags", json={"discard": ["university"]}).json()
    assert after["discarded_tags"] == ["university"] and after["suggested_tags"] == ["study"]
    back = client.post(f"/entries/{made['id']}/suggested-tags", json={"restore": ["university"]}).json()
    assert back["discarded_tags"] == []
    assert sorted(back["suggested_tags"]) == ["study", "university"]
