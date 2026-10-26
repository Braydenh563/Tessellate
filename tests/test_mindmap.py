"""Mindmaps: the map object, its tree, and the rule that a map contains its
own contents (MINDMAP_PLAN.md Phase 1).

The containment tests come first in this file because they were written
first, before any of the code they cover, the plan says so by name ("Write
the test first; this is the rule most likely to be got wrong"), and the rule
itself is the one place where getting it wrong destroys somebody's notes
rather than drawing a wrong picture:

> any and all text boxes and things that are in the map stay bundled within
> the map

A `topic` exists only in the map, so it goes with the map. A `note` /
`document` / `file` node is a *pointer at something in the library*, so the
pointer goes and the thing it pointed at must still be there afterwards.
Those are opposite outcomes for two rows in the same table, which is exactly
why a test says which is which.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tessellate.api.routes_whiteboard import MAP_BRANCH_PALETTE
from tessellate.core.database import Entry, WhiteboardObject


def _map(client, name="Thesis map", layout="tree-right"):
    board = client.post(
        "/whiteboard/boards", json={"name": name, "type": "map", "layout": layout}
    )
    assert board.status_code == 201, board.text
    return board.json()


def _node(client, board_id, *, parent_id=None, text="", kind="topic", ref_id=None):
    body = {"kind": kind, "parent_id": parent_id, "text": text}
    if ref_id is not None:
        body["ref_id"] = ref_id
    created = client.post(f"/whiteboard/boards/{board_id}/nodes", json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _purge(client, entry_id):
    """The bin, then the bin emptied, the only path to a permanent delete,
    and the one the Library's own Delete action starts down."""
    binned = client.delete(f"/entries/{entry_id}")
    assert binned.status_code == 200, binned.text
    purged = client.delete(f"/entries/{entry_id}/purge")
    assert purged.status_code == 200, purged.text


# --- containment ------------------------------------------------------------


def test_deleting_a_map_takes_its_topics_and_leaves_the_notes_it_referenced(
    client, session
):
    """The rule, both halves of it, in one test.

    Without this the default behaviour is actively wrong in two different
    directions at once: purging a board detaches everything on it to the
    default scratch board (`manager._hard_delete`), so a deleted map's topics
    would reappear as loose text on the one board nobody deletes, and any
    attempt to fix that by simply deleting everything on the board would take
    the referenced *notes* with it, which is data loss.
    """
    note = client.post("/entries", json={"content": "Chapter three"}).json()
    board = _map(client)
    topic = _node(client, board["id"], text="Root")
    child = _node(client, board["id"], parent_id=topic["id"], text="Branch")
    reference = _node(
        client, board["id"], parent_id=topic["id"], kind="note", ref_id=note["id"]
    )

    _purge(client, board["id"])

    for object_id in (topic["id"], child["id"], reference["id"]):
        assert session.get(WhiteboardObject, object_id) is None, (
            f"object {object_id} outlived the map it lived in"
        )
    survivor = session.get(Entry, note["id"])
    assert survivor is not None and not survivor.is_deleted, (
        "deleting a map deleted a note that only happened to be referenced by it"
    )


def test_deleting_an_ordinary_board_still_detaches_its_objects(client, session):
    """The behaviour containment must not break.

    A plain whiteboard's text boxes and images are *not* bundled: purging the
    board note detaches them to the default board rather than destroying
    them, deliberately (see `_hard_delete`'s own comment: "delete this one
    note" must not silently wipe a whiteboard). Containment is a rule about
    maps, and this asserts it stayed one.
    """
    board = client.post("/whiteboard/boards", json={"name": "Scratch"}).json()
    text = client.post(
        "/whiteboard/objects",
        json={"kind": "text", "board_id": board["id"], "data": {"content": "hello"}},
    ).json()

    _purge(client, board["id"])

    survivor = session.get(WhiteboardObject, text["id"])
    assert survivor is not None, "an ordinary board's text box was destroyed with it"
    assert survivor.board_id is None


def test_deleting_a_topic_deletes_its_subtree_and_hands_it_back(client):
    """Coggle's choice, made deliberately: a deleted branch takes its
    children with it rather than re-homing them on the grandparent.

    Re-parenting reads as tidier and is worse: a branch you meant to remove
    reappears as loose children under a node that never had them, and there
    is no single action that undoes it. Deleting the subtree is one action, 
    so the response carries the whole subtree back, which is what lets the
    frontend offer a real undo instead of a warning dialog.
    """
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    branch = _node(client, board["id"], parent_id=root["id"], text="Branch")
    leaf = _node(client, board["id"], parent_id=branch["id"], text="Leaf")
    keep = _node(client, board["id"], parent_id=root["id"], text="Sibling")

    gone = client.delete(f"/whiteboard/objects/{branch['id']}")
    assert gone.status_code == 200, gone.text
    deleted = gone.json()["deleted"]
    assert {row["id"] for row in deleted} == {branch["id"], leaf["id"]}
    # Enough to rebuild the branch, not just to count it.
    assert {row["parent_id"] for row in deleted} == {root["id"], branch["id"]}
    assert {row["data"]["content"] for row in deleted} == {"Branch", "Leaf"}

    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert [n["id"] for n in tree["roots"]] == [root["id"]]
    assert [n["id"] for n in tree["roots"][0]["children"]] == [keep["id"]]


def test_deleting_a_reference_node_leaves_the_note_alone(client, session):
    """The single-node case of the same rule, a map node is a pointer, and
    removing a pointer is not removing the thing."""
    note = client.post("/entries", json={"content": "Keep me"}).json()
    board = _map(client)
    reference = _node(client, board["id"], kind="note", ref_id=note["id"])

    removed = client.delete(f"/whiteboard/objects/{reference['id']}")
    assert removed.status_code == 200, removed.text

    survivor = session.get(Entry, note["id"])
    assert survivor is not None and not survivor.is_deleted


# --- the map object ---------------------------------------------------------


def test_a_board_is_a_free_whiteboard_unless_it_says_otherwise(client):
    """Every board that existed before this feature has NULL settings, and
    NULL has to read as "an ordinary free-layout whiteboard" rather than as
    anything needing a backfill."""
    board = client.post("/whiteboard/boards", json={"name": "Plain"}).json()
    assert (board["type"], board["layout"]) == ("board", "free")

    listed = {b["id"]: b for b in client.get("/whiteboard/boards").json()}
    assert listed[board["id"]]["type"] == "board"
    # The default scratch board has no note behind it to store settings on.
    assert listed[None]["type"] == "board"


def test_type_and_layout_survive_a_round_trip_through_the_list(client):
    board = _map(client, name="Radial", layout="radial")
    assert (board["type"], board["layout"]) == ("map", "radial")

    listed = {b["id"]: b for b in client.get("/whiteboard/boards").json()}
    assert listed[board["id"]]["layout"] == "radial"


def test_the_two_layouts_this_plan_promised_are_storable(client):
    """MINDMAP_PLAN 13e. Section 12.0's decision list named eight layouts and
    section 13.4 measured four: tree-left and both-sides were missing, and
    both-sides is the one Coggle is known for. A layout the API refuses is a
    layout the picker cannot offer, so this is the half of that work that has
    to be true before any of it is drawn."""
    for layout in ("tree-left", "tree-both"):
        board = _map(client, name=f"Map {layout}", layout=layout)
        assert (board["type"], board["layout"]) == ("map", layout)
        listed = {b["id"]: b for b in client.get("/whiteboard/boards").json()}
        assert listed[board["id"]]["layout"] == layout


