"""L565: the harness audit audit-1031-harness.md asked for and nobody ran since.

Six claims, each driven through the fake transport (`tests/fakes.py`), never a
real model: every destructive tool parks for a Confirm and runs only on the
press its card made; Regenerate swaps the answer and keeps the earlier one as a
version; a model unloaded mid-turn ends the turn with a sentence and no write;
an embedding switch re-embeds every note; the support bundle carries no note
text or secret; an autonomous pass cannot run a destructive tool.
"""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from tessellate.ai import tools
from tessellate.core import deps


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _note(client, content, **extra):
    response = client.post("/entries", json={"content": content, **extra})
    assert response.status_code == 201
    return response.json()


def _document(client, title="Plan", content="one\ntwo\nthree"):
    response = client.post("/documents", json={"title": title, "content": content})
    assert response.status_code in (200, 201), response.text
    return response.json()


#: Every tool the registry marks destructive, with the call "the model" makes.
#: A new destructive tool fails `test_every_destructive_tool_is_audited` until
#: it has a row here.
def _destructive_calls(client) -> dict[str, dict]:
    note = _note(client, "delete me please", category="Junk", tags=["oldtag"])
    _note(client, "another one", category="Other")
    document = _document(client)
    return {
        "delete_note": {"note_id": note["id"]},
        "delete_tag": {"tag": "oldtag"},
        "delete_category": {"name": "Junk"},
        "merge_categories": {"source": "Junk", "target": "Other"},
        "move_notes": {"note_ids": [note["id"]], "category": "Other"},
        "delete_document": {"document_id": document["id"]},
        "delete_skill": {"name": "Tidy"},
        "delete_board_item": {"kind": "card", "item_id": 1},
        "move_board_item": {"kind": "card", "item_id": 1, "x": 10, "y": 10},
        "edit_board_item": {"kind": "card", "item_id": 1, "text": "changed"},
    }


DESTRUCTIVE = sorted(n for n, s in tools.TOOLS.items() if s.destructive)


def test_every_destructive_tool_is_audited(ai_client):
    assert set(DESTRUCTIVE) == set(_destructive_calls(ai_client))


@pytest.mark.parametrize("name", DESTRUCTIVE)
def test_each_destructive_call_parks_and_never_runs(ai_client, fake_ollama, monkeypatch, name):
    calls = _destructive_calls(ai_client)
    ran: list[str] = []
    real = tools.execute_tool

    def spy(session, tool, args, *rest, **kw):
        ran.append(tool)
        return real(session, tool, args, *rest, **kw)

    monkeypatch.setattr(tools, "execute_tool", spy)
    fake_ollama.calls((name, calls[name]))
    events = _events(ai_client, f"please {name.replace('_', ' ')} for me")
    confirms = [e for e in events if e["type"] == "confirm"]
    assert [c["name"] for c in confirms] == [name], [(e.get("type"), e.get("error") or e.get("label")) for e in events]
    assert confirms[0]["consent_id"], "a parked card carries the id its press must spend"
    assert name not in ran, f"{name} ran before anyone pressed Confirm"


def test_a_press_runs_only_what_its_card_proposed_and_only_once(ai_client, fake_ollama):
    note = _note(ai_client, "delete me please", category="Junk")
    other = _note(ai_client, "keep me", category="Junk")
    fake_ollama.calls(("delete_note", {"note_id": note["id"]}))
    card = next(e for e in _events(ai_client, "delete that junk note") if e["type"] == "confirm")
    swapped = ai_client.post("/chat/tools/execute", json={"name": "delete_note", "arguments": {"note_id": other["id"]}, "consent_id": card["consent_id"]})
    assert swapped.status_code == 409, "a card cannot be spent on a different note"
    kept = ai_client.get(f"/entries/{other['id']}")
    assert kept.status_code == 200
    fake_ollama.calls(("delete_note", {"note_id": note["id"]}))
    card = next(e for e in _events(ai_client, "delete that junk note") if e["type"] == "confirm")
    pressed = ai_client.post("/chat/tools/execute", json={"name": card["name"], "arguments": card["arguments"], "consent_id": card["consent_id"]})
    assert pressed.status_code == 200, pressed.text
    again = ai_client.post("/chat/tools/execute", json={"name": card["name"], "arguments": card["arguments"], "consent_id": card["consent_id"]})
    assert again.status_code == 409, "a second press of a spent card runs nothing"


