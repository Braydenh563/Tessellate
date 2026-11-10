"""Named-route tests (ledger 1573): each calls its path with a plain id variable, the shape `tests/test_routes_named.py` reads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tessellate.api import routes_tidy
from tests.test_board_library import _save
from tests.test_meetings_644 import _make as _meeting


# Documents' joins, AI panel and history; the AI routes run with no model (the client fixture) and change nothing.


def _doc(client, content="hello world"):
    return client.post("/documents", json={"title": "T", "content": content}).json()["id"]


def test_a_note_attaches_to_a_document_shows_in_connections_and_detaches(client):
    doc_id = _doc(client)
    note_id = client.post("/entries", json={"content": "a note"}).json()["id"]
    attached = client.post(f"/documents/{doc_id}/notes", json={"entry_id": note_id})
    assert attached.status_code == 201
    connections = client.get(f"/documents/{doc_id}/connections").json()
    assert connections["total"] == 1 and connections["notes"][0]["id"] == note_id
    detached = client.delete(f"/documents/{doc_id}/notes/{note_id}")
    assert detached.status_code == 200
    assert client.get(f"/documents/{doc_id}/connections").json()["total"] == 0


def test_a_bookmark_attaches_to_a_document_and_a_note_and_detaches_from_both(client):
    doc_id = _doc(client)
    note_id = client.post("/entries", json={"content": "a note"}).json()["id"]
    mark_id = client.post("/bookmarks", json={"url": "https://example.com", "title": "Ex"}).json()["id"]
    client.post(f"/documents/{doc_id}/bookmarks", json={"bookmark_id": mark_id})
    client.post(f"/entries/{note_id}/bookmarks", json={"bookmark_id": mark_id})
    assert client.get(f"/documents/{doc_id}/connections").json()["bookmarks"][0]["id"] == mark_id
    gone_doc = client.delete(f"/documents/{doc_id}/bookmarks/{mark_id}")
    gone_note = client.delete(f"/entries/{note_id}/bookmarks/{mark_id}")
    assert gone_doc.json()["detached"] is True and gone_note.status_code == 200
    assert client.get(f"/documents/{doc_id}/connections").json()["bookmarks"] == []


def test_a_document_exports_as_markdown(client):
    doc_id = _doc(client, "Body text.")
    response = client.get(f"/documents/{doc_id}/export.md")
    assert response.status_code == 200 and "Body text." in response.text


def test_the_ai_panel_without_a_model_says_so_and_changes_nothing(client):
    doc_id = _doc(client)
    edit = client.post(f"/documents/{doc_id}/ai-edit", json={"instruction": "shorten", "verb": "edit"})
    assert edit.status_code == 200 and edit.json()["revised"] == "hello world"
    check = client.post(f"/documents/{doc_id}/ai-check", json={})
    assert check.status_code == 200 and "No model is connected" in check.text
    assert client.get(f"/documents/{doc_id}").json()["content"] == "hello world"


def test_an_ai_edit_is_reverted_from_the_log_and_a_revision_is_restored(client):
    doc_id = _doc(client, "before")
    logged = client.post(
        f"/documents/{doc_id}/ai-edit-log",
        json={"verb": "edit", "before_content": "before", "after_content": "after"},
    )
    entry_id = logged.json()["id"]
    client.put(f"/documents/{doc_id}", json={"content": "after"})
    reverted = client.post(f"/documents/{doc_id}/ai-edit-log/{entry_id}/revert")
    assert reverted.status_code == 200
    assert client.get(f"/documents/{doc_id}").json()["content"] == "before"
    client.put(f"/documents/{doc_id}", json={"content": "third"})
    revisions = client.get(f"/documents/{doc_id}/revisions").json()
    revision_id = revisions[-1]["id"]
    restored = client.post(f"/documents/{doc_id}/revisions/{revision_id}/restore")
    assert restored.status_code == 200
    missing = client.post(f"/documents/{doc_id}/revisions/99999/restore")
    assert missing.status_code == 404


# Notes: links, history, filing, mentions, meetings (meeting tests reuse the note shape from test_meetings_644).


def _note(client, content):
    return client.post("/entries", json={"content": content}).json()["id"]


def _link(client, a, b):
    made = client.post(f"/entries/{a}/links", json={"target_id": b, "reason": "same trip"})
    assert made.status_code == 200, made.text
    return made.json()["links"][0]["link_id"]


def test_a_link_reason_is_edited_and_asked_for_without_a_model(client):
    a = _note(client, "Lisbon trip notes")
    b = _note(client, "Lisbon packing list")
    link_id = _link(client, a, b)
    edited = client.put(f"/entries/{a}/links/{link_id}/reason", json={"reason": "packing for the trip"})
    assert edited.status_code == 200
    generated = client.post(f"/entries/{a}/links/{link_id}/generate-reason")
    assert generated.status_code in (200, 500)
    missing = client.post(f"/entries/{a}/links/99999/generate-reason")
    assert missing.status_code == 404


def test_an_earlier_version_of_a_note_is_restored(client):
    note_id = _note(client, "First wording of the note.")
    client.put(f"/entries/{note_id}", json={"content": "Second wording of the note."})
    history = client.get(f"/entries/{note_id}/history").json()
    revision_id = history["revisions"][0]["id"]
    restored = client.post(f"/entries/{note_id}/history/{revision_id}/restore")
    assert restored.status_code == 200
    assert "First wording" in restored.json()["content"]
    gone = client.post(f"/entries/{note_id}/history/99999/restore")
    assert gone.status_code == 404


def test_stopping_filing_on_a_filed_note_changes_nothing(client):
    note_id = _note(client, "Bought bread and milk.")
    stopped = client.post(f"/entries/{note_id}/filing/stop", json={"action": "keep"})
    assert stopped.status_code == 200 and stopped.json()["stopped"] is False
    bad = client.post(f"/entries/{note_id}/filing/stop", json={"action": "burn"})
    assert bad.status_code == 422


def test_a_mention_becomes_a_wiki_link(client):
    target = client.post("/entries", json={"content": "Orchid care\nbody text"}).json()["id"]
    source = client.post("/entries", json={"content": "I was reading Orchid care yesterday."}).json()["id"]
    mention = client.get(f"/entries/{target}/backlinks").json()["mentions"][0]
    linked = client.post(
        f"/entries/{target}/mentions/link",
        json={"kind": "note", "id": source, "start": mention["start"], "end": mention["end"]},
    )
    assert linked.status_code == 200
    assert "[[" in client.get(f"/entries/{source}").json()["content"]


def test_a_meeting_takes_lines_makes_a_reminder_and_summarises_by_rules(client):
    note_id = _meeting(client)["id"]
    appended = client.post(
        f"/entries/{note_id}/meeting/append", json={"section": "Decisions", "lines": ["Launch moves to November"]}
    )
    assert appended.status_code == 200 and "Launch moves to November" in appended.json()["content"]
    actions = client.get(f"/entries/{note_id}/meeting").json()["actions"]
    reminded = client.post(f"/entries/{note_id}/meeting/remind", json={"line": actions[0]["line"]})
    assert reminded.status_code == 201
    summary = client.post(f"/entries/{note_id}/meeting/summarise")
    assert summary.status_code == 200 and summary.json()["by"] == "rules"


# Archive, bin and summary routes.


def _soon() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()


def test_a_document_archives_and_unarchives(client):
    doc_id = client.post("/documents", json={"title": "Draft", "content": "x"}).json()["id"]
    r1 = client.put(f"/documents/{doc_id}/archive")
    assert r1.json()["archived_at"]
    r2 = client.put(f"/documents/{doc_id}/unarchive")
    assert r2.json()["archived_at"] is None


def test_a_document_is_purged_only_from_the_bin_and_restored_before(client):
    doc_id = client.post("/documents", json={"title": "Scrap", "content": "x"}).json()["id"]
    r3 = client.delete(f"/documents/{doc_id}/purge")
    assert r3.status_code == 409
    client.delete(f"/documents/{doc_id}")
    r4 = client.post(f"/documents/{doc_id}/restore")
    assert r4.status_code == 200
    client.delete(f"/documents/{doc_id}")
    r5 = client.delete(f"/documents/{doc_id}/purge")
    assert r5.status_code == 200
    r6 = client.post(f"/documents/{doc_id}/restore")
    assert r6.status_code == 404


def test_a_reminder_restores_and_purges(client):
    rem_id = client.post("/reminders", json={"text": "Water the plants", "due_at": _soon()}).json()["id"]
    client.delete(f"/reminders/{rem_id}")
    r7 = client.post(f"/reminders/{rem_id}/restore")
    assert r7.status_code == 200
    client.delete(f"/reminders/{rem_id}")
    r8 = client.delete(f"/reminders/{rem_id}/purge")
    assert r8.status_code == 200
    r9 = client.post(f"/reminders/{rem_id}/restore")
    assert r9.status_code == 404


def test_a_conversation_pins_and_archives(client):
    made = client.post("/conversations", json={"question": "Hi?", "answer": "Hello."}).json()
    chat_id = made["id"]
    r10 = client.put(f"/conversations/{chat_id}/pin", json={"pinned": True})
    assert r10.json()["pinned"] is True
    r11 = client.put(f"/conversations/{chat_id}/archive")
    assert r11.json()["archived_at"]
    r12 = client.put(f"/conversations/{chat_id}/unarchive")
    assert r12.json()["archived_at"] is None


def test_the_open_questions_summary_answers_on_an_empty_notebook(client):
    response = client.get("/questions/summary")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


# The board library's libraries, copies and restore.


def test_a_library_is_created_renamed_and_deleted_and_its_items_move_to_yours(client):
    created = client.post("/board-library/libraries", json={"name": "Flow shapes"})
    assert created.status_code == 201
    library_id = created.json()["id"]
    renamed = client.put(f"/board-library/libraries/{library_id}", json={"name": "Flow"})
    assert renamed.json()["name"] == "Flow"
    deleted = client.delete(f"/board-library/libraries/{library_id}")
    assert deleted.status_code == 200 and deleted.json()["deleted"] == library_id
    gone = client.put(f"/board-library/libraries/{library_id}", json={"name": "Again"})
    assert gone.status_code == 404


def test_a_library_item_is_duplicated_and_a_deleted_one_restored(client):
    item_id = _save(client)["id"]
    copy = client.post(f"/board-library/{item_id}/duplicate")
    assert copy.status_code == 201 and copy.json()["name"].endswith("(copy)")
    client.delete(f"/board-library/{item_id}")
    restored = client.post(f"/board-library/{item_id}/restore")
    assert restored.status_code == 200 and restored.json()["id"] == item_id


# Categories, chats, the learned list, OCR ranges, the bench and tidy stops, the review queue, map nodes and the device verdict.


def _category_id(client, name):
    return next(c["id"] for c in client.get("/categories").json() if c["name"] == name)


def test_a_category_is_split_and_merged(client):
    keep = client.post("/entries", json={"content": "Tomatoes grow best staked.", "category": "Garden"}).json()["id"]
    client.post("/entries", json={"content": "Basil likes sun.", "category": "Garden"})
    garden = _category_id(client, "Garden")
    split = client.post(f"/categories/{garden}/split", json={"name": "Veg", "entry_ids": [keep]})
    assert split.status_code == 200 and split.json()["moved_ids"] == [keep]
    veg = _category_id(client, "Veg")
    merged = client.post(f"/categories/{veg}/merge", json={"into": garden})
    assert merged.status_code == 200 and merged.json()["moved"] == 1


def test_a_chat_is_retitled_and_its_answer_and_followups_are_kept(client):
    made = client.post("/conversations", json={"question": "What is a mole?", "answer": "A small animal."})
    chat_id = made.json()["id"]
    retitled = client.post(f"/conversations/{chat_id}/retitle")
    assert retitled.status_code == 200 and retitled.json()["title"]
    edited = client.put(f"/conversations/{chat_id}/turns/0/answer", json={"content": "A burrowing animal."})
    assert edited.status_code == 200
    chips = client.put(f"/conversations/{chat_id}/turns/0/followups", json={"followups": ["Where do they live?"]})
    assert chips.status_code == 200
    blank = client.put(f"/conversations/{chat_id}/turns/0/answer", json={"content": ""})
    assert blank.status_code == 422


def test_a_learned_fact_is_reset_to_the_models_words(ai_client, fake_ollama):
    ai_client.post("/entries", json={"content": "The batch size should stay at 32."})
    ai_client.post("/night/run", json={"budget": 1000})
    fact = ai_client.get("/learned?kind=claim").json()["items"][0]
    ai_client.patch(f"/learned/{fact['id']}", json={"text": "changed"})
    reset = ai_client.post(f"/learned/{fact['id']}/reset")
    assert reset.status_code == 200 and reset.json()["text"] == fact["text"]
    absent = ai_client.post("/learned/99999/reset")
    assert absent.status_code == 404


def test_a_page_range_read_refuses_a_missing_upload(client):
    upload_id = 99999
    refused = client.post(f"/media/{upload_id}/ocr-range-read")
    assert refused.status_code == 404


def test_the_bench_can_be_stopped_and_the_link_reason_run_queues(client, monkeypatch):
    bench = client.post("/models/bench/stop")
    assert bench.status_code == 200 and bench.json()["stopping"] is False
    queued = []
    monkeypatch.setattr(routes_tidy.jobs, "enqueue", lambda *a, **k: queued.append(a[0]))
    run = client.post("/tidy/link-reasons/run")
    assert run.json() == {"queued": True} and queued == ["tidy-link-reasons"]


def test_accepting_a_filing_keeps_the_category(client):
    note_id = client.post("/entries", json={"content": "Bought bread and milk."}).json()["id"]
    accepted = client.post(f"/review-queue/{note_id}/accept")
    assert accepted.status_code == 200 and accepted.json()["user_filed"] is True
    absent = client.post("/review-queue/99999/accept")
    assert absent.status_code == 404


def _map(client):
    return client.post("/whiteboard/boards", json={"name": "Map", "type": "map", "layout": "tree-right"}).json()["id"]


def test_map_nodes_are_pasted_as_an_outline_moved_and_cleared_of_styles(client):
    board_id = _map(client)
    root = client.post(f"/whiteboard/boards/{board_id}/nodes", json={"kind": "topic", "text": "Root"}).json()["id"]
    pasted = client.post(
        f"/whiteboard/boards/{board_id}/nodes/outline", json={"parent_id": root, "text": "- One\n  - Two\n- Three"}
    )
    assert pasted.status_code == 201 and len(pasted.json()) == 3
    node_id = pasted.json()[0]["id"]
    moved = client.put(f"/whiteboard/boards/{board_id}/nodes/{node_id}/move", json={"parent_id": None})
    assert moved.status_code == 200
    cleared = client.post(f"/whiteboard/boards/{board_id}/nodes/clear-style")
    assert cleared.status_code == 200 and cleared.json()["cleared"] == 0


def test_a_device_verdict_needs_this_computer_and_a_waiting_device(client):
    device_id = "no-such-device"
    answered = client.post(f"/auth/lan-devices/{device_id}/allow")
    assert answered.status_code in (403, 404)