def test_the_layout_can_be_changed_without_renaming_the_board(client):
    """`PUT /whiteboard/boards/{id}` was rename-only, and a title was
    required. Switching a map's layout must not force the caller to resend
    the title it isn't changing: that is how a rename race loses an edit."""
    board = _map(client, name="Keep this name")
    updated = client.put(
        f"/whiteboard/boards/{board['id']}", json={"layout": "tree-down"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Keep this name"
    assert updated.json()["layout"] == "tree-down"


def test_an_unknown_type_or_layout_is_refused_rather_than_stored(client):
    assert (
        client.post("/whiteboard/boards", json={"name": "x", "type": "graph"}).status_code
        == 422
    )
    assert (
        client.post(
            "/whiteboard/boards", json={"name": "x", "layout": "spiral"}
        ).status_code
        == 422
    )


def test_the_maps_filter_returns_maps_and_nothing_else(client):
    """The Library's Maps chip. A filter that silently returns everything is
    worse than no filter, it reads as "you have no boards" only once the
    user has looked at every row."""
    plain = client.post("/whiteboard/boards", json={"name": "Whiteboard"}).json()
    mapped = _map(client, name="Mindmap")

    maps = client.get("/whiteboard/boards?type=map").json()
    assert [b["id"] for b in maps] == [mapped["id"]]

    boards = client.get("/whiteboard/boards?type=board").json()
    ids = [b["id"] for b in boards]
    assert plain["id"] in ids and mapped["id"] not in ids
    # The default scratch board is a board, so it belongs in one list and not
    # the other: it dropped out of both in the first draft of this filter.
    assert None in ids


# --- the tree ---------------------------------------------------------------


def test_the_tree_nests_children_under_their_parents_with_cross_links(client):
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    left = _node(client, board["id"], parent_id=root["id"], text="Left")
    right = _node(client, board["id"], parent_id=root["id"], text="Right")

    # A cross-link is a link sketch, exactly as it already is between two
    # cards: there is no second kind of edge and no second endpoint for one.
    linked = client.post(
        "/whiteboard/sketches",
        json={
            "board_id": board["id"],
            "data": json.dumps(
                {
                    "type": "link-straight",
                    "sourceId": left["id"],
                    "sourceKind": "object",
                    "targetId": right["id"],
                    "targetKind": "object",
                    "label": "compare",
                }
            ),
        },
    )
    assert linked.status_code == 200, linked.text

    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert tree["type"] == "map"
    assert [n["id"] for n in tree["roots"]] == [root["id"]]
    kids = tree["roots"][0]["children"]
    assert [n["text"] for n in kids] == ["Left", "Right"]
    assert kids[0]["kind"] == "topic"
    assert tree["cross_links"] == [
        {"from_id": left["id"], "to_id": right["id"], "label": "compare"}
    ]


def test_a_node_whose_parent_is_gone_reads_as_a_root(client, session):
    """A dangling `parent_id` must not make a branch invisible.

    `parent_id` is a plain integer, not a foreign key (see the column's own
    comment), so nothing at the database level stops one going stale. A tree
    builder that only walks down from `parent_id IS NULL` silently loses
    every node under a broken pointer, the board still holds them, the map
    just stops showing them, which is the worst way to lose something.
    """
    board = _map(client)
    orphan = _node(client, board["id"], text="Orphan")
    row = session.get(WhiteboardObject, orphan["id"])
    row.parent_id = 999_999
    session.commit()

    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert [n["id"] for n in tree["roots"]] == [orphan["id"]]


def test_a_node_cannot_be_moved_under_its_own_descendant(client):
    """The cycle check. Without it the tree walk never terminates, and the
    board is unreadable from then on with no way back through the UI that
    made it."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    child = _node(client, board["id"], parent_id=root["id"], text="Child")
    grandchild = _node(client, board["id"], parent_id=child["id"], text="Grandchild")

    refused = client.put(
        f"/whiteboard/boards/{board['id']}/nodes/{root['id']}/move",
        json={"parent_id": grandchild["id"]},
    )
    assert refused.status_code == 422, refused.text
    assert "descendant" in refused.json()["detail"].lower()

    # And the obvious degenerate case of the same thing.
    itself = client.put(
        f"/whiteboard/boards/{board['id']}/nodes/{root['id']}/move",
        json={"parent_id": root["id"]},
    )
    assert itself.status_code == 422


def test_moving_a_node_to_a_root_and_back_under_a_parent(client):
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    child = _node(client, board["id"], parent_id=root["id"], text="Child")

    promoted = client.put(
        f"/whiteboard/boards/{board['id']}/nodes/{child['id']}/move",
        json={"parent_id": None},
    )
    assert promoted.status_code == 200, promoted.text
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert {n["id"] for n in tree["roots"]} == {root["id"], child["id"]}

    client.put(
        f"/whiteboard/boards/{board['id']}/nodes/{child['id']}/move",
        json={"parent_id": root["id"]},
    )
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert [n["id"] for n in tree["roots"]] == [root["id"]]


def test_a_node_cannot_be_parented_onto_another_boards_node(client):
    """`board_id` scoping, the same rule the rest of this file already
    learned: a write has to be scoped to the board it claims."""
    here = _map(client, name="Here")
    there = _map(client, name="There")
    mine = _node(client, here["id"], text="Mine")
    theirs = _node(client, there["id"], text="Theirs")

    refused = client.put(
        f"/whiteboard/boards/{here['id']}/nodes/{mine['id']}/move",
        json={"parent_id": theirs["id"]},
    )
    assert refused.status_code == 404, refused.text


def test_a_reference_node_needs_something_real_to_point_at(client):
    board = _map(client)
    refused = client.post(
        f"/whiteboard/boards/{board['id']}/nodes",
        json={"kind": "note", "ref_id": 9999},
    )
    assert refused.status_code == 404
    assert (
        client.post(
            f"/whiteboard/boards/{board['id']}/nodes", json={"kind": "note"}
        ).status_code
        == 422
    )


def test_collapsed_and_pinned_are_stored_and_read_back(client):
    """Coggle's two: tidy on demand, and a branch you dragged stays where you
    put it. Both are per-node state on a node that already has a JSON blob,
    so neither is a column."""
    board = _map(client)
    node = _node(client, board["id"], text="Root")
    updated = client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": "topic",
            "board_id": board["id"],
            "data": {"content": "Root", "collapsed": True, "pinned": True},
        },
    )
    assert updated.status_code == 200, updated.text

    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert tree["roots"][0]["collapsed"] is True
    assert tree["roots"][0]["pinned"] is True


# --- preview ----------------------------------------------------------------


def test_a_maps_thumbnail_carries_its_edges(client):
    """The Library card. A map previewed as scattered dots reads as a board
    with no structure at all, which is precisely the thing a map has and a
    board does not."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], text="Child")

    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == board["id"])
    assert len(row["preview_items"]) == 2
    assert len(row["preview_edges"]) == 1
    edge = row["preview_edges"][0]
    assert {"x1", "y1", "x2", "y2"} <= set(edge)
    assert all(0.0 <= edge[axis] <= 1.0 for axis in ("x1", "y1", "x2", "y2"))
    # The edge carries the branch it belongs to, so the thumbnail is the same
    # picture as the canvas rather than a grey diagram of one.
    assert edge["color"] in MAP_BRANCH_PALETTE


def test_an_ordinary_board_has_no_edges_to_draw(client):
    board = client.post("/whiteboard/boards", json={"name": "Plain"}).json()
    client.post(
        "/whiteboard/objects",
        json={"kind": "text", "board_id": board["id"], "data": {"content": "hi"}},
    )
    row = next(b for b in client.get("/whiteboard/boards").json() if b["id"] == board["id"])
    assert row["preview_edges"] == []


# --- duplicate --------------------------------------------------------------


def test_duplicating_a_map_keeps_its_shape(client):
    """`duplicate_board` copied objects row by row, which for a map would
    copy every node's `parent_id` verbatim: pointing the copy's whole tree
    back at the original's rows. The copy has to be re-wired to itself."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], text="Child")

    copy = client.post(f"/whiteboard/boards/{board['id']}/duplicate").json()
    assert copy["type"] == "map"

    tree = client.get(f"/whiteboard/boards/{copy['id']}/tree").json()
    assert [n["text"] for n in tree["roots"]] == ["Root"]
    assert [n["text"] for n in tree["roots"][0]["children"]] == ["Child"]
    copied_ids = {n["id"] for n in tree["roots"]} | {
        n["id"] for n in tree["roots"][0]["children"]
    }
    assert not copied_ids & {root["id"]}


# --- what the notebook knows about a node (section 5 item 19) ---------------


def test_a_note_node_carries_its_category_and_age(client):
    """The perspectives colour a map by the notebook's own metadata, which is
    the thing a general mindmapper cannot do. It has to be resolved here: a
    copy on the client goes stale the moment a note is refiled, and the client
    has no way to know it did."""
    note = client.post("/entries", json={"content": "# Filed thing\n\nbody"}).json()
    board = _map(client)
    _node(client, board["id"], kind="note", ref_id=note["id"])

    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert node["ref_category"]
    assert node["ref_updated_at"]


def test_a_topic_carries_no_facets_at_all(client):
    """A topic stands for nothing, so it has nothing to be coloured by, and
    the payload says so by leaving the keys out rather than by sending nulls
    for every node on the board."""
    board = _map(client)
    _node(client, board["id"], text="Just a topic")

    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert "ref_category" not in node
    assert "ref_updated_at" not in node


def test_a_private_notes_filing_stays_behind_the_boundary(client, session):
    """Its title already does (`_reference_label` renders "Private note"), and
    its category and its edit time are facts about it too."""
    from tessellate.core import vault

    vault.close()
    vault.create(session, "test-passphrase")
    session.commit()
    note = client.post("/entries", json={"content": "# Secret\n\nbody"}).json()
    board = _map(client)
    _node(client, board["id"], kind="note", ref_id=note["id"])
    assert client.post(f"/entries/{note['id']}/privacy", json={"private": True}).status_code == 200

    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert node["text"] == "Private note"
    assert "ref_category" not in node
    vault.close()


# --- export and import ------------------------------------------------------


OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Reading list</title></head>
  <body>
    <outline text="Fiction">
      <outline text="Le Guin"/>
      <outline text="Borges"/>
    </outline>
    <outline text="History"/>
  </body>
</opml>"""


def _structure(tree_nodes):
    return [
        {"text": node["text"], "children": _structure(node["children"])}
        for node in tree_nodes
    ]


def test_opml_imports_and_exports_to_the_same_structure(client):
    """The round trip the plan asks for by name, and the reason the export
    formats are worth having at all: a map that cannot leave is a lock-in,
    and OPML is what every other mindmapper reads."""
    imported = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": OPML}
    )
    assert imported.status_code == 201, imported.text
    board = imported.json()
    assert board["type"] == "map"
    assert board["title"] == "Reading list"

    first = _structure(client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"])
    assert [n["text"] for n in first] == ["Fiction", "History"]
    assert [n["text"] for n in first[0]["children"]] == ["Le Guin", "Borges"]

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml")
    assert exported.status_code == 200, exported.text

    again = client.post(
        "/whiteboard/boards/import",
        json={"format": "opml", "content": exported.text},
    ).json()
    second = _structure(client.get(f"/whiteboard/boards/{again['id']}/tree").json()["roots"])
    assert second == first


FREEMIND = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1">
  <node TEXT="Thesis">
    <node TEXT="Method">
      <node TEXT="Interviews"/>
    </node>
    <node TEXT="Results"/>
  </node>
</map>"""


def test_freemind_imports_its_single_root_as_the_central_topic(client):
    """**Reversed 2026-10-05** (audit FEAT-01, features.md 9.5; the owner's
    newer words win). A `.mm` file's single root node is the map's central
    topic, the way FreeMind, Freeplane and XMind draw it: reading it as the
    board's title instead left every imported map as loose trunks with its
    centre gone. The title still comes from the root's text when the file
    names nothing else."""
    imported = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": FREEMIND}
    )
    assert imported.status_code == 201, imported.text
    board = imported.json()
    assert board["type"] == "map"
    assert board["title"] == "Thesis"

    roots = _structure(client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"])
    assert roots == [
        {
            "text": "Thesis",
            "children": [
                {"text": "Method", "children": [{"text": "Interviews", "children": []}]},
                {"text": "Results", "children": []},
            ],
        }
    ]


def _big_map(client, name="Hundred"):
    """A map made in the app, one root, ten branches of nine: 101 topics,
    the `kb100.js` shape the audit measured the round trips at."""
    board = _map(client, name=name)
    root = _node(client, board["id"], text="Centre")
    for b in range(10):
        branch = _node(client, board["id"], parent_id=root["id"], text=f"Branch {b}")
        for leaf in range(9):
            _node(client, board["id"], parent_id=branch["id"], text=f"Leaf {b}.{leaf}")
    return board


@pytest.mark.parametrize("fmt", ["freemind", "opml", "markdown"])
def test_a_101_topic_map_made_here_round_trips_losslessly(client, fmt):
    """FEAT-01's own test: start from a map made in the app, not from an
    import that had already dropped its root, so the export and the import
    are each tested against the other. All 101 topics, every parent edge,
    the central topic and the map's name come back."""
    board = _big_map(client, name="Hundred topics")
    first = _structure(client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"])
    assert len(first) == 1 and first[0]["text"] == "Centre"

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}")
    assert exported.status_code == 200, exported.text
    back = client.post(
        "/whiteboard/boards/import", json={"format": fmt, "content": exported.text}
    )
    assert back.status_code == 201, back.text
    assert back.json()["title"] == "Hundred topics"
    assert back.json()["object_count"] == 101
    second = _structure(client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"])
    assert second == first


@pytest.mark.parametrize("fmt", ["freemind", "opml", "markdown"])
def test_an_imported_map_opens_in_the_tree_right_layout(client, fmt):
    """Audit FEAT-05: an import landed in the Free layout, so the first Tab
    piled new topics on top of old ones (240 overlapping pairs over 101
    topics, measured). A map made here starts in tree-right, and so does
    one brought in."""
    board = _big_map(client, name="Laid out")
    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
    back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": exported})
    assert back.status_code == 201, back.text
    assert back.json()["layout"] == "tree-right"
    listed = {b["id"]: b for b in client.get("/whiteboard/boards").json()}
    assert listed[back.json()["id"]]["layout"] == "tree-right"


def test_freemind_round_trips_through_the_export(client):
    """The point of the format: a map made here opens in FreeMind, and a map
    made there opens here, without either end losing the tree."""
    first_id = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": FREEMIND}
    ).json()["id"]
    first = _structure(client.get(f"/whiteboard/boards/{first_id}/tree").json()["roots"])

    exported = client.get(f"/whiteboard/boards/{first_id}/export?format=freemind")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-disposition"].endswith('.mm"')
    assert exported.text.lstrip().startswith("<?xml")
    assert "<map version=" in exported.text

    again = client.post(
        "/whiteboard/boards/import",
        json={"format": "freemind", "content": exported.text},
    ).json()
    assert _structure(client.get(f"/whiteboard/boards/{again['id']}/tree").json()["roots"]) == first


def test_a_multi_root_map_exports_under_one_freemind_root(client):
    """`.mm` has room for exactly one root, and a map here can have several.
    The alternative to naming a trunk after the map is a file FreeMind
    refuses to open, or one that quietly drops every root but the first."""
    board = _map(client, name="Two trunks")
    _node(client, board["id"], text="Alpha")
    _node(client, board["id"], text="Beta")

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    assert exported.count("<node") == 3
    back = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": exported}
    ).json()
    assert back["title"] == "Two trunks"
    roots = _structure(client.get(f"/whiteboard/boards/{back['id']}/tree").json()["roots"])
    assert [node["text"] for node in roots] == ["Alpha", "Beta"]


