"""A topic's summary, on demand (GRAPH_PLAN KG6 remainder, INBOX 528).

`POST /graph/topics/summary` asks the local model for one sentence about a
topic's notes, caches it by the members and their versions, and with no model
(or a failing one) answers from the terms the notes share, never an error.
"""

from __future__ import annotations

import pytest

from tessellate.core import deps


class _Models:
    def utility_model(self) -> str:
        return "fake"


class _Ollama:
    calls: list[str] = []
    reply = "Notes about firing the kiln and testing glazes."
    fail = False

    def is_running(self) -> bool:
        return True

    def chat(self, model, messages, mode=None):  # noqa: ANN001, ARG002
        type(self).calls.append(messages[-1]["content"])
        if type(self).fail:
            raise RuntimeError("model fell over")
        return {"content": type(self).reply}


def _asked():
    """The summary prompts only (the fake also answers note filing)."""
    return [c for c in _Ollama.calls if "The notes:" in c]


class _NoOllama:
    def is_running(self) -> bool:
        return False


@pytest.fixture(autouse=True)
def _fresh():
    from tessellate.api import routes_graph

    routes_graph.reset_graph_cache()
    _Ollama.calls = []
    _Ollama.fail = False


def _notes(client, *texts):
    return [client.post("/entries", json={"content": t}).json()["id"] for t in texts]


def _ask(client, ids, terms=("#glaze", "kiln")):
    return client.post("/graph/topics/summary", json={"ids": ids, "name": terms[0], "terms": list(terms)})


def test_with_no_model_the_summary_is_the_shared_terms(client, monkeypatch):
    monkeypatch.setattr(deps, "get_ollama", _NoOllama)
    ids = _notes(client, "# Glaze A\n\nshino", "# Glaze B\n\nceladon", "# Kiln log\n\ncone 6")
    body = _ask(client, ids).json()
    assert body["source"] == "terms"
    assert body["summary"].startswith("3 notes about #glaze and kiln. Written ")
    assert "Most linked: " in body["summary"] and "Glaze A" in body["summary"]


def test_the_model_writes_it_once_and_an_edit_asks_again(client, monkeypatch):
    monkeypatch.setattr(deps, "get_ollama", _Ollama)
    monkeypatch.setattr(deps, "get_model_manager", _Models)
    ids = _notes(client, "# Glaze A\n\nshino", "# Glaze B\n\nceladon", "# Kiln log\n\ncone 6")
    first = _ask(client, ids).json()
    assert first == {"summary": _Ollama.reply, "source": "model", "cached": False}
    assert _ask(client, list(reversed(ids))).json()["cached"] is True
    assert len(_asked()) == 1
    client.put(f"/entries/{ids[0]}", json={"content": "# Glaze A\n\nshino, refired"})
    assert _ask(client, ids).json()["cached"] is False
    assert len(_asked()) == 2


def test_a_private_note_is_never_read_to_the_model(client, session, monkeypatch):
    from tessellate.core.database import Entry

    monkeypatch.setattr(deps, "get_ollama", _Ollama)
    monkeypatch.setattr(deps, "get_model_manager", _Models)
    ids = _notes(client, "# Glaze A\n\nshino", "# Diary\n\nsecret words here", "# Kiln log\n\ncone 6")
    session.get(Entry, ids[1]).is_private = True
    session.commit()
    _ask(client, ids)
    assert "secret words" not in _asked()[0] and "Diary" not in _asked()[0]
    assert "Glaze A" in _asked()[0]


def test_a_failing_model_falls_back_and_is_not_cached(client, monkeypatch):
    monkeypatch.setattr(deps, "get_ollama", _Ollama)
    monkeypatch.setattr(deps, "get_model_manager", _Models)
    _Ollama.fail = True
    ids = _notes(client, "one note", "two note", "three note")
    assert _ask(client, ids).json()["source"] == "terms"
    _Ollama.fail = False
    assert _ask(client, ids).json()["source"] == "model"


def test_no_notes_is_refused_and_a_topic_with_no_terms_still_reads(client, monkeypatch):
    monkeypatch.setattr(deps, "get_ollama", _NoOllama)
    assert client.post("/graph/topics/summary", json={"ids": []}).status_code == 422
    ids = _notes(client, "a", "b", "c")
    body = client.post("/graph/topics/summary", json={"ids": ids, "name": "Topic 2", "terms": []}).json()
    assert body["summary"].startswith("3 notes that link to each other more than to the rest.")


def test_the_extractive_sentence_is_pure_and_names_only_what_the_notes_hold():
    from datetime import datetime

    from tessellate.entry import topics

    a, b = datetime(2026, 3, 1), datetime(2026, 4, 2)
    assert topics.extractive_sentence(2, ["kiln"], a, b, ["Glaze A", "", "Third"]) == (
        "2 notes about kiln. Written 2026-03-01 to 2026-04-02. Most linked: \u201cGlaze A\u201d; \u201cThird\u201d."
    )
    assert topics.extractive_sentence(1, [], a, a, []) == (
        "1 notes that link to each other more than to the rest. Written 2026-03-01."
    )