def test_regenerate_replaces_the_answer_and_keeps_the_history(client):
    cid = client.post("/conversations", json={"question": "first question", "answer": "first answer"}).json()["id"]
    client.post(f"/conversations/{cid}/turns", json={"question": "second question", "answer": "take one"})
    earlier = [{"text": "take one", "sources": [], "made_at": "2026-11-20T10:00:00"}]
    swapped = client.put(f"/conversations/{cid}/turns/last", json={"question": "second question", "answer": "take two", "prior_versions": earlier})
    assert swapped.status_code == 200, swapped.text
    messages = client.get(f"/conversations/{cid}").json()["messages"]
    assert [m["content"] for m in messages] == ["first question", "first answer", "second question", "take two"]
    assert [v["text"] for v in messages[-1]["versions"]] == ["take one", "take two"], "the earlier answer is kept as a version"


def test_a_model_unloaded_mid_turn_ends_cleanly_and_writes_nothing(ai_client, fake_ollama):
    note = _note(ai_client, "milk and eggs", category="Shopping")
    fake_ollama.calls(("search_notes", {"query": "milk"}), ("delete_note", {"note_id": note["id"]}))
    fake_ollama.unload_after = 1  # the first round answers, the second finds no model
    events = _events(ai_client, "find my milk note and delete it")
    kinds = [e["type"] for e in events]
    assert "confirm" not in kinds and kinds[-1] == "done", kinds
    said = " ".join(str(e.get("delta") or e.get("error") or e.get("message") or "") for e in events)
    assert said.strip(), "the person is told the turn stopped"
    assert "Traceback" not in said
    kept = ai_client.get(f"/entries/{note['id']}")
    assert kept.status_code == 200


def test_an_embedding_switch_re_embeds_every_note(ai_client):
    import time

    from sqlalchemy import select

    from tessellate.core import embedswitch
    from tessellate.core.database import EmbeddingRecord

    for words in ("one note", "two notes", "three notes"):
        _note(ai_client, words)
    started = ai_client.post("/models/embedding-backend", json={"backend": "ollama", "model": "nomic-embed-text"})
    assert started.status_code == 200 and started.json()["reindex_started"] is True
    deadline = time.monotonic() + 10
    while embedswitch.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.05)
    assert embedswitch.status()["outcome"] == "completed", embedswitch.status()
    with deps.get_db().session() as session:
        records = list(session.scalars(select(EmbeddingRecord)))
    assert len(records) == 3 and {r.model_version for r in records} == {deps.get_embeddings().backend_id()}


def test_an_import_marks_the_index_stale_until_a_rebuild(ai_client):
    deps.mark_index_stale(4)
    before = ai_client.get("/models/status").json()
    assert before["index_stale_notes"] == 4
    rebuilt = ai_client.post("/models/reindex").json()
    assert rebuilt["reindex_started"] is True
    after = ai_client.get("/models/status").json()
    assert after["index_stale_notes"] == 0


def test_the_support_bundle_has_no_note_text_or_secret(ai_client, fake_ollama):
    _note(ai_client, "Quixotic walrus diary entry about my bank pin 4417-9305")
    config = deps.get_config()
    config.set_preference("display_name", "Zanzibar Person")
    config.set_preference("openai_base_url", "http://alice:hunter2secret@localhost:8080/v1")
    fake_ollama.librarian_reply = "Your quixotic walrus note mentions 4417-9305."
    _events(ai_client, "what did I write about the quixotic walrus")
    bundle = ai_client.get("/support-bundle")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        text = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist()).lower()
    # A bare "4417" also matches a log record's seq once a worker has logged that many lines.
    for secret in ("quixotic", "walrus", "4417-9305", "zanzibar", "hunter2secret"):
        assert secret not in text, f"the support bundle carries {secret!r}"


@pytest.mark.parametrize("name", DESTRUCTIVE)
def test_an_autonomous_pass_is_never_offered_a_destructive_tool(app_state, monkeypatch, name):
    """Nobody is there to confirm, so a destructive tool is barred, not parked:
    a parked card failed the whole pass and left a card nobody would see."""
    from tessellate.ai import autonomous

    seen: dict = {}

    def capture(**kwargs):
        seen.update(kwargs)
        return iter([])

    monkeypatch.setattr(autonomous.agent, "run_agent", capture)
    autonomous._working.set()
    autonomous._run_optimization()
    assert name in set(seen["blocked_tools"])