def test_a_freemind_import_with_a_doctype_is_refused(client):
    """The second XML door. It shares `_parse_xml_document` with OPML for
    exactly this reason: a security check copied per format is a check that
    is one day only in one of them."""
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        '<map version="1.0.1"><node TEXT="&lol;"/></map>'
    )
    refused = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": bomb}
    )
    assert refused.status_code == 422
    assert "FreeMind" in refused.json()["detail"]


def test_an_opml_file_sent_as_freemind_imports_as_nothing_rather_than_wrongly(client):
    """OPML's nodes are `<outline>` and FreeMind's are `<node>`: the parser
    finds nothing rather than inventing a tree. Written down because the
    client picks the format from the file's extension, and `.mm` had to be
    tested before `.xml` for that reason."""
    empty = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": OPML}
    ).json()
    assert empty["object_count"] == 0


def test_a_hand_resized_topic_keeps_its_size(client):
    """MINDMAP_PLAN.md item 177, "resize a topic as a card resizes on the
    whiteboard". Three things have to survive the PUT together or the feature
    is a grip that appears to do nothing: the two columns, and the flag that
    says a person chose them rather than the creation defaults.

    The flag is the part that was easy to lose. `WhiteboardObjectData` drops
    any field it does not name, silently, which is exactly how an earlier map
    toggle looked like a frontend bug: the drag worked, the PUT returned 200,
    and the value came back missing."""
    board = _map(client, name="Resized")
    node = _node(client, board["id"], text="Wide topic")
    saved = client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], "sized": True},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
            "width": 340,
            "height": 128,
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["width"], body["height"]) == (340, 128)
    assert body["data"]["sized"] is True

    # And again from the board state, not only from the response to the write:
    # the round trip that matters is the one a reload makes.
    stored = client.get(f"/whiteboard/?board_id={board['id']}").json()["objects"]
    mine = next(o for o in stored if o["id"] == node["id"])
    assert (mine["width"], mine["height"]) == (340, 128)
    assert json.loads(json.dumps(mine["data"]))["sized"] is True


#: Everything the node edit strip and the two radials can write on a node
#: (MINDMAP_PLAN.md §12.1 items 2 to 4), one value each, so a round-trip test
#: fails if any single one of them is dropped on the way out or on the way
#: back. Written once and used by both format tests: the two exports lost the
#: same seven fields in the same way, which is what a shared fixture says.
MAP_STYLE = {
    "bold": True,
    "italic": True,
    "font_size": 22,
    "align": "center",
    "shape": "pill",
    "core": True,
    "spine": "dashed",
    "fill": "branch",
    "icon": "lightbulb",
    "link": "https://example.org/paper",
    "edge_label": "because",
    "edge_style": "elbow",
    "edge_dashed": True,
    "edge_width": "thick",
    "edge_arrow": "off",
    "edge_bend": 0.32,
    "edge_slide": -0.18,
    "image": "/media/0123456789abcdef0123456789abcdef.png",
    "color": "#4f46e5",
}


def _styled_map(client, name):
    """A two-node map whose child wears every style field there is."""
    board = _map(client, name=name)
    root = _node(client, board["id"], text="Trunk")
    child = _node(client, board["id"], parent_id=root["id"], text="Branch")
    saved = client.put(
        f"/whiteboard/objects/{child['id']}",
        json={
            "kind": child["kind"],
            "board_id": board["id"],
            "data": {**child["data"], **MAP_STYLE},
            "x": child["x"],
            "y": child["y"],
            "z": child["z"],
        },
    )
    assert saved.status_code == 200, saved.text
    return board


def _styled_child(client, board_id):
    """The styled node, wherever the tree puts it. A `.mm` file's one root is
    its title, so a map exported and imported again comes back with its trunk
    as the board's name and the styled node at the top level: the round trip
    being tested is the style's, not the depth's."""

    def find(nodes):
        for node in nodes:
            if node["text"] == "Branch":
                return node
            found = find(node["children"])
            if found is not None:
                return found
        return None

    found = find(client.get(f"/whiteboard/boards/{board_id}/tree").json()["roots"])
    assert found is not None
    return found


def test_the_tree_hands_back_what_the_strip_and_the_rings_wrote(client):
    """The style fields were readable only by fetching the raw objects, so
    every other reader of a map (the exports, the agent, a thumbnail) could
    not see them at all. They are on the node in the tree now."""
    board = _styled_map(client, "Styled")
    child = _styled_child(client, board["id"])
    assert child["color"] == "#4f46e5"
    assert child["style"] == {
        key: value for key, value in MAP_STYLE.items() if key != "color"
    }


def test_freemind_carries_a_styled_node_out_and_back(client):
    """§12.0: "a feature that cannot round-trip is not built". The strip and
    the two rings landed with none of their fields in either XML export,
    which made the one path built for taking a map somewhere else a silent
    loss of everything a person had styled."""
    board = _styled_map(client, "Styled")
    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text

    # The four FreeMind has words of its own for, in its own words.
    assert 'LINK="https://example.org/paper"' in exported
    assert 'BOLD="true"' in exported and 'ITALIC="true"' in exported
    assert 'SIZE="22"' in exported
    assert 'STYLE="bubble"' in exported and '_shape="pill"' in exported
    assert 'STYLE="horizontal"' in exported and 'COLOR="#4f46e5"' in exported
    # And the four it does not, as private attributes rather than as invented
    # FreeMind that another reader would choke on.
    assert '_core="true"' in exported
    assert '_spine="dashed"' in exported
    assert '_edge_width="thick"' in exported and 'WIDTH="4"' in exported
    assert '_icon="lightbulb"' in exported
    assert '_edge_label="because"' in exported
    assert '_edge_dashed="true"' in exported
    assert '_align="center"' in exported

    back = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": exported}
    ).json()
    child = _styled_child(client, back["id"])
    assert child["color"] == "#4f46e5"
    assert child["style"] == {
        key: value for key, value in MAP_STYLE.items() if key != "color"
    }


def test_opml_carries_a_styled_node_out_and_back(client):
    """OPML 2.0 has one attribute that fits (`url`) and no word for the rest,
    so the rest ride as private attributes: the same device `_kind` and
    `_ref` have used here since the export was written."""
    board = _styled_map(client, "Styled")
    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text

    assert 'url="https://example.org/paper"' in exported
    # Not `type="link"`: that would say the outline *is* a link, and a reader
    # honouring it drops the children underneath.
    assert 'type="link"' not in exported
    assert '_bold="true"' in exported and '_edge_style="elbow"' in exported
    assert '_core="true"' in exported
    assert '_color="#4f46e5"' in exported

    back = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": exported}
    ).json()
    child = _styled_child(client, back["id"])
    assert child["color"] == "#4f46e5"
    assert child["style"] == {
        key: value for key, value in MAP_STYLE.items() if key != "color"
    }


def test_a_core_idea_can_be_an_ellipse(client):
    """MINDMAP_PLAN.md item 177: a core node's shape set is "rounded
    rectangle, pill, ellipse". The first two were already there; `ellipse` is
    the one the validator would have refused, and a pattern that refuses a
    value the picker offers is a control that silently does nothing."""
    board = _map(client, name="Core")
    node = _node(client, board["id"], text="The whole idea")
    saved = client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], "shape": "ellipse", "core": True},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )
    assert saved.status_code == 200, saved.text
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert root["style"]["shape"] == "ellipse"
    assert root["style"]["core"] is True

    # And a shape nobody drew is still refused, which is what keeps the class
    # this string is written into a closed set.
    refused = client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], "shape": "trapezoid"},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )
    assert refused.status_code == 422


def test_k31_topic_shapes_and_pinned_line_sides_are_kept(client):
    """K31, the owner: "more shape designs for the core idea nodes" and "more
    say in which sides the connections come from and to". The four new shapes
    and the two side fields round-trip through the tree; a side that is not
    one of the four is refused, as an unknown shape is."""
    board = _map(client, name="K31")
    node = _node(client, board["id"], text="Core")

    def put(**data):
        return client.put(
            f"/whiteboard/objects/{node['id']}",
            json={"kind": node["kind"], "board_id": board["id"], "data": {**node["data"], **data},
                  "x": node["x"], "y": node["y"], "z": node["z"]},
        )

    for shape in ("circle", "hexagon", "diamond", "cloud"):
        assert put(shape=shape).status_code == 200, shape
        root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
        assert root["style"]["shape"] == shape
    assert put(edge_from="top", edge_to="left").status_code == 200
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert (root["style"]["edge_from"], root["style"]["edge_to"]) == ("top", "left")
    assert put(edge_from="middle").status_code == 422


