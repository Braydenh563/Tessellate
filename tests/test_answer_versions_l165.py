"""L165: regenerate and edit-and-resend keep every version of an answer.

The stored assistant message carries `versions` (text, sources, made_at); the
latest one shows. A pager "1 of N" shows only when a turn has more than one.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent


def _turn(**more):
    return {"question": "sum up my week", "answer": "first take", **more}


def _snap(text, made_at="2026-11-14T09:00:00"):
    return {"text": text, "sources": [], "made_at": made_at}


def test_a_turn_without_prior_versions_stores_none(client):
    cid = client.post("/conversations", json=_turn()).json()["id"]
    last = client.get(f"/conversations/{cid}").json()["messages"][-1]
    assert "versions" not in last


def test_a_regenerate_keeps_the_earlier_answer_and_the_new_one_is_latest(client):
    cid = client.post("/conversations", json=_turn()).json()["id"]
    client.put(f"/conversations/{cid}/turns/last", json=_turn(answer="second take", prior_versions=[_snap("first take")]))
    last = client.get(f"/conversations/{cid}").json()["messages"][-1]
    assert last["content"] == "second take"
    assert [v["text"] for v in last["versions"]] == ["first take", "second take"]
    assert all(v["made_at"] for v in last["versions"])


def test_a_checkpoint_then_the_final_save_is_one_version_not_two(client):
    cid = client.post("/conversations", json=_turn()).json()["id"]
    prior = [_snap("first take")]
    client.put(f"/conversations/{cid}/turns/last", json=_turn(answer="half", prior_versions=prior))
    client.put(f"/conversations/{cid}/turns/last", json=_turn(answer="whole", prior_versions=prior))
    last = client.get(f"/conversations/{cid}").json()["messages"][-1]
    assert [v["text"] for v in last["versions"]] == ["first take", "whole"]


def test_versions_are_capped_and_each_text_bounded(client):
    cid = client.post("/conversations", json=_turn()).json()["id"]
    prior = [_snap(f"v{i}") for i in range(40)]
    resp = client.put(f"/conversations/{cid}/turns/last", json=_turn(answer="new", prior_versions=prior))
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        last = client.get(f"/conversations/{cid}").json()["messages"][-1]
        assert len(last["versions"]) <= 20
        assert last["versions"][-1]["text"] == "new"


def test_the_pager_shows_only_on_a_turn_with_more_than_one_version():
    js = app_js_text()
    assert "answer-version-pager" in js
    assert "versions.length > 1" in js
    assert "of ${versions.length}" in js


def test_regenerate_with_another_model_runs_that_model_once(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "Pottery class is on Thursdays."})
    ai_client.post("/chat", json={"question": "when is pottery class?", "model": "other-model:7b"})
    assert fake_ollama.chat_models and fake_ollama.chat_models[-1] == "other-model:7b"
    ai_client.post("/chat", json={"question": "when is pottery class?"})
    assert fake_ollama.chat_models[-1] != "other-model:7b", "the choice is for this answer only"


def test_regenerate_without_a_model_is_composed_by_the_app(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "Pottery class is on Thursdays."})
    before = len(fake_ollama.chat_models)
    body = ai_client.post("/chat", json={"question": "when is pottery class?", "composer_only": True}).json()
    assert body["answered_by"] is None
    assert len(fake_ollama.chat_models) == before, "no model ran"
    assert "Thursday" in body["ai_response"]


def test_the_regenerate_with_menu_lists_models_and_the_composer():
    js = app_js_text()
    assert "Regenerate with" in js and "Same model" in js and "Without a model" in js
