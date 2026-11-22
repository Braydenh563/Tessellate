"""A tool server token scoped to categories or tags (L-world-class-560, B52).

The owner's ask: "a token that limits which notes and tools that client sees".
A scoped token reads and changes only notes filed in one of its categories or
carrying one of its tags: search, list, count, get, the graph tools and the
resources all leave the rest out, an id outside the scope reads as missing,
and a write may not put a note outside the scope or move one out of it.
"""

from __future__ import annotations

import json

from tessellate.core import deps, mcp_clients, mcp_scope


def _rpc(method, msg_id=1, **params):
    return {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}


def _post(client, token, body):
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})


def _call(client, token, name, **arguments):
    reply = _post(client, token, _rpc("tools/call", name=name, arguments=arguments)).json()["result"]
    return reply["isError"], json.loads(reply["content"][0]["text"])


def _note(content, category, tags=()):
    from tessellate.entry import manager

    with deps.get_db().session() as session:
        entry = manager.create_entry(session, content, category_name=category, tags=list(tags))
        return entry.id


def _link(a, b):
    from tessellate.core.database import Entry
    from tessellate.entry import manager_links

    with deps.get_db().session() as session:
        manager_links.create_link(session, session.get(Entry, a), session.get(Entry, b))


def _token(client, scope, writes=False):
    reply = client.post("/mcp-clients", json={"name": "Scoped", "writes": writes, "scope": scope})
    assert reply.status_code == 200, reply.text
    return reply.json()


def _notebook():
    return {
        "work": _note("Quarterly plan for the team", "Work"),
        "trip": _note("Packing list for the coast", "Home", ["travel"]),
        "diary": _note("Plan for the weekend, not for work eyes", "Home"),
    }


def test_the_scope_is_cleaned_kept_and_shown(client):
    made = _token(client, {"categories": [" Work ", "work", ""], "tags": ["#Travel", "travel"]})
    assert made["client"]["scope"] == {"categories": ["Work"], "tags": ["Travel"]}
    listed = client.get("/mcp-clients").json()["clients"][0]
    assert listed["scope"] == {"categories": ["Work"], "tags": ["Travel"]}
    assert mcp_scope.describe(listed["scope"]) == "notes in Work, or tagged Travel"
    whole = _token(client, {})
    assert whole["client"]["scope"] == {"categories": [], "tags": []}


def test_list_count_and_search_leave_out_notes_outside_the_scope(client):
    notes = _notebook()
    token = _token(client, {"categories": ["Work"], "tags": ["travel"]})["token"]
    _err, listed = _call(client, token, "list_notes", limit=25)
    assert {n["id"] for n in listed["notes"]} == {notes["work"], notes["trip"]}
    assert listed["total_matching"] == 2
    _err, counted = _call(client, token, "count_notes")
    assert counted == {**counted, "total": 2, "by_category": {"Work": 1, "Home": 1}}
    _err, found = _call(client, token, "search_notes", query="plan")
    ids = {n["id"] for n in found["notes"]}
    assert notes["work"] in ids and notes["diary"] not in ids
    whole = _token(client, {})["token"]
    _err, found = _call(client, whole, "search_notes", query="plan")
    assert notes["diary"] in {n["id"] for n in found["notes"]}, "the unscoped search does find it"


def test_get_and_resources_refuse_a_note_outside_the_scope_as_missing(client):
    notes = _notebook()
    token = _token(client, {"categories": ["Work"]})["token"]
    err, got = _call(client, token, "get_note", note_id=notes["diary"])
    _err, missing = _call(client, token, "get_note", note_id=9999)
    assert err is True and got["error"] == missing["error"].replace("9999", str(notes["diary"]))
    err, got = _call(client, token, "get_note", note_id=notes["work"])
    assert err is False and got["id"] == notes["work"]
    uris = [r["uri"] for r in _post(client, token, _rpc("resources/list")).json()["result"]["resources"]]
    assert uris == [f"memorymap://note/{notes['work']}"]
    read = _post(client, token, _rpc("resources/read", uri=f"memorymap://note/{notes['diary']}")).json()
    assert "error" in read