def test_k31_the_map_line_style_picker_and_end_grips_are_wired():
    """The picker beside the layout writes the theme's `edge_style` through
    the undoable theme setter; the elbow keeps right-angled legs; the end
    grips write `edge_from`/`edge_to` through the undoable node setter."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (root / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
    assert '<select id="wb-map-link-style"' in html
    assert "return wbMapSetTheme({ edge_style:" in js
    assert "await wbMapSetNodeStyle(child, { [field]: side });" in js
    assert "if (style === \"elbow\") return wbMapElbowD(wbMapElbowPoints(a, w));" in js


def test_a_lines_thickness_and_arrowhead_are_kept_per_branch(client):
    """MINDMAP_PLAN.md item 177: "connection line styles: per-branch thickness,
    dash and arrowhead, managed from the map strip rather than by one global
    rule".

    Both live on the child, with the label and the line shape, because a tree
    edge is `parent_id` and has no row of its own. Both are also fields
    `WhiteboardObjectData` has to name: an undeclared one is dropped on the way
    in and the control looks like a frontend bug.
    """
    board = _map(client, name="Lines")
    root = _node(client, board["id"], text="Root")
    kid = _node(client, board["id"], text="A heavy branch")
    moved = client.put(
        f"/whiteboard/boards/{board['id']}/nodes/{kid['id']}/move",
        json={"parent_id": root["id"]},
    )
    assert moved.status_code == 200, moved.text

    def put(data):
        return client.put(
            f"/whiteboard/objects/{kid['id']}",
            json={
                "kind": kid["kind"],
                "board_id": board["id"],
                "data": {**kid["data"], **data},
                "x": kid["x"],
                "y": kid["y"],
                "z": kid["z"],
            },
        )

    assert put({"edge_width": "thick", "edge_arrow": "on"}).status_code == 200
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    style = tree["roots"][0]["children"][0]["style"]
    assert style["edge_width"] == "thick" and style["edge_arrow"] == "on"

    # A step nobody draws, and a third state for a two-word field, are refused
    # rather than stored: the frontend turns both straight into a class name.
    assert put({"edge_width": "hairline"}).status_code == 422
    assert put({"edge_arrow": "maybe"}).status_code == 422


def test_the_bar_on_a_topics_edge_is_kept_and_is_a_closed_set(client):
    """MINDMAP_PLAN.md item 177: "per-node left edge: solid, dashed or none".

    The check that matters is the round trip, not the 200: `WhiteboardObjectData`
    drops any field it does not name, so a `spine` the schema had not declared
    would have saved without complaint and come back missing, which is exactly
    what made an earlier toggle look like a frontend bug.
    """
    board = _map(client, name="Spine")
    node = _node(client, board["id"], text="A quiet topic")
    put = lambda data: client.put(  # noqa: E731 - one line, read three times below
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], **data},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )
    for value in ("dashed", "none"):
        assert put({"spine": value}).status_code == 200
        root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
        assert root["style"]["spine"] == value

    # Solid is the absence of the field, so nothing pins a map to today's
    # stylesheet, and a value nothing draws is refused rather than stored.
    assert put({"spine": None}).status_code == 200
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert "spine" not in root["style"]
    assert put({"spine": "dotted"}).status_code == 422


def test_a_topic_with_no_box_is_freeminds_own_fork_node(client):
    """The one shape FreeMind has a word for. `bubble` covers the other three
    between them, so the private `_shape` is what tells a pill from a box on
    the way back; `fork` is written as well because it is what makes the file
    look right in FreeMind, Freeplane and Coggle.

    The other direction matters more: a `.mm` written somewhere else carries
    no `_shape` at all, and `fork` is the only one of FreeMind's two styles
    that means anything here."""
    board = _map(client, name="Plain topics")
    node = _node(client, board["id"], text="On the line")
    client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"], "board_id": board["id"],
            "data": {**node["data"], "shape": "none"},
            "x": node["x"], "y": node["y"], "z": node["z"],
        },
    )
    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    assert 'STYLE="fork"' in exported

    foreign = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.0.1"><node TEXT="Root">
  <node TEXT="Bare" STYLE="fork"/><node TEXT="Boxed" STYLE="bubble"/>
</node></map>"""
    back = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": foreign}
    ).json()
    # The single root is the central topic (FEAT-01), so the two styled
    # topics are its children.
    roots = client.get(f"/whiteboard/boards/{back['id']}/tree").json()["roots"][0]["children"]
    shapes = {node["text"]: node["style"].get("shape") for node in roots}
    # `bubble` is this map's own default, so it stays unset rather than
    # putting a field on every node of every imported file.
    assert shapes == {"Bare": "none", "Boxed": None}


def test_a_plain_map_exports_exactly_as_it_did_before_styles(client):
    """The other half of the round trip: an attribute per unset field would
    triple a plain map's file and say nothing, so nothing unset is written."""
    board = _map(client, name="Plain")
    _node(client, board["id"], text="Trunk")
    freemind = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    opml = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    assert "<font" not in freemind and "<edge" not in freemind
    assert "_icon" not in freemind and "LINK" not in freemind and "STYLE" not in freemind
    assert "_bold" not in opml and "url=" not in opml


def test_an_imported_style_a_file_invented_is_dropped_field_by_field(client):
    """The import door validates each attribute against the same model the
    object PUT endpoint uses, and drops only what fails: a file with one bad
    attribute loses that attribute, not the nine beside it.

    The icon and the link are the two that matter. An icon name is written
    straight into a class attribute on the node, and a link is followed on
    click, so `javascript:` and a name full of punctuation are exactly what a
    file from somewhere else would carry if it were hostile."""
    hostile = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>Hostile</title></head><body>
<outline text="Topic" url="javascript:alert(1)" _icon="a&quot; onload=x" _bold="true"
         _font_size="9999" _edge_style="spiral" _color="red; background: url(x)"/>
</body></opml>"""
    board = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": hostile}
    ).json()
    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert node["style"] == {"bold": True}
    assert node["color"] is None


def _put_style(client, board_id, node, patch):
    """One style patch onto a node, through the door the strip and the rings
    use, returned unasserted so a test can check a refusal."""
    return client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board_id,
            "data": {**node["data"], **patch},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )


def test_a_picture_in_a_topic_is_one_of_this_notebooks_own_uploads(client):
    """MINDMAP_PLAN.md §12.1 item 2's fourth. The picture is a url, so the
    only question the schema has to answer is which urls: this install's own
    `/media/...` uploads and nothing else.

    Both of the two wrong answers are tested, because they fail differently:
    an off-origin address makes a node a way to call out of an app whose whole
    promise is that it never does, and a traversal passes a `startswith`
    check while resolving well outside the media folder."""
    board = _map(client, name="Pictures")
    node = _node(client, board["id"], text="Trunk")
    assert _put_style(client, board["id"], node, {"image": "https://evil.example/x.png"}).status_code == 422
    assert _put_style(client, board["id"], node, {"image": "/media/../../../etc/passwd"}).status_code == 422
    url = "/media/0123456789abcdef0123456789abcdef.png"
    assert _put_style(client, board["id"], node, {"image": url}).status_code == 200
    roots = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"]
    assert roots[0]["style"]["image"] == url


def test_a_line_bent_past_its_own_ends_is_refused(client):
    """The waypoint is two fractions of the line's own length (the fields'
    own comment). A slide past an anchor turns the curve back on itself, so
    the schema holds it inside the ends rather than letting a tangle be
    stored that no drag can undo."""
    board = _map(client, name="Bends")
    root = _node(client, board["id"], text="Trunk")
    child = _node(client, board["id"], parent_id=root["id"], text="Branch")
    assert _put_style(client, board["id"], child, {"edge_slide": 0.9}).status_code == 422
    assert _put_style(client, board["id"], child, {"edge_bend": 40}).status_code == 422
    assert _put_style(client, board["id"], child, {"edge_bend": -1.25, "edge_slide": 0.4}).status_code == 200
    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]["children"][0]
    assert node["style"]["edge_bend"] == -1.25
    assert node["style"]["edge_slide"] == 0.4


def test_an_imported_picture_or_bend_a_file_invented_is_dropped(client):
    """The import door holds these two to the same rules the PUT door does,
    which is what `_clean_import_style` is for: a `_image` in a file somebody
    was sent is exactly the door an off-origin url would come through, and a
    `_edge_bend` of a thousand is a line drawn off the edge of the map."""
    hostile = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>Hostile</title></head><body>
<outline text="Topic" _image="https://evil.example/x.png" _edge_bend="1000"
         _edge_slide="0.2" _bold="true"/>
</body></opml>"""
    board = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": hostile}
    ).json()
    node = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert node["style"] == {"bold": True, "edge_slide": 0.2}


def test_markdown_exports_as_an_indented_outline_and_comes_back(client):
    board = _map(client, name="Trip")
    root = _node(client, board["id"], text="Packing")
    _node(client, board["id"], parent_id=root["id"], text="Boots")

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown")
    assert exported.status_code == 200
    assert exported.text.splitlines()[:3] == ["# Trip", "", "- Packing"]
    assert "  - Boots" in exported.text

    back = client.post(
        "/whiteboard/boards/import",
        json={"format": "markdown", "content": exported.text},
    ).json()
    assert back["title"] == "Trip"
    tree = client.get(f"/whiteboard/boards/{back['id']}/tree").json()
    assert _structure(tree["roots"]) == [
        {"text": "Packing", "children": [{"text": "Boots", "children": []}]}
    ]


def test_a_reference_node_exports_as_the_note_it_points_at(client):
    """An outline whose rows say "(note 12)" is what makes the export usable
    as a working document rather than a picture of one."""
    note = client.post("/entries", json={"content": "# Sources\n\nreading"}).json()
    board = _map(client, name="Essay")
    _node(client, board["id"], kind="note", ref_id=note["id"])

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "Sources" in exported
    assert f"note {note['id']}" in exported


def test_an_import_with_a_doctype_is_refused(client):
    """The billion-laughs shape. Nothing in this app parses XML from anywhere
    else, and an import box is the one door that takes it, so the door
    refuses a document type declaration outright rather than trusting the
    parser's own defaults not to expand entities."""
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        "<opml><body><outline text=\"&lol;\"/></body></opml>"
    )
    refused = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": bomb}
    )
    assert refused.status_code == 422


def test_an_import_that_is_not_xml_at_all_is_a_422_not_a_500(client):
    refused = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": "not xml"}
    )
    assert refused.status_code == 422


def test_exporting_an_empty_map_is_still_a_document(client):
    board = _map(client, name="Empty")
    markdown = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert markdown.strip() == "# Empty"
    opml = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    assert "<opml" in opml and "Empty" in opml


def test_private_note_text_never_reaches_an_export(client, session):
    """The same rule the board preview and the Connections block already
    follow: the *fact* of the connection is not secret, its content is."""
    note = client.post("/entries", json={"content": "SECRET plans"}).json()
    session.get(Entry, note["id"]).is_private = True
    session.commit()

    board = _map(client, name="Essay")
    _node(client, board["id"], kind="note", ref_id=note["id"])

    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "SECRET" not in exported
    assert f"note {note['id']}" in exported


def test_the_node_endpoint_stores_position_and_colour(client):
    board = _map(client)
    created = client.post(
        f"/whiteboard/boards/{board['id']}/nodes",
        json={"kind": "topic", "text": "Root", "x": 40, "y": 90, "color": "#ff0000"},
    ).json()
    assert (created["x"], created["y"]) == (40, 90)

    stored = client.get(f"/whiteboard/?board_id={board['id']}").json()["objects"]
    assert [json.loads(json.dumps(o["data"]))["color"] for o in stored] == ["#ff0000"]
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert tree["roots"][0]["color"] == "#ff0000"


# --- Phase 3: the map as a citizen of the app (MINDMAP_PLAN.md §5 items 12-13)


def test_a_map_a_tool_touched_becomes_a_chip_in_the_transcript():
    """MINDMAP_PLAN.md §5 item 12, the chat half.

    `_touched_items` reads `id` off a result row, and every map tool names its
    board with `board_id` instead: so before this the four map tools
    contributed nothing at all to the transcript's touched line. A turn that
    read a whole map showed a bare tool name and no way to open what it read,
    which is the failure that line exists to prevent.
    """
    from tessellate.ai import agent

    rows = agent._touched_items(
        {"board_id": 7, "board_title": "Thesis map", "node_count": 12, "outline": "…"}
    )
    assert rows == [{"kind": "map", "id": 7, "label": "Thesis map"}]


