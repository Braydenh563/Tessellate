"""Undo bin: deleted things (ask history, chats, files, learned facts, memory proposals, tensions) can be put back."""

from __future__ import annotations

from datetime import timedelta
import io

from tessellate.ai import memory, tensions, tools
from tessellate.core import deps, undo_bin
from tessellate.core.database import AskTurn, Entry, EntryLink, utcnow
from tessellate.entry import manager
import pytest
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)


# Ask history and the Ask again chips can be put back (INBOX 898).


def _turn(session, question, pinned=False):
    row = AskTurn(question=question, answer=f"answer to {question}", pinned=pinned)
    session.add(row)
    session.commit()
    return row.id


def _ask_again(client):
    return client.get("/chat/recent").json()


def _asked(client, session, question):
    """A question as the Ask box leaves it: a turn and the audit row behind the chip."""

    manager.log_action(session, "queried", "chat", detail=question)
    session.commit()


def test_a_deleted_question_comes_back_with_its_answer(ai_client, session):
    turn_id = _turn(session, "when is the dentist")
    gone = ai_client.delete(f"/ask-history/{turn_id}").json()
    assert gone["undo_token"]
    assert ai_client.get("/ask-history").json()["total"] == 0

    back = ai_client.post("/ask-history/restore", json={"token": gone["undo_token"]})
    assert back.json() == {"restored": 1}
    shown = ai_client.get(f"/ask-history/{turn_id}").json()
    assert shown["question"] == "when is the dentist"
    assert shown["answer"] == "answer to when is the dentist"
    reply_1 = ai_client.post("/ask-history/restore", json={"token": gone["undo_token"]})
    assert reply_1.status_code == 404


def test_deleting_a_turn_hides_its_chip_and_undo_shows_it_again(ai_client, session):
    _asked(ai_client, session, "what is the plan")
    turn_id = _turn(session, "what is the plan")
    assert _ask_again(ai_client) == ["what is the plan"]
    token = ai_client.delete(f"/ask-history/{turn_id}").json()["undo_token"]
    assert _ask_again(ai_client) == []
    ai_client.post("/ask-history/restore", json={"token": token})
    assert _ask_again(ai_client) == ["what is the plan"]


def test_clear_keeps_the_pinned_and_undo_brings_back_the_rest(ai_client, session):
    _asked(ai_client, session, "one")
    _asked(ai_client, session, "two")
    kept = _turn(session, "kept", pinned=True)
    _turn(session, "one")
    _turn(session, "two")
    cleared = ai_client.delete("/ask-history").json()
    assert cleared["deleted"] == 2
    assert [t["id"] for t in ai_client.get("/ask-history").json()["turns"]] == [kept]
    assert _ask_again(ai_client) == []

    back = ai_client.post("/ask-history/restore", json={"token": cleared["undo_token"]}).json()
    assert back == {"restored": 2}
    assert ai_client.get("/ask-history").json()["total"] == 3
    assert _ask_again(ai_client) == ["two", "one"]


def test_forgetting_a_chip_is_undone_and_redone(ai_client, session):
    _asked(ai_client, session, "alpha")
    forgot = ai_client.delete("/chat/recent", params={"question": "alpha"}).json()
    assert _ask_again(ai_client) == []
    back = ai_client.post("/chat/recent/restore", json={"marker_id": forgot["marker_id"]})
    assert back.status_code == 200
    assert _ask_again(ai_client) == ["alpha"]
    #: Redo is the same forget again.
    ai_client.delete("/chat/recent", params={"question": "alpha"})
    assert _ask_again(ai_client) == []


def test_only_a_forget_marker_can_be_lifted(ai_client, session):
    _asked(ai_client, session, "alpha")
    from tessellate.core.database import AuditLog
    from sqlalchemy import select

    queried = session.scalar(select(AuditLog).where(AuditLog.action == "queried"))
    reply_2 = ai_client.post("/chat/recent/restore", json={"marker_id": queried.id})
    assert reply_2.status_code == 404


# Editing a question and resending cuts the chat short; Undo puts the tail back (INBOX 898).


def _chat(client, turns=3):
    first = client.post("/conversations", json={"question": "q0", "answer": "a0"}).json()
    for i in range(1, turns):
        client.post(f"/conversations/{first['id']}/turns", json={"question": f"q{i}", "answer": f"a{i}"})
    return first["id"]


def _texts(client, chat_id):
    return [m["content"] for m in client.get(f"/conversations/{chat_id}").json()["messages"]]