def test_the_graph_tools_stay_inside_the_scope(client):
    notes = _notebook()
    _link(notes["work"], notes["diary"])
    _link(notes["work"], notes["trip"])
    token = _token(client, {"categories": ["Work"], "tags": ["travel"]})["token"]
    _err, near = _call(client, token, "related_notes", note_id=notes["work"])
    assert {n["id"] for n in near["related"]} == {notes["trip"]}
    _err, got = _call(client, token, "get_note", note_id=notes["work"])
    assert notes["diary"] not in got["links"]
    err, _path = _call(client, token, "path_between", note_id=notes["work"], other_note_id=notes["diary"])
    assert err is True
    err, path = _call(client, token, "path_between", note_id=notes["trip"], other_note_id=notes["work"])
    assert err is False and {step["id"] for step in path["path"]} <= {notes["work"], notes["trip"]}


def test_a_scoped_token_is_offered_only_the_tools_that_can_be_scoped(client):
    token = _token(client, {"tags": ["travel"]}, writes=True)["token"]
    names = {t["name"] for t in _post(client, token, _rpc("tools/list")).json()["result"]["tools"]}
    assert {"search_notes", "get_note", "list_notes", "related_notes", "create_note", "tag_note"} <= names
    assert not names & {"notebook_overview", "list_documents", "read_whiteboard", "rename_tag", "list_reminders", "web_search"}
    assert names <= mcp_scope.SCOPED_TOOLS
    refused = _post(client, token, _rpc("tools/call", name="notebook_overview", arguments={})).json()["result"]
    assert refused["isError"] is True
    init = _post(client, token, _rpc("initialize", protocolVersion="2025-06-18")).json()["result"]
    assert "tagged travel" in init["instructions"]


def test_writes_may_not_leave_the_scope(client):
    notes = _notebook()
    token = _token(client, {"categories": ["Work"], "tags": ["travel"]}, writes=True)["token"]
    err, refused = _call(client, token, "create_note", content="Somewhere else", category="Home")
    assert err is True and "notes in Work, or tagged travel" in refused["error"]
    err, made = _call(client, token, "create_note", content="Inside", category="Home", tags=["travel"])
    assert err is False
    err, _ = _call(client, token, "create_note", content="Filed at work", category="work")
    assert err is False
    err, _ = _call(client, token, "edit_note", note_id=notes["work"], category="Home")
    assert err is True, "an edit may not move a note out of the scope"
    err, _ = _call(client, token, "tag_note", note_id=notes["trip"], remove=["travel"])
    assert err is True, "nor may a tag change"
    err, _ = _call(client, token, "edit_note", note_id=notes["diary"], content="changed")
    assert err is True
    err, _ = _call(client, token, "tag_note", note_ids=[notes["work"], notes["diary"]], add=["x"])
    assert err is True
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    with deps.get_db().session() as session:
        assert "x" not in manager.entry_tags(session.get(Entry, notes["work"])), "a refused batch changes nothing"
        assert session.get(Entry, notes["diary"]).content.startswith("Plan for the weekend")
    err, _ = _call(client, token, "link_notes", note_id=notes["work"], other_note_id=notes["diary"])
    assert err is True
    err, _ = _call(client, token, "tag_note", note_id=notes["work"], add=["travel"])
    assert err is False


def test_an_unscoped_token_still_sees_the_whole_notebook(client):
    notes = _notebook()
    token = _token(client, {})["token"]
    _err, listed = _call(client, token, "list_notes", limit=25)
    assert set(notes.values()) <= {n["id"] for n in listed["notes"]}
    assert mcp_scope.current.get() is None, "the scope never outlives its request"


def test_the_scope_of_a_row_is_read_from_the_stored_preference(client):
    _token(client, {"categories": ["Work"]})
    rows = deps.get_config().get_preference(mcp_clients.PREF, [])
    assert rows[0]["scope"] == {"categories": ["Work"], "tags": []}