def test_a_created_map_is_named_from_title_when_there_is_no_board_title():
    """`create_mindmap` returns `title`, `read_mindmap` returns `board_title`.
    Both are the map's name, and a chip reading "map #12" for one of them
    would be the same bug wearing a different key."""
    from tessellate.ai import agent

    rows = agent._touched_items({"board_id": 12, "title": "New map", "root_id": 3})
    assert rows == [{"kind": "map", "id": 12, "label": "New map"}]


def test_a_result_with_no_board_id_still_contributes_nothing():
    from tessellate.ai import agent

    assert agent._touched_items({"ok": True}) == []


def test_a_map_and_its_notes_are_a_node_and_edges_in_the_graph(client):
    """MINDMAP_PLAN.md §5 item 13, and the §3.3 rule it settles: a map's
    *membership* is a link, a node's *position* is not."""
    note = client.post("/entries", json={"content": "Gradient descent"}).json()
    other = client.post("/entries", json={"content": "Backprop"}).json()
    board = _map(client, name="ML map")
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], kind="note", ref_id=note["id"])
    _node(client, board["id"], parent_id=root["id"], kind="note", ref_id=other["id"])
    # A topic is not a note and must never become a graph edge.
    _node(client, board["id"], parent_id=root["id"], text="Just a thought")

    data = client.get("/graph?include_maps=true").json()
    map_edges = [e for e in data["edges"] if e["kind"] == "map"]
    assert sorted(e["target"] for e in map_edges) == sorted([note["id"], other["id"]])
    assert {e["source"] for e in map_edges} == {board["id"]}

    # The board is the node it already was, marked, not duplicated.
    ids = [n["id"] for n in data["nodes"]]
    assert ids.count(board["id"]) == 1
    node = next(n for n in data["nodes"] if n["id"] == board["id"])
    assert node["type"] == "map"


def test_a_board_is_off_the_graph_until_include_maps_asks_for_it(client):
    """`include_maps=false` means no board node and no map edge at all.

    This test used to assert the opposite of its second half: that the board
    stayed on the graph as an ordinary untyped node while the switch was off.
    That was the contract until INBOX 185, the owner: "Things that I have
    turned off in the graph for not showing them like the mindmap and entities
    still show anyway". A board *is* an `Entry`, so it had been a node here
    since boards existed, and the switch only ever marked it and drew its
    membership edges: three switches drawn identically, two of which added
    nodes and one of which did not, which is not a difference a reader can see.
    Off now means absent, the same as `include_entities` and
    `include_documents` (`scratchpad/ui-sweeps/graphshow.js` counts it in the
    browser; measured before the fix: 5 of 5 boards drawn with the switch off).
    """
    note = client.post("/entries", json={"content": "Gradient descent"}).json()
    board = _map(client, name="ML map")
    _node(client, board["id"], kind="note", ref_id=note["id"])

    data = client.get("/graph").json()
    assert [e for e in data["edges"] if e["kind"] == "map"] == []
    assert [n for n in data["nodes"] if n["id"] == board["id"]] == []

    asked = client.get("/graph?include_maps=true").json()
    node = next(n for n in asked["nodes"] if n["id"] == board["id"])
    assert node["type"] == "map"
    assert [e for e in asked["edges"] if e["kind"] == "map"]


def test_an_ordinary_whiteboard_is_marked_as_a_board_not_a_map(client):
    """A board of either kind is not a note the way every other graph node is,
    and one drawn as a note with a `# heading` for a label says so to nobody."""
    board = client.post("/whiteboard/boards", json={"name": "Sketches"}).json()
    data = client.get("/graph?include_maps=true").json()
    node = next(n for n in data["nodes"] if n["id"] == board["id"])
    assert node["type"] == "board"


def test_a_map_node_pointing_at_a_deleted_note_makes_no_dangling_edge(client, session):
    """d3 silently drops an edge naming a node it never received, so a
    dangling edge is an invisible failure rather than a visible one."""
    note = client.post("/entries", json={"content": "Temporary"}).json()
    board = _map(client, name="ML map")
    _node(client, board["id"], kind="note", ref_id=note["id"])
    client.delete(f"/entries/{note['id']}")
    session.expire_all()

    data = client.get("/graph?include_maps=true").json()
    ids = {n["id"] for n in data["nodes"]}
    for edge in data["edges"]:
        assert edge["source"] in ids and edge["target"] in ids


def test_a_document_node_on_a_map_is_not_a_graph_edge(client):
    """Only a *note* reference is an edge here: a document node's id is a
    Document id, and emitting it into a space of Entry ids would join the map
    to whichever unrelated note happened to share the number."""
    board = _map(client, name="Reading")
    document = client.post("/documents", json={"title": "Paper", "content": "x"}).json()
    _node(client, board["id"], kind="document", ref_id=document["id"])

    data = client.get("/graph?include_maps=true").json()
    assert [e for e in data["edges"] if e["kind"] == "map"] == []


# --- Phase 3: attaching a map to a chat message (MINDMAP_PLAN.md §5 item 11)


def _prepared(**body):
    """What `_prepare` hands the model, for a question with attachments.

    Called directly rather than through `POST /chat` because that endpoint
    needs a running model to answer, and this is a test about what the model
    is *given*, not about what it says back.
    """
    from tessellate.api import routes_chat
    from tessellate.core import deps

    session = deps.get_db().session()
    try:
        return routes_chat._prepare(
            session, body.pop("question", "what is on it?"), **body
        )
    finally:
        session.close()


def test_an_attached_map_reaches_the_model_as_its_outline(client):
    """The whole reason `board_ids` is its own field: a board IS an Entry, so
    `note_ids` would have carried it, and a board's content is the single
    line `# My map`, so attaching one as a note sends the model a heading and
    calls it a map."""
    board = _map(client, name="Thesis")
    root = _node(client, board["id"], text="Argument")
    _node(client, board["id"], parent_id=root["id"], text="Evidence")
    _node(client, board["id"], parent_id=root["id"], text="Counterpoint")

    prepared = _prepared(board_ids=[board["id"]])
    rows = [n for n in prepared["notes"] if n.get("category") == "Mind map"]
    assert len(rows) == 1
    content = rows[0]["content"]
    assert "Mind map: Thesis" in content
    assert "3 nodes" in content
    # Indented, one node per line, the shape the plan chose for a small model.
    assert "- Argument" in content
    assert "  - Evidence" in content
    assert "  - Counterpoint" in content
    assert rows[0]["attached"] is True


def test_a_reference_node_says_what_kind_it_is_in_the_outline(client):
    """"Which of these is a real note?" has to be answerable from the outline
    without a second call, the same reason `read_mindmap` marks them."""
    note = client.post("/entries", json={"content": "Gradient descent"}).json()
    board = _map(client, name="ML")
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], kind="note", ref_id=note["id"])

    content = [
        n for n in _prepared(board_ids=[board["id"]])["notes"]
        if n.get("category") == "Mind map"
    ][0]["content"]
    assert "Gradient descent [note]" in content


def test_attaching_a_map_makes_the_turn_about_the_notebook(client):
    """Same override the other three attachment kinds already apply: "what do
    you think?" with a map clipped to it is a question about that map, however
    smalltalk-shaped it reads."""
    from tessellate.ai import intent

    board = _map(client, name="Thesis")
    _node(client, board["id"], text="Argument")
    assert _prepared(question="hey", board_ids=[board["id"]])["intent"] == intent.NOTES


def test_a_private_board_is_never_attached(client, session):
    """Attaching is a deliberate act, so this is not the guard that matters, 
    but `read_mindmap` refuses a private board on the AI's behalf, and one
    reaching the model through a different door would make that decorative."""
    board = _map(client, name="Secret")
    _node(client, board["id"], text="SECRET plan")
    session.get(Entry, board["id"]).is_private = True
    session.commit()

    prepared = _prepared(board_ids=[board["id"]])
    assert [n for n in prepared["notes"] if n.get("category") == "Mind map"] == []
    assert "SECRET" not in json.dumps(prepared["notes"])


def test_an_empty_map_says_it_is_empty_rather_than_nothing(client):
    """A chip in the transcript corresponding to nothing at all is the failure
    `document_ids` already shipped once (routes_chat.py says so by name)."""
    board = _map(client, name="Blank")
    content = [
        n for n in _prepared(board_ids=[board["id"]])["notes"]
        if n.get("category") == "Mind map"
    ][0]["content"]
    assert "(empty: no nodes yet)" in content


def test_a_long_outline_is_truncated_to_the_budget(client):
    """Every character here is resent on every round of the turn."""
    from tessellate.api import routes_chat

    board = _map(client, name="Huge")
    root = _node(client, board["id"], text="Root")
    for i in range(400):
        _node(client, board["id"], parent_id=root["id"], text=f"Node number {i} with words")

    content = [
        n for n in _prepared(board_ids=[board["id"]])["notes"]
        if n.get("category") == "Mind map"
    ][0]["content"]
    assert "[…truncated]" in content
    assert len(content) < routes_chat.ATTACHED_MAP_CHARS + 400


def test_the_chat_request_caps_attached_maps_at_four(client):
    """Matching `document_ids` and `file_ids`, and the composer's own ceiling."""
    refused = client.post(
        "/chat", json={"question": "hi", "board_ids": [1, 2, 3, 4, 5]}
    )
    assert refused.status_code == 422


def test_a_board_id_that_is_not_a_board_contributes_nothing(client):
    """A deleted map, or an id typed by hand. Skipped in silence rather than
    refused: the message is still worth answering."""
    prepared = _prepared(board_ids=[99999])
    assert [n for n in prepared["notes"] if n.get("category") == "Mind map"] == []


# --- exports that cannot be made to recurse ---------------------------------


def _deep_chain(session, board_id: int, depth: int) -> int:
    """One branch, `depth` nodes long, written straight to the database.

    Through the API this would be `depth` requests and about as many seconds;
    what the test is about is the export, not the insert. `parent_id` is a
    plain integer column (see its own comment), so this builds exactly the
    shape a person builds with the Tab key, only faster.
    """
    parent_id = None
    for level in range(depth):
        node = WhiteboardObject(
            kind="topic",
            data=json.dumps({"content": f"Level {level}"}),
            board_id=board_id,
            x=float(level * 40),
            y=0.0,
            width=200.0,
            height=56.0,
            parent_id=parent_id,
        )
        session.add(node)
        session.flush()
        parent_id = node.id
    session.commit()
    return depth