def test_truncate_hands_back_what_it_cut_and_restore_puts_it_there(client):
    chat_id = _chat(client)
    cut = client.post(f"/conversations/{chat_id}/truncate", json={"from_turn": 1}).json()
    assert [m["content"] for m in cut["removed_messages"]] == ["q1", "a1", "q2", "a2"]
    assert _texts(client, chat_id) == ["q0", "a0"]

    back = client.post(
        f"/conversations/{chat_id}/truncate/restore", json={"from_turn": 1, "messages": cut["removed_messages"]}
    )
    assert back.status_code == 200, back.text
    assert _texts(client, chat_id) == ["q0", "a0", "q1", "a1", "q2", "a2"]


def test_restore_refuses_when_the_chat_moved_on(client):
    chat_id = _chat(client)
    cut = client.post(f"/conversations/{chat_id}/truncate", json={"from_turn": 1}).json()
    client.post(f"/conversations/{chat_id}/turns", json={"question": "new", "answer": "new"})
    refused = client.post(
        f"/conversations/{chat_id}/truncate/restore", json={"from_turn": 1, "messages": cut["removed_messages"]}
    )
    assert refused.status_code == 409


def test_cutting_the_whole_chat_answers_with_the_row_to_restore(client):
    chat_id = _chat(client, turns=2)
    cut = client.post(f"/conversations/{chat_id}/truncate", json={"from_turn": 0}).json()
    assert cut["conversation_deleted"] is True
    back = client.post("/conversations/restore", json=cut["restore"])
    assert back.status_code == 201
    assert _texts(client, chat_id) == ["q0", "a0", "q1", "a1"]


# Undo for a deleted conversation: the whole chat comes back with its pin.


def test_a_deleted_conversation_comes_back_whole(client):
    made = client.post("/conversations", json={"question": "Where is the map?", "answer": "In the drawer."}).json()
    client.post(f"/conversations/{made['id']}/turns", json={"question": "Which drawer?", "answer": "The top one."})
    client.put(f"/conversations/{made['id']}/pin", json={"pinned": True})
    before = client.get(f"/conversations/{made['id']}").json()
    gone = client.delete(f"/conversations/{made['id']}").json()
    assert gone["deleted"] is True and gone["restore"]["id"] == made["id"]
    assert client.get(f"/conversations/{made['id']}").status_code == 404
    back = client.post("/conversations/restore", json=gone["restore"])
    assert back.status_code == 201, back.text
    assert client.get(f"/conversations/{made['id']}").json() == before
    # Twice is refused, not duplicated.
    assert client.post("/conversations/restore", json=gone["restore"]).status_code == 409


# A deleted file or picture can be put back (INBOX 898, undo everywhere).


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def _upload(client, name="shot.png"):
    made = client.post("/media/upload", files={"file": (name, PNG, "image/png")}).json()
    return made


def test_a_deleted_picture_comes_back_with_its_bytes(ai_client):
    made = _upload(ai_client)
    assert ai_client.get(made["url"]).content == PNG
    gone = ai_client.delete(f"/media/{made['id']}").json()
    assert gone["undo_token"]
    assert ai_client.get(made["url"]).status_code == 404

    back = ai_client.post("/media/restore", json={"token": gone["undo_token"]})
    assert back.status_code == 200, back.text
    assert back.json()["id"] == made["id"]
    assert ai_client.get(made["url"]).content == PNG
    #: A token is used once.
    reply_1 = ai_client.post("/media/restore", json={"token": gone["undo_token"]})
    assert reply_1.status_code == 404


def test_redo_of_a_media_delete_is_another_delete(ai_client):
    made = _upload(ai_client)
    first = ai_client.delete(f"/media/{made['id']}").json()["undo_token"]
    ai_client.post("/media/restore", json={"token": first})
    again = ai_client.delete(f"/media/{made['id']}")
    assert again.status_code == 200
    assert again.json()["undo_token"] != first


def test_deleting_with_references_stripped_is_undone_in_the_notes_too(ai_client, session):
    made = _upload(ai_client)
    entry = manager.create_entry(session, f"Before\n\n![shot]({made['url']})\n\nAfter")
    session.commit()
    original = entry.content
    gone = ai_client.delete(f"/media/{made['id']}?strip_references=true").json()
    assert entry.id in gone["cleaned_notes"]
    assert made["url"] not in ai_client.get(f"/entries/{entry.id}").json()["content"]

    ai_client.post("/media/restore", json={"token": gone["undo_token"]})
    assert ai_client.get(f"/entries/{entry.id}").json()["content"] == original


def test_a_note_edited_since_keeps_its_edit_when_the_picture_returns(ai_client, session):
    made = _upload(ai_client)
    entry = manager.create_entry(session, f"![shot]({made['url']})\n\ntext")
    session.commit()
    gone = ai_client.delete(f"/media/{made['id']}?strip_references=true").json()
    ai_client.put(f"/entries/{entry.id}", json={"content": "rewritten by hand"})
    ai_client.post("/media/restore", json={"token": gone["undo_token"]})
    assert ai_client.get(f"/entries/{entry.id}").json()["content"] == "rewritten by hand"


