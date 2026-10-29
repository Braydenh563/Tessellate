"""Every read route passes the one vault gate (INBOX 1437; audit 1029 rank 8).

A private note's text is ciphertext at rest and its words never leave the
vault while it is locked. That held for search, chat and MCP; it did not hold
for the side doors (the Graph preview, `/tags`, word counts, export, history).
Naming them one at a time is how the next one gets missed, so this walks every
GET route the app serves, with a locked private note in the notebook, and
fails on any response carrying the note's text, its tag or its title.

The allowlist is the whole decision: only a route that cannot return a note's
data, each with its reason.
"""

from __future__ import annotations

import pytest

from tests.test_every_route_is_locked import _fill, _routes

SECRET_TITLE = "ZXQSECRETTITLE"
SECRET_BODY = "ZXQSECRETBODY the combination is zxqhuntertwo"
SECRET_TAG = "zxqsecrettag"
NEEDLES = (SECRET_TITLE.lower(), "zxqsecretbody", SECRET_TAG, "zxqhuntertwo")
PASSPHRASE = "test-passphrase"

#: GET routes that cannot return note data, each with why.
CANNOT_RETURN_NOTES = {
    "/openapi.json": "the API schema, no notebook data",
    "/health": "liveness only",
    "/instance": "a hash of the data dir",
}

#: Routes that stream until closed; a test client would hang on them.
STREAMS = {
    "/events": "server-sent events, no request/response body to read",
    "/logs/stream": "the app log tail, an endless stream; its lines are the app's own, never a note",
}


@pytest.fixture()
def locked_with_a_private_note(client, session):
    from tessellate.core import vault

    vault.close()
    vault.create(session, PASSPHRASE)
    session.commit()
    made = client.post("/entries", json={"content": f"# {SECRET_TITLE}\n\n{SECRET_BODY}", "tags": [SECRET_TAG]})
    assert made.status_code in (200, 201), made.text
    entry_id = made.json()["id"]
    sealed = client.post(f"/entries/{entry_id}/privacy", json={"private": True})
    assert sealed.status_code == 200
    vault.close()
    return entry_id


def test_no_read_route_returns_a_locked_private_notes_words(client, locked_with_a_private_note):
    entry_id = locked_with_a_private_note
    leaks = []
    walked = 0
    for method, path in _routes(client.app):
        if method != "GET" or path in CANNOT_RETURN_NOTES or path in STREAMS:
            continue
        if path.startswith(("/static/", "/css/", "/js/", "/assets/", "/icons/", "/fonts/")):
            continue
        url = _fill(path).replace("/1/", f"/{entry_id}/")
        response = client.get(url, params={"q": "combination", "query": "combination", "text": "combination"})
        walked += 1
        body = response.text.lower()
        for needle in NEEDLES:
            if needle in body:
                leaks.append(f"GET {path} -> {response.status_code} carries {needle!r}")
    assert walked > 100, "the walk found too few routes to mean anything"
    assert not leaks, "a locked private note leaks through: " + "; ".join(leaks)


def test_the_allowlist_names_only_routes_that_exist(client):
    paths = {path for _method, path in _routes(client.app)}
    stale = sorted(p for p in (CANNOT_RETURN_NOTES | STREAMS) if p not in paths)
    assert not stale, f"allowlisted but no longer routed: {stale}"


def test_export_and_history_refuse_while_locked(client, locked_with_a_private_note):
    for suffix in ("export.md", "history"):
        response = client.get(f"/entries/{locked_with_a_private_note}/{suffix}")
        assert response.status_code == 409, suffix
        assert response.json()["detail"] == "Unlock first."


def test_export_and_history_work_once_unlocked(client, session, locked_with_a_private_note):
    from tessellate.core import vault

    vault.open_with(session, PASSPHRASE)
    assert vault.key() is not None
    entry_id = locked_with_a_private_note
    exported = client.get(f"/entries/{entry_id}/export.md")
    assert exported.status_code == 200 and "zxqhuntertwo" in exported.text
    history = client.get(f"/entries/{entry_id}/history")
    assert history.status_code == 200
    vault.close()


def test_the_graph_keeps_a_locked_private_node_but_drops_its_text_tags_and_count(client, locked_with_a_private_note):
    nodes = client.get("/graph").json()["nodes"]
    node = next(n for n in nodes if n["id"] == locked_with_a_private_note)
    assert node["preview"] == "Private note"
    assert node["tags"] == []
    assert node["words"] == 0


def test_tags_drop_a_locked_private_notes_tags(client, locked_with_a_private_note):
    tags = client.get("/tags").json()
    assert SECRET_TAG not in tags