def test_a_map_deeper_than_pythons_recursion_headroom_still_exports(client, session):
    """**The two XML exports used to recurse.** Nothing caps how deep a map
    built by hand can go: `MAX_IMPORT_DEPTH` caps an import and the Tab key is
    not an import. A branch longer than Python's own recursion limit therefore
    left `_export_opml` and `_export_freemind` raising `RecursionError`, which
    reaches the person pressing Download as a 500 on a map that opens fine.

    1,200 rather than a round thousand: the default limit is 1,000 and each
    level of the old walk took more than one frame, so a number just over it
    would have passed by luck on some builds.
    """
    board = _map(client, name="Deep map")
    depth = _deep_chain(session, board["id"], 1200)

    for fmt in ("opml", "freemind", "markdown"):
        exported = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}")
        assert exported.status_code == 200, f"{fmt}: {exported.text[:200]}"
        # Every level is in the file: the nesting is clamped past
        # MAX_MAP_DEPTH, the content is not.
        assert "Level 0" in exported.text
        assert f"Level {depth - 1}" in exported.text
        assert exported.text.count("Level ") == depth


def test_a_ring_in_the_tree_does_not_hang_an_export(client, session):
    """`_build_tree` re-roots the lowest id of an unreachable ring rather than
    dropping its rows, so a ring reaches the exporters as a root whose
    descendants lead back to it. The recursive versions never returned, and
    the Markdown walk, which was already iterative, had no seen set and
    appended rows until it ran out of memory.

    A ring is not hypothetical: `parent_id` is a plain integer, so any write
    that sets it without the move endpoint's `_is_descendant` check can make
    one, and a restored backup or a hand-edited database certainly can.
    """
    board = _map(client, name="Ring map")
    first = _node(client, board["id"], text="A")
    second = _node(client, board["id"], parent_id=first["id"], text="B")
    # Close the ring behind the API's back: the move endpoint refuses this,
    # which is the point. It is the shape that arrives from somewhere else.
    session.get(WhiteboardObject, first["id"]).parent_id = second["id"]
    session.commit()

    for fmt in ("opml", "freemind", "markdown"):
        exported = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}")
        assert exported.status_code == 200, f"{fmt}: {exported.text[:200]}"
        # Each node once, not once per lap.
        laps_a = exported.text.count(">A<") + exported.text.count('"A"') + exported.text.count("- A")
        laps_b = exported.text.count(">B<") + exported.text.count('"B"') + exported.text.count("- B")
        assert laps_a == 1, f"{fmt}: node A written {laps_a} times"
        assert laps_b == 1, f"{fmt}: node B written {laps_b} times"


# --- the map's own theme (MINDMAP_PLAN.md §13e) ------------------------------
#
# The owner, INBOX 305: "the customisation features are lacking severely."
# §13.4 measured what that meant: eleven per-topic fields, every one of them
# set one topic at a time, and no map-level default of any kind. These tests
# hold the two rules the theme is worth nothing without: a topic that was
# never told otherwise follows the map, and a topic that *was* told never
# changes because the map did.


def test_a_new_map_has_no_theme(client):
    board = _map(client)
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree")
    assert tree.status_code == 200, tree.text
    assert tree.json()["theme"] == {}


def test_a_theme_is_stored_and_read_back(client):
    board = _map(client)
    saved = client.put(
        f"/whiteboard/boards/{board['id']}",
        json={"theme": {"font_size": 19, "shape": "pill", "edge_width": "thick", "bold": True}},
    )
    assert saved.status_code == 200, saved.text
    theme = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["theme"]
    assert theme == {"font_size": 19, "shape": "pill", "edge_width": "thick", "bold": True}


def test_a_theme_write_is_a_patch_and_null_stops_theming_a_field(client):
    board = _map(client)
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"shape": "pill", "italic": True}})
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"italic": None}})
    theme = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["theme"]
    # The shape was not mentioned in the second write, so it is untouched; the
    # italic was sent as null, which is how the dialog says "stop theming it".
    assert theme == {"shape": "pill"}


def test_a_theme_never_clears_the_board_type_or_layout(client):
    """The settings blob is a family, and a theme write is read-modify-write.

    The failure this catches is silent: a map that quietly became an ordinary
    whiteboard because somebody picked a font size.
    """
    board = _map(client, layout="radial")
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"font_size": 25}})
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert (tree["type"], tree["layout"]) == ("map", "radial")


def test_a_layout_change_never_clears_the_theme(client):
    board = _map(client)
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"font_size": 25}})
    client.put(f"/whiteboard/boards/{board['id']}", json={"layout": "tree-down"})
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree").json()
    assert tree["theme"] == {"font_size": 25}
    assert tree["layout"] == "tree-down"


def test_an_unknown_theme_field_or_value_is_dropped_rather_than_refused(client):
    """A look, not a document: a picker one version ahead leaves a plainer map.

    Refusing would make the whole write fail over one field, which is how a
    person loses the four choices they made beside it.
    """
    board = _map(client)
    saved = client.put(
        f"/whiteboard/boards/{board['id']}",
        json={"theme": {"shape": "octagon", "beard": "long", "align": "center", "font_size": 4000}},
    )
    assert saved.status_code == 200, saved.text
    assert client.get(f"/whiteboard/boards/{board['id']}/tree").json()["theme"] == {"align": "center"}


def test_a_corrupt_settings_blob_reads_as_no_theme(client, session):
    board = _map(client)
    entry = session.get(Entry, board["id"])
    entry.board_settings = "{not json at all"
    session.commit()
    tree = client.get(f"/whiteboard/boards/{board['id']}/tree")
    assert tree.status_code == 200
    assert tree.json()["theme"] == {}


def test_the_tree_still_reports_what_each_node_itself_carries(client):
    """The theme is resolved at paint time, never written onto a node.

    This is the rule that makes a map-wide change safe to press, and the one
    the strip depends on: it has to be able to show a field as set or unset.
    """
    board = _map(client)
    node = _node(client, board["id"], text="Root")
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"shape": "pill"}})
    roots = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"]
    assert roots[0]["id"] == node["id"]
    assert "shape" not in roots[0]["style"]


def test_an_export_of_a_themed_map_carries_the_theme_a_topic_did_not_override(client):
    """None of the three formats has a place for a map-level look, so a file
    written from the stored styles alone comes out plainer than the map."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    kept = _node(client, board["id"], parent_id=root["id"], text="Its own shape")
    saved = client.put(
        f"/whiteboard/objects/{kept['id']}",
        json={
            "kind": kept["kind"],
            "board_id": board["id"],
            "data": {**kept["data"], "shape": "rect"},
            "x": kept["x"],
            "y": kept["y"],
            "z": kept["z"],
        },
    )
    assert saved.status_code == 200, saved.text
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"shape": "pill"}})
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    # The root never chose a shape, so it exports as the map's; the child did,
    # and exports as its own.
    assert 'shape="pill"' in text
    assert 'shape="rect"' in text


def test_clearing_every_topics_look_leaves_them_following_the_map(client):
    """"Reset to branch" at the map's scope: the same list of fields, dropped
    from every topic in one request rather than one at a time."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    child = _node(client, board["id"], parent_id=root["id"], text="Child")
    for node, patch in ((root, {"shape": "ellipse", "bold": True}), (child, {"color": "#ff0000"})):
        saved = client.put(
            f"/whiteboard/objects/{node['id']}",
            json={
                "kind": node["kind"],
                "board_id": board["id"],
                "data": {**node["data"], **patch},
                "x": node["x"],
                "y": node["y"],
                "z": node["z"],
            },
        )
        assert saved.status_code == 200, saved.text
    done = client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    assert done.status_code == 200, done.text
    assert done.json() == {"cleared": 2}
    roots = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"]
    assert roots[0]["style"] == {}
    assert roots[0]["children"][0]["style"] == {}
    assert roots[0]["children"][0]["color"] is None
    # And it is idempotent: nothing left to clear is a count of zero, not an
    # error and not a write.
    assert client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style").json() == {"cleared": 0}


def test_clearing_a_topics_look_keeps_its_picture(client):
    """A picture is content, not a look: the one thing the per-node reset has
    always kept, kept here for the same reason."""
    board = _map(client)
    node = _node(client, board["id"], text="With a picture")
    client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], "image": "/media/x.png", "bold": True},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )
    assert client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style").json() == {"cleared": 1}
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert root["style"] == {"image": "/media/x.png"}


# --- a cross-link survives an export (MINDMAP_PLAN.md §13d) -------------------
#
# §13.2 measured it: a map's two kinds of connection have different export
# fates. The branch is the indent and survives all three formats; the
# cross-link survived none, because `export_board` walks objects and
# `parent_id` only and no exporter read `cross_links`.


def _cross_link(client, board_id, source, target, label=""):
    made = client.post(
        "/whiteboard/sketches",
        json={
            "board_id": board_id,
            "data": json.dumps(
                {
                    "type": "link-straight",
                    "sourceId": source,
                    "sourceKind": "object",
                    "targetId": target,
                    "targetKind": "object",
                    "label": label,
                }
            ),
        },
    )
    assert made.status_code == 200, made.text
    return made.json()


def _linked_map(client):
    board = _map(client, name="Crossed")
    root = _node(client, board["id"], text="Trunk")
    left = _node(client, board["id"], parent_id=root["id"], text="Left")
    right = _node(client, board["id"], parent_id=root["id"], text="Right")
    _cross_link(client, board["id"], left["id"], right["id"], label="compare")
    return board, root, left, right


def test_a_cross_link_is_written_into_the_freemind_export(client):
    board, _root, left, right = _linked_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    assert f'ID="ID_{left["id"]}"' in text
    assert f'DESTINATION="ID_{right["id"]}"' in text
    assert 'MIDDLE_LABEL="compare"' in text


def test_a_cross_link_is_written_into_the_opml_export(client):
    board, _root, left, right = _linked_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    assert f'_id="ID_{left["id"]}"' in text
    assert f'_links="ID_{right["id"]}"' in text


def test_markdown_carries_the_outline_and_says_nothing_about_cross_links(client):
    """The decision, not an oversight: this format's promise is an outline
    anybody can paste anywhere, and `_parse_markdown_outline` reads
    indentation, so a cross-links section would come back in as topics."""
    board, _root, _left, _right = _linked_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "Left" in text and "Right" in text
    assert "ID_" not in text and "compare" not in text


def test_a_cross_link_round_trips_through_freemind(client):
    board, _root, left, right = _linked_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    back = client.post(
        "/whiteboard/boards/import",
        json={"format": "freemind", "content": text, "name": "Back"},
    )
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    # The single root comes back as the central topic (FEAT-01), with
    # "Left" and "Right" under it, still linked.
    assert [node["text"] for node in tree["roots"]] == ["Trunk"]
    names = {node["id"]: node["text"] for node in tree["roots"][0]["children"]}
    assert sorted(names.values()) == ["Left", "Right"]
    assert len(tree["cross_links"]) == 1
    link = tree["cross_links"][0]
    assert (names[link["from_id"]], names[link["to_id"]]) == ("Left", "Right")


def test_a_cross_link_round_trips_through_opml(client):
    board, _root, _left, _right = _linked_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    back = client.post(
        "/whiteboard/boards/import", json={"format": "opml", "content": text, "name": "Back"}
    )
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    assert len(tree["cross_links"]) == 1


