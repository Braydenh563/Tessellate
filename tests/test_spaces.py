"""Spaces (workspace partitioning): CRUD, id/icon/name validation, and the
delete-time reassignment that keeps rows from becoming invisible.
"""

from __future__ import annotations

from tessellate.core.database import Category, Entry, EntryLink, Document


def _row(session, model, **kwargs):
    obj = model(**kwargs)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def test_create_rename_delete_happy_path(client):
    created = client.post("/spaces", json={"name": "Garden Notes"}).json()
    assert created["id"] == "garden-notes"
    assert created["name"] == "Garden Notes"
    assert created["icon"] == "ph-circles-four"

    renamed = client.put(
        f"/spaces/{created['id']}", json={"name": "Garden"}
    ).json()
    assert renamed["name"] == "Garden"
    assert renamed["icon"] == "ph-circles-four"  # untouched field survives

    deleted = client.delete(f"/spaces/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["id"] == created["id"]

    ids = [s["id"] for s in client.get("/spaces").json()]
    assert created["id"] not in ids


def test_client_supplied_id_is_ignored(client):
    """A client-sent id (including a reserved sentinel) never wins, the
    server always slugifies `name` itself."""
    resp = client.post("/spaces", json={"id": "all", "name": "My Space"}).json()
    assert resp["id"] == "my-space"


def test_name_that_slugifies_to_a_reserved_word_is_deduped(client):
    # "All" itself is refused since audit 1030 Y8; "All!" still slugifies to "all".
    resp = client.post("/spaces", json={"name": "All!"}).json()
    assert resp["id"] != "all"
    assert resp["id"] not in ("all", "default")


def test_names_that_slugify_alike_get_a_numeric_suffix(client):
    # Two different names can make the same id; the id is deduped (the name
    # check below is separate: sweep 1028b W12).
    first = client.post("/spaces", json={"name": "Studio"}).json()
    second = client.post("/spaces", json={"name": "Studio!"}).json()
    assert first["id"] != second["id"]
    assert second["id"].startswith("studio-")


def test_a_space_name_already_taken_is_refused_whatever_its_case_or_spacing(client):
    made = client.post("/spaces", json={"name": "Studio"})
    assert made.status_code == 200
    for again in ("Studio", "studio ", "  STUDIO", "Studio  "):
        resp = client.post("/spaces", json={"name": again})
        assert resp.status_code == 409, again
        assert "already exists" in resp.json()["detail"]
    other = client.post("/spaces", json={"name": "Garden"}).json()
    clash = client.put(f"/spaces/{other['id']}", json={"name": "studio"})
    assert clash.status_code == 409
    same = client.put(f"/spaces/{other['id']}", json={"name": "Garden"})
    assert same.status_code == 200


def test_bad_icon_refused_on_create(client):
    resp = client.post(
        "/spaces", json={"name": "X", "icon": "evil\" onclick=\"alert(1)"}
    )
    assert resp.status_code == 400


def test_bad_icon_refused_on_update(client):
    created = client.post("/spaces", json={"name": "X"}).json()
    resp = client.put(f"/spaces/{created['id']}", json={"icon": "not-an-icon"})
    assert resp.status_code == 400


def test_bad_name_refused_empty(client):
    resp = client.post("/spaces", json={"name": "   "})
    assert resp.status_code == 400


def test_bad_name_refused_too_long(client):
    resp = client.post("/spaces", json={"name": "x" * 61})
    assert resp.status_code == 400


def test_update_only_applies_provided_fields(client):
    created = client.post(
        "/spaces", json={"name": "Keep Icon", "icon": "ph-star"}
    ).json()
    updated = client.put(
        f"/spaces/{created['id']}", json={"name": "Keep Icon Renamed"}
    ).json()
    assert updated["icon"] == "ph-star"


def test_renaming_a_missing_space_404s(client):
    resp = client.put("/spaces/does-not-exist", json={"name": "New"})
    assert resp.status_code == 404


def test_deleting_default_refused(client):
    resp = client.delete("/spaces/default")
    assert resp.status_code == 400


def test_deleting_all_refused(client):
    resp = client.delete("/spaces/all")
    assert resp.status_code == 400


def test_deleting_missing_space_404s(client):
    resp = client.delete("/spaces/does-not-exist")
    assert resp.status_code == 404


def test_a_chat_made_in_one_space_is_invisible_from_another(client):
    created = client.post("/spaces", json={"name": "Focus Room"}).json()
    space_id = created["id"]

    resp = client.post(
        "/conversations",
        json={"question": "a question asked in Focus Room", "answer": "an answer"},
        headers={"X-Workspace-ID": space_id},
    )
    assert resp.status_code == 201
    conversation_id = resp.json()["id"]

    # Visible from its own space, and from "all".
    assert conversation_id in [
        c["id"] for c in client.get("/conversations", headers={"X-Workspace-ID": space_id}).json()
    ]
    assert conversation_id in [
        c["id"] for c in client.get("/conversations", headers={"X-Workspace-ID": "all"}).json()
    ]

    # Not visible from an unrelated space, or the default one. (No header at
    # all means unfiltered, same as "all", so that is not the negative case
    # here; a *named* space that isn't this one is.)
    assert conversation_id not in [
        c["id"]
        for c in client.get("/conversations", headers={"X-Workspace-ID": "default"}).json()
    ]
    other = client.post("/spaces", json={"name": "Somewhere Else"}).json()
    assert conversation_id not in [
        c["id"]
        for c in client.get(
            "/conversations", headers={"X-Workspace-ID": other["id"]}
        ).json()
    ]


def test_a_hidden_space_leaves_all_spaces_but_still_works_when_selected(client):
    """Asked for directly: "how do I hide a specific space's notes and
    images/documents etc, all the content from the 'all spaces' space if I
    wish??" There was no way, `Space` carried only id/name/icon, and "all"
    switched the workspace filter off entirely, so it showed everything.

    The flag is a *view* filter and this pins both halves of that: the space
    drops out of the everything-view, and stays completely usable when it is
    the one selected.
    """
    private = client.post("/spaces", json={"name": "Journal"}).json()
    other = client.post("/spaces", json={"name": "Errands"}).json()

    client.post(
        "/entries",
        json={"content": "a private thought", "defer_filing": True},
        headers={"X-Workspace-ID": private["id"]},
    )
    client.post(
        "/entries",
        json={"content": "a work note", "defer_filing": True},
        headers={"X-Workspace-ID": other["id"]},
    )

    def contents(workspace):
        rows = client.get("/entries", headers={"X-Workspace-ID": workspace}).json()
        return {e["content"] for e in rows}

    # Before hiding, "all" sees both.
    everything = contents("all")
    assert "a private thought" in everything
    assert "a work note" in everything

    hidden = client.put(f"/spaces/{private['id']}", json={"hidden_from_all": True})
    assert hidden.status_code == 200
    assert hidden.json()["hidden_from_all"] is True

    # Gone from the everything-view, and nothing else went with it.
    after = contents("all")
    assert "a private thought" not in after
    assert "a work note" in after

    # Still entirely usable when you actually go there.
    assert "a private thought" in contents(private["id"])

    # And it comes back.
    client.put(f"/spaces/{private['id']}", json={"hidden_from_all": False})
    assert "a private thought" in contents("all")


def test_the_default_space_cannot_be_hidden(client):
    """It is where a deleted space's notes land, so hiding it would quietly
    empty the everything-view of anything that ever fell back to it.
    """
    refused = client.put("/spaces/default", json={"hidden_from_all": True})
    assert refused.status_code == 400


# --- delete cascades ---------------------------------------------------------
#
# These four replaced the "reassign everything to default" tests. Asked for
# directly: "make sure that if a specific space is deleted too, that all the
# content including notes files and images etc originating in that specific
# space get deleted with it as well." Reassigning was the opposite of what
# the word means: the notes did not go away, they turned up in another space.


def _gone(session, model, row_id) -> bool:
    # `session.get` on an instance the identity map still holds raises
    # ObjectDeletedError once the row is gone; a fresh query just says no.
    session.expunge_all()
    return session.query(model).filter_by(id=row_id).first() is None


def test_delete_removes_every_workspace_scoped_row_of_that_space(client, session):
    created = client.post("/spaces", json={"name": "Doomed"}).json()
    space_id = created["id"]
    category = _row(session, Category, name="doomed-cat", workspace_id=space_id)
    entry = _row(session, Entry, content="a note", workspace_id=space_id)
    other_entry = _row(session, Entry, content="another note", workspace_id=space_id)
    link = _row(
        session, EntryLink, source_entry_id=entry.id, target_entry_id=other_entry.id,
        workspace_id=space_id,
    )
    document = _row(session, Document, title="doomed doc", content="", workspace_id=space_id)
    survivor = _row(session, Entry, content="stays", workspace_id="default")
    doomed = [
        (Category, category.id), (Entry, entry.id), (Entry, other_entry.id),
        (EntryLink, link.id), (Document, document.id),
    ]
    survivor_id = survivor.id

    resp = client.delete(f"/spaces/{space_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == space_id  # response captured before the row was gone

    for model, row_id in doomed:
        assert _gone(session, model, row_id), f"{model.__name__} survived its space"
    assert not _gone(session, Entry, survivor_id), "another space's note was taken too"


def test_deleting_a_space_with_a_same_named_category_does_not_crash(client, session):
    """The old merge-by-name code existed because a blind UPDATE collided on
    `(workspace_id, name)`. A delete has no such collision; this pins that the
    default space's own category is untouched."""
    created = client.post("/spaces", json={"name": "Doomed Twin"}).json()
    space_id = created["id"]
    default_uncat = _row(session, Category, name="Uncategorised", workspace_id="default")
    doomed_uncat = _row(session, Category, name="Uncategorised", workspace_id=space_id)
    _row(session, Entry, content="filed", workspace_id=space_id, category_id=doomed_uncat.id)
    doomed_id, default_id = doomed_uncat.id, default_uncat.id

    resp = client.delete(f"/spaces/{space_id}")
    assert resp.status_code == 200, resp.text
    assert _gone(session, Category, doomed_id)
    assert not _gone(session, Category, default_id)


def test_a_foreign_note_pointing_at_a_doomed_category_keeps_the_note(client, session):
    """A note in *another* space that was filed under this space's category
    is not ours to delete, it loses the pointer, exactly as if the category
    had been deleted on its own."""
    created = client.post("/spaces", json={"name": "Doomed Unique"}).json()
    space_id = created["id"]
    category = _row(session, Category, name="doomed-only-cat", workspace_id=space_id)
    foreign = _row(session, Entry, content="elsewhere", workspace_id="default",
                   category_id=category.id)
    category_id, foreign_id = category.id, foreign.id

    resp = client.delete(f"/spaces/{space_id}")
    assert resp.status_code == 200, resp.text
    assert _gone(session, Category, category_id)
    kept = session.query(Entry).filter_by(id=foreign_id).first()
    assert kept is not None and kept.category_id is None


def test_deleting_a_space_deletes_its_chats(client, session):
    from tessellate.core.database import Conversation

    created = client.post("/spaces", json={"name": "Temporary"}).json()
    space_id = created["id"]
    conversation = _row(
        session, Conversation, title="doomed chat", messages="[]", workspace_id=space_id
    )
    deleted = client.delete(f"/spaces/{space_id}")
    assert deleted.status_code == 200
    assert _gone(session, Conversation, conversation.id)


def test_deleting_a_space_clears_every_table_that_points_at_its_notes(client, session):
    """Owner, 0.3.31: DELETE /spaces/<id> failed with "FOREIGN KEY constraint
    failed" on `DELETE FROM entries`: tables that point at notes (scores,
    derived facts) were on no purge list. References are now found from the
    schema, so a table added later cannot bring this back."""
    from tessellate.core.database import DerivedFact, NoteScore

    space = client.post("/spaces", json={"name": "Doomed"}).json()
    note = client.post(
        "/entries",
        json={"content": "a note in a doomed space", "category": "Stuff"},
        headers={"X-Workspace-ID": space["id"]},
    ).json()
    session.add(NoteScore(entry_id=note["id"], workspace_id=space["id"]) if hasattr(NoteScore, "workspace_id") else NoteScore(entry_id=note["id"]))
    session.add(DerivedFact(entry_id=note["id"], kind="fact", text="x"))
    session.commit()
    response = client.delete(f"/spaces/{space['id']}")
    assert response.status_code == 200, response.text
    session.expire_all()
    assert session.get(Entry, note["id"]) is None


def test_deleting_a_space_can_move_its_contents_to_another(client, session):
    """Owner, 0.3.31: delete a space's contents, or move them to a different
    space. A category both spaces have is merged, not duplicated."""

    source = client.post("/spaces", json={"name": "Old"}).json()["id"]
    target = client.post("/spaces", json={"name": "New"}).json()["id"]
    moved = client.post(
        "/entries", json={"content": "moves along", "category": "Shared"},
        headers={"X-Workspace-ID": source},
    ).json()
    only_here = client.post(
        "/entries", json={"content": "own category", "category": "Only old"},
        headers={"X-Workspace-ID": source},
    ).json()
    client.post(
        "/entries", json={"content": "already there", "category": "Shared"},
        headers={"X-Workspace-ID": target},
    )
    response = client.delete(f"/spaces/{source}?move_to={target}")
    assert response.status_code == 200, response.text
    session.expire_all()
    for note in (moved, only_here):
        assert session.get(Entry, note["id"]).workspace_id == target
    shared = session.query(Category).filter(Category.name == "Shared").all()
    assert len(shared) == 1 and shared[0].workspace_id == target
    assert session.get(Entry, moved["id"]).category_id == shared[0].id
    into_itself = client.delete(f"/spaces/{target}?move_to={target}")
    assert into_itself.status_code == 400


# Undo for a deleted space: it comes back with exactly its rows, or says it cannot


def test_a_space_deleted_by_moving_comes_back_with_exactly_its_rows(client, session):

    source = client.post("/spaces", json={"name": "Old", "icon": "ph-star"}).json()["id"]
    target = client.post("/spaces", json={"name": "New"}).json()["id"]
    client.put(f"/spaces/{source}", json={"hidden_from_all": True})
    moved = client.post("/entries", json={"content": "moves along", "category": "Shared"}, headers={"X-Workspace-ID": source}).json()
    own = client.post("/entries", json={"content": "own category", "category": "Only old"}, headers={"X-Workspace-ID": source}).json()
    stays = client.post("/entries", json={"content": "already there", "category": "Shared"}, headers={"X-Workspace-ID": target}).json()
    shared_before = session.get(Entry, moved["id"]).category_id

    gone = client.delete(f"/spaces/{source}?move_to={target}")
    assert gone.status_code == 200, gone.text
    restore = gone.json()["restore"]
    assert restore["space"] == {"id": source, "name": "Old", "icon": "ph-star", "hidden_from_all": True}

    back = client.post("/spaces/restore", json=restore)
    assert back.status_code == 200, back.text
    session.expire_all()
    assert session.get(Entry, moved["id"]).workspace_id == source
    assert session.get(Entry, own["id"]).workspace_id == source
    assert session.get(Entry, stays["id"]).workspace_id == target
    # The merged category is re-made in the source space, with its id, and
    # its note points at it again; the target's own "Shared" is untouched.
    assert session.get(Entry, moved["id"]).category_id == shared_before
    assert session.get(Category, shared_before).workspace_id == source
    assert session.get(Entry, stays["id"]).category_id != shared_before
    spaces = {s["id"]: s for s in client.get("/spaces").json()}
    assert spaces[source]["hidden_from_all"] is True and spaces[source]["icon"] == "ph-star"
    # And it is findable in its own space again.
    found = client.get("/entries", headers={"X-Workspace-ID": source}).json()
    assert {e["id"] for e in found} == {moved["id"], own["id"]}


def test_an_empty_space_comes_back_and_a_full_one_says_it_cannot(client):
    empty = client.post("/spaces", json={"name": "Empty"}).json()["id"]
    restore = client.delete(f"/spaces/{empty}").json()["restore"]
    assert restore is not None
    assert client.post("/spaces/restore", json=restore).status_code == 200
    assert empty in {s["id"] for s in client.get("/spaces").json()}

    full = client.post("/spaces", json={"name": "Full"}).json()["id"]
    client.post("/entries", json={"content": "gone for good"}, headers={"X-Workspace-ID": full})
    deleted = client.delete(f"/spaces/{full}")
    assert deleted.json()["restore"] is None


def test_a_space_restore_refuses_a_taken_id(client):
    sid = client.post("/spaces", json={"name": "Twice"}).json()["id"]
    restore = client.delete(f"/spaces/{sid}").json()["restore"]
    client.post("/spaces", json={"name": "Twice"})
    assert client.post("/spaces/restore", json=restore).status_code == 409
    restore["space"]["id"] = "all"
    assert client.post("/spaces/restore", json=restore).status_code == 400