def test_restore_refuses_a_bad_or_foreign_token(ai_client, session):
    reply_2 = ai_client.post("/media/restore", json={"token": "../../etc"})
    assert reply_2.status_code == 404
    reply_3 = ai_client.post("/media/restore", json={"token": "0" * 32})
    assert reply_3.status_code == 404
    #: A token for another kind of thing is not this route's.
    made = _upload(ai_client)
    gone = ai_client.delete(f"/media/{made['id']}").json()["undo_token"]
    reply_4 = ai_client.post("/files/restore", json={"token": gone})
    assert reply_4.status_code == 404


def _note_with_file(client, session):
    entry = manager.create_entry(session, "a note that carries a file")
    session.commit()
    response = client.post(
        f"/entries/{entry.id}/files",
        files={"file": ("lecture.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )
    assert response.status_code in (200, 201), response.text
    return entry, client.get(f"/entries/{entry.id}").json()["attachments"][0]["id"]


def test_a_deleted_attachment_comes_back_on_its_note(ai_client, session):
    entry, attachment_id = _note_with_file(ai_client, session)
    gone = ai_client.delete(f"/files/{attachment_id}")
    assert gone.status_code == 200
    token = gone.json()["undo_token"]
    assert ai_client.get(f"/entries/{entry.id}").json()["attachments"] == []
    assert ai_client.get(f"/files/{attachment_id}").status_code == 404

    back = ai_client.post("/files/restore", json={"token": token})
    assert back.status_code == 200, back.text
    attachments = ai_client.get(f"/entries/{entry.id}").json()["attachments"]
    assert [a["id"] for a in attachments] == [attachment_id]
    assert ai_client.get(f"/files/{attachment_id}").content == b"%PDF-1.4 fake"


def test_the_bin_forgets_old_stashes(app_state):
    data_dir = deps.get_config().data_dir
    token = undo_bin.stash(data_dir, "media", {"row": {}}, {})
    folder = data_dir / undo_bin.FOLDER / token
    assert folder.is_dir()
    import os
    import time

    old = time.time() - (undo_bin.KEEP_DAYS + 1) * 86400
    os.utime(folder, (old, old))
    undo_bin.prune(data_dir)
    assert not folder.exists()


# What the notebook learned can be put back (INBOX 898).


def _derive(ai_client, fake_ollama, text="The batch size should stay at 32."):
    ai_client.post("/entries", json={"content": text})
    ai_client.post("/night/run", json={"budget": 1000})
    return ai_client.get("/learned?kind=claim").json()["items"][0]


def _kinds(client):
    return [c["kind"] for c in client.get("/learned/corrections").json()]


def test_a_deleted_fact_comes_back_and_the_lesson_goes(ai_client, fake_ollama):
    fact = _derive(ai_client, fake_ollama)
    fact_id = fact['id']
    ai_client.delete(f"/learned/{fact['id']}")
    assert "delete_fact" in _kinds(ai_client)
    assert ai_client.get(f"/learned/{fact['id']}").status_code == 404

    back = ai_client.post(f"/learned/{fact_id}/restore")
    assert back.status_code == 200, back.text
    assert back.json()["text"] == fact["text"]
    assert "delete_fact" not in _kinds(ai_client)
    #: A fact that is not deleted cannot be "restored".
    reply_1 = ai_client.post(f"/learned/{fact_id}/restore")
    assert reply_1.status_code == 404


def test_a_bulk_delete_is_undone_by_a_bulk_restore(ai_client, fake_ollama):
    fact = _derive(ai_client, fake_ollama)
    ai_client.post("/learned/bulk", json={"ids": [fact["id"]], "action": "delete"})
    assert ai_client.get("/learned?kind=claim").json()["items"] == []
    done = ai_client.post("/learned/bulk", json={"ids": [fact["id"]], "action": "restore"}).json()
    assert done["done"] == 1
    assert [r["id"] for r in ai_client.get("/learned?kind=claim").json()["items"]] == [fact["id"]]
    assert "delete_fact" not in _kinds(ai_client)


def test_forgetting_everything_is_undone_whole(ai_client, fake_ollama):
    fact = _derive(ai_client, fake_ollama)
    ai_client.post("/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": 1, "b": 2}})
    forgotten = ai_client.request("DELETE", "/learned", json={"confirm": True}).json()
    assert ai_client.get("/learned").json()["items"] == []
    assert ai_client.get("/learned/corrections").json() == []

    back = ai_client.post("/learned/unforget", json={"token": forgotten["undo_token"]})
    assert back.status_code == 200, back.text
    assert [r["id"] for r in ai_client.get("/learned?kind=claim").json()["items"]] == [fact["id"]]
    assert "dismiss_link" in _kinds(ai_client)
    reply_2 = ai_client.post("/learned/unforget", json={"token": forgotten["undo_token"]})
    assert reply_2.status_code == 404


def test_a_correction_can_be_taken_back_by_its_id_only(ai_client, session):
    made = ai_client.post(
        "/learned/corrections", json={"kind": "dismiss_link", "subject": {"a": 1, "b": 2}}
    ).json()
    reply_3 = ai_client.delete(f"/learned/corrections/{made['id']}")
    assert reply_3.status_code == 200
    assert ai_client.get("/learned/corrections").json() == []
    reply_4 = ai_client.delete(f"/learned/corrections/{made['id']}")
    assert reply_4.status_code == 404
    #: Any other row of the event log is out of reach.

    row = manager.log_action(session, "queried", "chat", detail="x")
    session.commit()
    reply_5 = ai_client.delete(f"/learned/corrections/{row.id}")
    assert reply_5.status_code == 404


# Answering a memory proposal can be taken back and answered again (INBOX 898).


def test_an_answered_proposal_goes_back_to_being_a_question(ai_client, session):
    tools.execute_tool(session, "save_user_preference", {"preference": "Answer in Welsh"})
    pref = ai_client.get("/memory").json()["preferences"][0]
    ai_client.post(f"/memory/{pref['id']}/answer", json={"accept": True})
    session.expire_all()
    assert "Welsh" in memory.persona_with_memory(session, "P.")

    undone = ai_client.patch(f"/memory/{pref['id']}", json={"proposed": True, "active": False})
    assert undone.json()["proposed"] is True and undone.json()["active"] is False
    session.expire_all()
    assert "Welsh" not in memory.persona_with_memory(session, "P.")

    redone = ai_client.patch(f"/memory/{pref['id']}", json={"proposed": False, "active": True})
    assert redone.json()["proposed"] is False and redone.json()["active"] is True
    session.expire_all()
    assert "Welsh" in memory.persona_with_memory(session, "P.")


# Accepting or dismissing a tension can be taken back (INBOX 898).


def _pair(client, session):
    a = client.post("/entries", json={"content": "The launch is in May."}).json()["id"]
    b = client.post("/entries", json={"content": "The launch slipped to August."}).json()["id"]
    session.get(Entry, a).created_at = utcnow() - timedelta(days=30)
    session.commit()
    tensions.record_event(session, tensions.FOUND, a, b, reason="May against August", model="fake", confidence=0.7)
    session.commit()
    return a, b


def _status(client, a, b):
    rows = client.get("/entries/tensions/known", params={"status": "all"}).json()["tensions"]
    return [r["status"] for r in rows if {r["earlier_id"], r["later_id"]} == {a, b}]


def test_a_dismissal_is_reopened(client, session):
    a, b = _pair(client, session)
    client.post("/entries/tensions/dismiss", json={"earlier_id": a, "later_id": b})
    assert _status(client, a, b) == ["dismissed"]
    assert "dismiss_tension" in _kinds(client)

    reopened = client.post("/entries/tensions/reopen", json={"earlier_id": a, "later_id": b})
    assert reopened.status_code == 200, reopened.text
    assert _status(client, a, b) == ["open"]
    assert "dismiss_tension" not in _kinds(client)
    #: The dismissed list the scan reads no longer holds the pair either.
    assert client.get("/entries/tensions").json()["status"] in ("no_model", "no_embeddings", "ok", "none")


def test_an_accept_that_made_the_link_is_reopened_with_it(client, session):
    a, b = _pair(client, session)
    client.post("/entries/tensions/accept", json={"earlier_id": a, "later_id": b})
    assert session.query(EntryLink).filter_by(link_type="contradicts").count() == 1
    assert _status(client, a, b) == ["accepted"]

    reopened = client.post("/entries/tensions/reopen", json={"earlier_id": a, "later_id": b, "remove_link": True}).json()
    assert reopened["removed_link"] is True
    session.expire_all()
    assert session.query(EntryLink).filter_by(link_type="contradicts").count() == 0
    assert _status(client, a, b) == ["open"]
    assert "accept_tension" not in _kinds(client)


def test_a_link_the_person_already_had_is_left_when_remove_link_is_off(client, session):
    a, b = _pair(client, session)
    client.post(f"/entries/{a}/links", json={"target_id": b, "link_type": "contradicts"})
    client.post("/entries/tensions/accept", json={"earlier_id": a, "later_id": b})
    client.post("/entries/tensions/reopen", json={"earlier_id": a, "later_id": b})
    session.expire_all()
    assert session.query(EntryLink).filter_by(link_type="contradicts").count() == 1