def test_an_arrowlink_to_a_node_that_is_not_in_the_file_is_dropped(client):
    """Half a link is a line to nowhere, which `_forget_links_to` exists to
    stop accumulating; the import must not create one in the first place."""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<map version="1.0.1"><node TEXT="Trunk" ID="ID_1">'
        '<node TEXT="Here" ID="ID_2"><arrowlink DESTINATION="ID_999"/></node>'
        "</node></map>"
    )
    back = client.post(
        "/whiteboard/boards/import", json={"format": "freemind", "content": content, "name": "Half"}
    )
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    assert tree["cross_links"] == []


def test_a_map_with_no_cross_links_exports_exactly_as_it_did(client):
    """A plain map's file must not grow a single attribute it did not have."""
    board = _map(client, name="Plain")
    root = _node(client, board["id"], text="Trunk")
    _node(client, board["id"], parent_id=root["id"], text="Leaf")
    for fmt, marker in (("freemind", "arrowlink"), ("opml", "_links")):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert marker not in text


def test_a_topics_order_among_its_siblings_is_stored_and_read_back(client):
    """Sibling order (INBOX 445; MINDMAP_PLAN §12.0's Ctrl+Shift+arrows): a
    topic moved up among its siblings carries `data.order`, and the tree and
    the exports read the siblings in that order, so it round-trips. Without
    it the order was creation order and nothing could change it."""
    board = _map(client, name="Order map")
    root = _node(client, board["id"], text="Trunk")
    first = _node(client, board["id"], parent_id=root["id"], text="First")
    _node(client, board["id"], parent_id=root["id"], text="Second")
    third = _node(client, board["id"], parent_id=root["id"], text="Third")

    def kids(board_id):
        tree = client.get(f"/whiteboard/boards/{board_id}/tree").json()
        return [n["text"] for n in tree["roots"][0]["children"]]

    assert kids(board["id"]) == ["First", "Second", "Third"]
    # Third to the top: its key goes below First's, which is First's id.
    moved = {**third, "data": {**third["data"], "order": first["id"] - 0.5}}
    put = client.put(f"/whiteboard/objects/{third['id']}", json=moved)
    assert put.status_code == 200, put.text
    assert put.json()["data"]["order"] == first["id"] - 0.5
    assert kids(board["id"]) == ["Third", "First", "Second"]

    outline = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert outline.index("Third") < outline.index("First") < outline.index("Second")
    opml = client.get(f"/whiteboard/boards/{board['id']}/export?format=opml").text
    again = client.post("/whiteboard/boards/import", json={"format": "opml", "content": opml})
    assert again.status_code == 201, again.text
    assert kids(again.json()["id"]) == ["Third", "First", "Second"]


def test_deleting_a_branch_hands_back_the_cross_links_that_went_with_it(client):
    """INBOX 445 (2): a branch deleted and restored with Ctrl+Z came back
    without its cross-links, because the response named the topics and not
    the link sketches the server dropped with them. They ride along now, as
    sketch rows, so the client can draw them again between the restored
    topics. A link from inside the branch to a topic outside it is among
    them (its far end still exists); a link elsewhere on the board is not."""
    board = _map(client, name="Links go too")
    root = _node(client, board["id"], text="Trunk")
    branch = _node(client, board["id"], parent_id=root["id"], text="Branch")
    inside = _node(client, board["id"], parent_id=branch["id"], text="Inside")
    outside = _node(client, board["id"], parent_id=root["id"], text="Outside")
    other = _node(client, board["id"], parent_id=root["id"], text="Other")
    across = _cross_link(client, board["id"], inside["id"], outside["id"], label="across")
    within = _cross_link(client, board["id"], branch["id"], inside["id"])
    elsewhere = _cross_link(client, board["id"], outside["id"], other["id"])

    res = client.delete(f"/whiteboard/objects/{branch['id']}")
    assert res.status_code == 200, res.text
    body = res.json()
    got = {row["id"]: json.loads(row["data"]) for row in body["links"]}
    assert set(got) == {across["id"], within["id"]}
    assert got[across["id"]]["label"] == "across"
    assert got[across["id"]]["sourceId"] == inside["id"]
    assert got[across["id"]]["targetId"] == outside["id"]
    # The server really dropped them, and left the unrelated one.
    left = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["cross_links"]
    assert [(link["from_id"], link["to_id"]) for link in left] == [(outside["id"], other["id"])]
    assert elsewhere["id"] not in got


def test_deleting_a_topic_with_no_links_returns_an_empty_list(client):
    """The new field is empty rather than absent, so a client can read it
    without a guard."""
    board = _map(client, name="No links")
    root = _node(client, board["id"], text="Trunk")
    leaf = _node(client, board["id"], parent_id=root["id"], text="Leaf")
    body = client.delete(f"/whiteboard/objects/{leaf['id']}").json()
    assert body["links"] == []



# --- a topic that is a task (MINDMAP_PLAN.md decision 15) ---------------------


def _set_data(client, board, node, patch):
    return client.put(
        f"/whiteboard/objects/{node['id']}",
        json={
            "kind": node["kind"],
            "board_id": board["id"],
            "data": {**node["data"], **patch},
            "x": node["x"],
            "y": node["y"],
            "z": node["z"],
        },
    )


def _task_map(client):
    board = _map(client, name="Launch")
    root = _node(client, board["id"], text="Launch")
    open_ = _node(client, board["id"], parent_id=root["id"], text="Write the post")
    done = _node(client, board["id"], parent_id=root["id"], text="Book the room")
    assert _set_data(client, board, open_, {"task": "open"}).status_code == 200
    assert _set_data(client, board, done, {"task": "done"}).status_code == 200
    return board


def test_a_task_is_open_or_done_and_nothing_else(client):
    board = _map(client)
    node = _node(client, board["id"], text="Maybe")
    assert _set_data(client, board, node, {"task": "half"}).status_code == 422
    assert _set_data(client, board, node, {"task": "done"}).status_code == 200
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert root["style"] == {"task": "done"}


def test_a_markdown_export_writes_tasks_as_task_list_items_and_reads_them_back(client):
    board = _task_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "  - [ ] Write the post" in text and "  - [x] Book the room" in text
    assert "- Launch" in text and "[ ] Launch" not in text
    back = client.post(
        "/whiteboard/boards/import", json={"format": "markdown", "content": text, "name": "Back"}
    )
    assert back.status_code == 201, back.text
    kids = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"][0]["children"]
    assert {(k["text"], k["style"].get("task")) for k in kids} == {
        ("Write the post", "open"),
        ("Book the room", "done"),
    }


def test_a_task_round_trips_through_both_xml_formats(client):
    board = _task_map(client)
    for fmt in ("opml", "freemind"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert '_task="open"' in text and '_task="done"' in text
        back = client.post(
            "/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt}
        )
        assert back.status_code == 201, back.text
        # A FreeMind file's root is the map's title on the way back in, so
        # every node is read rather than the first root's children.
        seen, stack = [], list(client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"])
        while stack:
            node = stack.pop()
            seen.append(node["style"].get("task"))
            stack.extend(node["children"])
        assert sorted(t for t in seen if t) == ["done", "open"], fmt


def test_resetting_a_maps_looks_keeps_its_tasks(client):
    board = _task_map(client)
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    kids = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]["children"]
    assert sorted(k["style"].get("task") for k in kids) == ["done", "open"]


def test_a_bracket_with_nothing_after_it_is_a_topic_not_a_task(client):
    back = client.post(
        "/whiteboard/boards/import",
        json={"format": "markdown", "content": "# T\n- [ ]\n- [x] Done thing\n", "name": "Edge"},
    )
    assert back.status_code == 201, back.text
    roots = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"]
    assert [(r["text"], r["style"].get("task")) for r in roots] == [("[ ]", None), ("Done thing", "done")]



# --- numbered branches (MINDMAP_PLAN.md decision 17) --------------------------


def _numbered_map(client, numbered=True):
    board = _map(client, name="Plan")
    root = _node(client, board["id"], text="Plan")
    first = _node(client, board["id"], parent_id=root["id"], text="Research")
    _node(client, board["id"], parent_id=first["id"], text="Read the papers")
    second = _node(client, board["id"], parent_id=root["id"], text="Write")
    _node(client, board["id"], parent_id=first["id"], text="Interview")
    assert _set_data(client, board, second, {"task": "open"}).status_code == 200
    if numbered:
        assert client.put(f"/whiteboard/boards/{board['id']}", json={"numbered": True}).status_code == 200
    return board


def test_numbering_is_off_until_a_map_asks_and_a_put_without_it_leaves_it(client):
    board = _map(client)

    def tree():
        return client.get(f"/whiteboard/boards/{board['id']}/tree").json()

    assert tree()["numbered"] is False
    assert client.put(f"/whiteboard/boards/{board['id']}", json={"numbered": True}).status_code == 200
    assert tree()["numbered"] is True
    # A layout change, a theme change and a rename do not touch it.
    client.put(f"/whiteboard/boards/{board['id']}", json={"layout": "radial"})
    client.put(f"/whiteboard/boards/{board['id']}", json={"theme": {"bold": True}})
    client.put(f"/whiteboard/boards/{board['id']}", json={"title": "Renamed"})
    assert tree()["numbered"] is True
    assert tree()["layout"] == "radial"
    assert client.put(f"/whiteboard/boards/{board['id']}", json={"numbered": False}).status_code == 200
    assert tree()["numbered"] is False


def test_a_numbered_maps_markdown_carries_the_numbers_after_the_task_box(client):
    board = _numbered_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    lines = [line for line in text.splitlines() if line.lstrip().startswith("-")]
    assert lines == [
        "- Plan",
        "  - 1 Research",
        "    - 1.1 Read the papers",
        "    - 1.2 Interview",
        "  - [ ] 2 Write",
    ]


def test_an_unnumbered_maps_markdown_has_no_numbers(client):
    board = _numbered_map(client, numbered=False)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "  - Research" in text and "1.1" not in text


def _tree_texts(client, board_id):
    out, stack = [], list(client.get(f"/whiteboard/boards/{board_id}/tree").json()["roots"])
    while stack:
        node = stack.pop()
        out.append(node["text"])
        stack.extend(node["children"])
    return sorted(out)


def test_numbering_round_trips_through_markdown_and_opml(client):
    board = _numbered_map(client)
    for fmt in ("markdown", "opml"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        if fmt == "opml":
            assert '_number="1.2"' in text and '_number="2"' in text
        back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt})
        assert back.status_code == 201, back.text
        tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
        assert tree["numbered"] is True, fmt
        assert _tree_texts(client, back.json()["id"]) == sorted(
            ["Plan", "Research", "Read the papers", "Interview", "Write"]
        ), fmt


def test_numbers_that_do_not_match_the_outline_stay_as_text(client):
    content = "# Years\n- Years\n  - 2024 plan\n  - 2025 plan\n"
    back = client.post("/whiteboard/boards/import", json={"format": "markdown", "content": content})
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    assert tree["numbered"] is False
    assert [k["text"] for k in tree["roots"][0]["children"]] == ["2024 plan", "2025 plan"]



# --- a note behind a topic (MINDMAP_PLAN.md decision 18) ----------------------

_NOTE = "First line\nsecond line\n\n- a line that looks like a bullet\n# and one like a heading"


