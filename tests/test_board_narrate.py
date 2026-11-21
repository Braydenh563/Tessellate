"""`POST /whiteboard/history/{event_id}/narrate` (L-whiteboard-11): what changed
between two board versions, in words. The composer writes it from the diff; a
running model rewrites it on a job thread with a timeout. Fake transport only
(the standing caveat): no real model has worded one of these.
"""

from __future__ import annotations

import time

from tessellate.core import deps


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Narrated"}).json()["id"]


def _event(client):
    return client.get("/audit?limit=1").json()[0]["id"]


def _text(client, bid, words, x=0, y=0):
    out = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": words}, "board_id": bid, "x": x, "y": y, "width": 120, "height": 40})
    assert out.status_code in (200, 201), out.text
    return out.json()


def _card(client, bid, content, x=0, y=0):
    eid = client.post("/entries", json={"content": content}).json()["id"]
    out = client.post("/whiteboard/nodes", json={"entry_id": eid, "board_id": bid, "x": x, "y": y})
    assert out.status_code in (200, 201), out.text
    return eid, out.json()


def _narrate(client, bid, event, **params):
    return client.post(f"/whiteboard/history/{event}/narrate", params={"board_id": bid, **params})


def test_without_a_model_the_summary_is_written_from_the_diff(client):
    bid = _board(client)
    _text(client, bid, "Base")
    before = _event(client)
    for title in ("Alpha", "Beta", "Gamma"):
        _card(client, bid, f"# {title}\nbody")
    got = _narrate(client, bid, before)
    assert got.status_code == 200, got.text
    assert got.json() == {"summary": "Added 3 cards: Alpha, Beta and Gamma.", "by": "composer"}


def test_moved_retitled_and_removed_items_are_told(client):
    bid = _board(client)
    keep = _text(client, bid, "Todo", x=0)
    gone = _text(client, bid, "Done", x=50)
    before = _event(client)
    client.put(f"/whiteboard/objects/{keep['id']}", json={"kind": "text", "data": {"content": "Doing"}, "board_id": bid, "x": 300, "y": 0, "width": 120, "height": 40})
    deleted = client.delete(f"/whiteboard/objects/{gone['id']}")
    assert deleted.status_code in (200, 204)
    text = _narrate(client, bid, before).json()["summary"]
    assert "Moved the text box Doing." in text
    assert "Changed the text box Todo to Doing." in text
    assert "Removed the text box Done." in text
    assert "!" not in text and chr(0x2014) not in text


def test_two_equal_versions_say_nothing_changed(client):
    bid = _board(client)
    _text(client, bid, "Only")
    now = _event(client)
    got = _narrate(client, bid, now).json()
    assert got == {"summary": "Nothing changed between these two versions.", "by": "composer"}


def test_a_running_model_rewrites_the_summary(client, monkeypatch):
    bid = _board(client)
    _text(client, bid, "Base")
    before = _event(client)
    _card(client, bid, "# Alpha\nbody")
    seen = []
    monkeypatch.setattr(type(deps.get_ollama()), "is_running", lambda self: True)
    monkeypatch.setattr(type(deps.get_ollama()), "chat", lambda self, model, messages, mode=None: seen.append(messages) or {"content": " You added the card Alpha. "})
    got = _narrate(client, bid, before).json()
    assert got == {"summary": "You added the card Alpha.", "by": "model"}
    assert "Added the card Alpha." in seen[0][1]["content"]


def test_a_slow_model_falls_back_to_the_composer_text(client, monkeypatch):
    from tessellate.api import wb_narrate

    bid = _board(client)
    _text(client, bid, "Base")
    before = _event(client)
    _card(client, bid, "# Alpha\nbody")
    monkeypatch.setattr(wb_narrate, "NARRATE_SECONDS", 0.05)
    monkeypatch.setattr(type(deps.get_ollama()), "is_running", lambda self: True)
    monkeypatch.setattr(wb_narrate, "rewrite", lambda *a: time.sleep(1) or "Too late")
    got = _narrate(client, bid, before).json()
    assert got == {"summary": "Added the card Alpha.", "by": "composer"}


def test_a_private_note_is_never_named(client, session, monkeypatch):
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    bid = _board(client)
    _text(client, bid, "Base")
    before = _event(client)
    plain, _ = _card(client, bid, "# Garden plan\nBeds.")
    secret, _ = _card(client, bid, "# Surprise party\nShh.")
    made_private = client.post(f"/entries/{secret}/privacy", json={"private": True})
    assert made_private.status_code == 200
    seen = []
    monkeypatch.setattr(type(deps.get_ollama()), "is_running", lambda self: True)
    monkeypatch.setattr(type(deps.get_ollama()), "chat", lambda self, model, messages, mode=None: seen.append(messages) or {"content": "Two cards."})
    got = _narrate(client, bid, before)
    assert got.status_code == 200, got.text
    text = got.json()["summary"]
    vault.close()
    assert "Surprise" not in text and "Surprise" not in str(seen)
    assert "Garden plan" in str(seen)
    assert plain


def test_a_missing_version_is_a_404(client):
    bid = _board(client)
    no_event = _narrate(client, bid, 99999999)
    no_board = _narrate(client, 999999, 1)
    assert no_event.status_code == 404 and no_board.status_code == 404


def test_the_history_bar_offers_it_through_the_real_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    assert 'id="wb-history-narrate"' in (root / "index.html").read_text(encoding="utf-8")
    js = (root / "js" / "whiteboard-history.js").read_text(encoding="utf-8")
    assert "/narrate?board_id=" in js and "wbHist.realApi || apiJson" in js