def _note_map(client, numbered=False):
    board = _map(client, name="Notes")
    root = _node(client, board["id"], text="Notes")
    research = _node(client, board["id"], parent_id=root["id"], text="Research")
    _node(client, board["id"], parent_id=research["id"], text="Read the papers")
    plain = _node(client, board["id"], parent_id=root["id"], text="Write")
    assert _set_data(client, board, research, {"note": _NOTE}).status_code == 200
    assert _set_data(client, board, plain, {"task": "open", "note": "One line."}).status_code == 200
    if numbered:
        assert client.put(f"/whiteboard/boards/{board['id']}", json={"numbered": True}).status_code == 200
    return board


def _notes_by_text(client, board_id):
    out, stack = {}, list(client.get(f"/whiteboard/boards/{board_id}/tree").json()["roots"])
    while stack:
        node = stack.pop()
        out[node["text"]] = (node["style"].get("note"), len(node["children"]))
        stack.extend(node["children"])
    return out


def test_a_note_is_saved_with_the_topic_and_has_a_ceiling(client):
    board = _map(client)
    node = _node(client, board["id"], text="Topic")
    assert _set_data(client, board, node, {"note": "x" * 10_001}).status_code == 422
    assert _set_data(client, board, node, {"note": "Behind it."}).status_code == 200
    root = client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"][0]
    assert root["style"] == {"note": "Behind it."}


def test_a_markdown_export_writes_a_note_as_an_indented_paragraph(client):
    board = _note_map(client)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert (
        "  - Research\n"
        "\n"
        "    First line\n"
        "    second line\n"
        "\n"
        "    \\- a line that looks like a bullet\n"
        "    \\# and one like a heading\n"
        "\n"
        "    - Read the papers\n"
    ) in text
    assert "  - [ ] Write\n\n    One line.\n" in text


def test_notes_round_trip_through_markdown_with_tasks_and_numbers(client):
    board = _note_map(client, numbered=True)
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    back = client.post("/whiteboard/boards/import", json={"format": "markdown", "content": text})
    assert back.status_code == 201, back.text
    tree = client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()
    assert tree["numbered"] is True
    notes = _notes_by_text(client, back.json()["id"])
    assert notes["Research"] == (_NOTE, 1)
    assert notes["Write"] == ("One line.", 0)
    assert notes["Read the papers"] == (None, 0)
    kids = tree["roots"][0]["children"]
    assert [k["style"].get("task") for k in kids] == [None, "open"]


def test_notes_round_trip_through_both_xml_formats(client):
    board = _note_map(client)
    for fmt in ("opml", "freemind"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert '_note="One line."' in text, fmt
        back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt})
        assert back.status_code == 201, back.text
        notes = _notes_by_text(client, back.json()["id"])
        assert notes["Research"][0] == _NOTE, fmt
        assert notes["Write"][0] == "One line.", fmt


def test_a_paragraph_under_a_hand_written_bullet_is_its_note(client):
    content = "# Trip\n- Trip\n  - Pack\n    Passport, charger.\n    Tickets.\n  - Go\n"
    back = client.post("/whiteboard/boards/import", json={"format": "markdown", "content": content})
    assert back.status_code == 201, back.text
    notes = _notes_by_text(client, back.json()["id"])
    assert notes["Pack"] == ("Passport, charger.\nTickets.", 0)
    assert notes["Go"] == (None, 0)


def test_resetting_a_maps_looks_keeps_its_notes(client):
    board = _note_map(client)
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    notes = _notes_by_text(client, board["id"])
    assert notes["Research"][0] == _NOTE and notes["Write"][0] == "One line."


# --- boundaries and summaries (MINDMAP_PLAN.md decisions 19 and 20) ---------


def _structure_map(client):
    board = _map(client, name="Structure")
    root = _node(client, board["id"], text="Plan")
    a = _node(client, board["id"], parent_id=root["id"], text="Pack")
    _node(client, board["id"], parent_id=a["id"], text="Passport")
    b = _node(client, board["id"], parent_id=root["id"], text="Book")
    _node(client, board["id"], parent_id=root["id"], text="Go")
    assert _set_data(client, board, a, {"boundary": "cloud", "boundary_label": "Before"}).status_code == 200
    assert _set_data(client, board, a, {"boundary": "cloud", "boundary_label": "Before", "summary": "Errands", "summary_span": 2}).status_code == 200
    assert _set_data(client, board, b, {"boundary": "dashed"}).status_code == 200
    return board


def _styles_by_text(client, board_id):
    out, stack = {}, list(client.get(f"/whiteboard/boards/{board_id}/tree").json()["roots"])
    while stack:
        node = stack.pop()
        out[node["text"]] = node["style"]
        stack.extend(node["children"])
    return out


def test_a_boundary_and_a_summary_are_checked_on_the_way_in(client):
    board = _map(client)
    node = _node(client, board["id"], text="Topic")
    assert _set_data(client, board, node, {"boundary": "zigzag"}).status_code == 422
    assert _set_data(client, board, node, {"boundary_label": "x" * 81}).status_code == 422
    assert _set_data(client, board, node, {"summary": "x" * 81}).status_code == 422
    assert _set_data(client, board, node, {"summary_span": 0}).status_code == 422
    assert _set_data(client, board, node, {"summary_span": 101}).status_code == 422


def test_boundaries_and_summaries_round_trip_through_both_xml_formats(client):
    board = _structure_map(client)
    want = {"boundary": "cloud", "boundary_label": "Before", "summary": "Errands", "summary_span": 2}
    for fmt in ("opml", "freemind"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert '_summary_span="2"' in text and '_boundary="cloud"' in text, fmt
        back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt})
        assert back.status_code == 201, back.text
        styles = _styles_by_text(client, back.json()["id"])
        assert {k: styles["Pack"].get(k) for k in want} == want, fmt
        assert styles["Book"].get("boundary") == "dashed", fmt
        assert "boundary" not in styles["Go"], fmt


def test_resetting_a_maps_looks_keeps_its_boundaries_and_summaries(client):
    board = _structure_map(client)
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    styles = _styles_by_text(client, board["id"])
    assert styles["Pack"]["boundary"] == "cloud" and styles["Pack"]["summary"] == "Errands"


# --- Markers (§12.2 item 4, the audit's M4, decision 34) -------------------


def _marked_map(client):
    board = _map(client, name="Marked")
    root = _node(client, board["id"], text="Plan")
    a = _node(client, board["id"], parent_id=root["id"], text="Pack")
    b = _node(client, board["id"], parent_id=root["id"], text="Book")
    marks = {"priority": 2, "progress": 50, "flag": True, "markers": ["star", "warning"]}
    assert _set_data(client, board, a, marks).status_code == 200
    assert _set_data(client, board, b, {"priority": 5}).status_code == 200
    return board, marks


def test_markers_are_checked_on_the_way_in(client):
    board = _map(client)
    node = _node(client, board["id"], text="Topic")
    assert _set_data(client, board, node, {"priority": 0}).status_code == 422
    assert _set_data(client, board, node, {"priority": 6}).status_code == 422
    assert _set_data(client, board, node, {"progress": 101}).status_code == 422
    assert _set_data(client, board, node, {"markers": ["Star!"]}).status_code == 422
    assert _set_data(client, board, node, {"markers": ["star"] * 7}).status_code == 422


def test_markers_round_trip_through_both_xml_formats_and_survive_a_look_reset(client):
    board, want = _marked_map(client)
    styles = _styles_by_text(client, board["id"])
    assert {k: styles["Pack"].get(k) for k in want} == want
    for fmt in ("opml", "freemind"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert '_priority="2"' in text and '_markers="star,warning"' in text, fmt
        back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt})
        assert back.status_code == 201, back.text
        got = _styles_by_text(client, back.json()["id"])
        assert {k: got["Pack"].get(k) for k in want} == want, fmt
        assert got["Book"].get("priority") == 5, fmt
    markdown = client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    assert "star" not in markdown and "priority" not in markdown.lower()
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    assert _styles_by_text(client, board["id"])["Pack"].get("markers") == ["star", "warning"]


def test_a_due_date_is_a_marker_checked_kept_and_carried(client):
    """MINDMAP_PLAN §12.2 item 4's due date (decision 37): a calendar day,
    content like the other markers (a look reset keeps it), carried by OPML
    and FreeMind as `_due`, never by Markdown."""
    board = _map(client, name="Due")
    root = _node(client, board["id"], text="Plan")
    node = _node(client, board["id"], parent_id=root["id"], text="Book")
    assert _set_data(client, board, node, {"due": "12 October"}).status_code == 422
    assert _set_data(client, board, node, {"due": "2026-10-12T09:00"}).status_code == 422
    assert _set_data(client, board, node, {"due": "2026-10-12"}).status_code == 200
    assert _styles_by_text(client, board["id"])["Book"]["due"] == "2026-10-12"
    for fmt in ("opml", "freemind"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert '_due="2026-10-12"' in text, fmt
        back = client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": fmt})
        assert _styles_by_text(client, back.json()["id"])["Book"].get("due") == "2026-10-12", fmt
    assert "2026-10-12" not in client.get(f"/whiteboard/boards/{board['id']}/export?format=markdown").text
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    assert _styles_by_text(client, board["id"])["Book"]["due"] == "2026-10-12"


def test_a_map_exports_and_imports_as_a_plain_text_outline(client):
    """MINDMAP_PLAN §12.2 item 10: "plain-text outline" out and ".txt
    outline" in. One topic per line, a tab per level, no bullets and no
    title line (a plain outline has no word for one: the file's name is the
    map's, and the client sends it back as `name`). The 101-topic map comes
    back whole."""
    board = _big_map(client, name="Plain")
    first = _structure(client.get(f"/whiteboard/boards/{board['id']}/tree").json()["roots"])
    exported = client.get(f"/whiteboard/boards/{board['id']}/export?format=text")
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/plain")
    assert ".txt" in exported.headers["content-disposition"]
    lines = exported.text.splitlines()
    assert lines[0] == "Centre" and lines[1] == "\tBranch 0" and lines[2] == "\t\tLeaf 0.0"
    assert not any(line.lstrip().startswith(("-", "#")) for line in lines)
    back = client.post(
        "/whiteboard/boards/import",
        json={"format": "text", "content": exported.text, "name": "Plain"},
    )
    assert back.status_code == 201, back.text
    assert back.json()["title"] == "Plain" and back.json()["object_count"] == 101
    second = _structure(client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"])
    assert second == first


def test_a_hand_written_text_outline_imports_by_indentation(client):
    """A .txt from anywhere: spaces or tabs, a numbered line, a bullet left
    in; with no name sent, a single top line names the map."""
    text = "Trip\n  1. Book\n    flights\n  - Pack\n"
    back = client.post("/whiteboard/boards/import", json={"format": "text", "content": text})
    assert back.status_code == 201, back.text
    assert back.json()["title"] == "Trip"
    tree = _structure(client.get(f"/whiteboard/boards/{back.json()['id']}/tree").json()["roots"])
    assert tree == [{"text": "Trip", "children": [
        {"text": "Book", "children": [{"text": "flights", "children": []}]},
        {"text": "Pack", "children": []},
    ]}]
