"""INBOX 607: a mind map made from the graph is built from the graph.

The owner: "this is how it made the map, surely there's a better and more
dynamic way it can build the map based off the connections and links and
relevancy etc??" (one root, 33 children in a column), and "the notification
included no link to it". The tree: a central note as the root, linked notes
under the note they link to, what is not linked grouped by category, an
overfull hub split by category, and every link that does not fit the tree
kept as a cross-link. Laid out on both sides, balanced by weight.
"""

from __future__ import annotations

from tessellate.api.routes_map_from_notes import MAX_FANOUT, build_tree, layout_both_sides


def _note(i, category="Work", tags=()):
    return {"id": i, "title": f"Note {i}", "category": category, "tags": list(tags)}


def _flat(node, out=None, depth=0):
    out = [] if out is None else out
    out.append((node, depth))
    for child in node["children"]:
        _flat(child, out, depth + 1)
    return out


def _parent_of(tree):
    parents = {}
    for node, _ in _flat(tree):
        for child in node["children"]:
            parents[child.get("note") or child["text"]] = node.get("note") or node["text"]
    return parents


def test_the_most_connected_note_is_the_root_and_links_hang_under_it():
    notes = [_note(i) for i in range(1, 7)]
    # 3 is the hub; 5 links only to 4, which links to the hub.
    edges = [(3, 1), (3, 2), (3, 4), (4, 5), (1, 2)]
    tree = build_tree(notes, edges, name="Map")
    assert tree["note"] == 3
    parents = _parent_of(tree)
    assert parents[1] == 3 and parents[2] == 3 and parents[4] == 3
    assert parents[5] == 4, "a linked note sits under the note it links to"
    # 1-2 is not a tree edge: it is kept as a cross-link, once.
    refs = {node["ref"]: node.get("note") for node, _ in _flat(tree)}
    crossed = {(refs[node["ref"]], refs[target]) for node, _ in _flat(tree) for target in node.get("links", [])}
    assert crossed in ({(1, 2)}, {(2, 1)})
    # 6 is linked to nothing: it is still on the map, exactly once.
    ids = [node.get("note") for node, _ in _flat(tree) if node.get("note")]
    assert sorted(ids) == [1, 2, 3, 4, 5, 6]


def test_a_picked_root_wins():
    notes = [_note(i) for i in range(1, 5)]
    tree = build_tree(notes, [(1, 2), (1, 3), (3, 4)], root_id=4, name="Map")
    assert tree["note"] == 4
    assert _parent_of(tree)[3] == 4


def test_unlinked_notes_branch_by_category_under_a_named_root():
    notes = [_note(i, "Work") for i in range(1, 6)] + [_note(i, "Home") for i in range(6, 9)]
    tree = build_tree(notes, [], name="Everything")
    assert tree.get("note") is None and tree["text"] == "Everything"
    branches = {child["text"]: child for child in tree["children"]}
    assert set(branches) == {"Work", "Home"}
    assert len(branches["Work"]["children"]) == 5
    assert len(branches["Home"]["children"]) == 3


def test_thirty_three_unlinked_notes_are_not_one_column():
    # The owner's case: one category, no links. Grouped by tag where the tags
    # say something; never 33 children of one node.
    notes = [_note(i, "Inbox", tags=(f"t{i % 4}",)) for i in range(1, 34)]
    tree = build_tree(notes, [], name="test")
    widest = max(len(node["children"]) for node, _ in _flat(tree))
    assert widest <= MAX_FANOUT + 4, widest
    ids = [node.get("note") for node, _ in _flat(tree) if node.get("note")]
    assert sorted(ids) == list(range(1, 34))


def test_an_overfull_hub_is_split_by_category():
    notes = [_note(1, "Hub")] + [_note(i, "A" if i % 2 else "B") for i in range(2, 22)]
    edges = [(1, i) for i in range(2, 22)]
    tree = build_tree(notes, edges, name="Map")
    assert tree["note"] == 1
    assert len(tree["children"]) <= MAX_FANOUT
    texts = sorted(child["text"] for child in tree["children"])
    assert texts == ["A", "B"]


def test_layout_is_balanced_on_both_sides_and_never_overlaps():
    notes = [_note(i, "A" if i < 12 else "B" if i < 24 else "C") for i in range(1, 34)]
    tree = build_tree(notes, [], name="Map")
    pos = layout_both_sides(tree)
    root_x = pos[tree["ref"]][0]
    left = sum(1 for ref, (x, _) in pos.items() if x < root_x)
    right = sum(1 for ref, (x, _) in pos.items() if x > root_x)
    assert left and right and abs(left - right) <= 12, (left, right)
    # Same column, distinct rows: no two topics on one spot.
    spots = {(round(x), round(y)) for x, y in pos.values()}
    assert len(spots) == len(pos)


def test_the_route_makes_the_map_and_its_cross_links(client):
    ids = []
    for text, category in [("Hub note", "Work"), ("Spoke one", "Work"), ("Spoke two", "Work"), ("Loose", "Home")]:
        r = client.post("/entries", json={"content": f"# {text}\n\nbody", "category": category, "defer_filing": True})
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])
    hub, one, two, loose = ids
    r = client.post(
        "/whiteboard/maps/from-notes",
        json={"name": "From the graph", "note_ids": ids, "edges": [[hub, one], [hub, two], [one, two]]},
    )
    assert r.status_code == 201, r.text
    board = r.json()
    assert board["type"] == "map" and board["layout"] == "tree-both"
    assert board["object_count"] == 4  # one loose note joins the root directly
    state = client.get("/whiteboard/", params={"board_id": board["id"]}).json()
    objects = state["objects"]
    by_ref = {o["data"].get("ref_id"): o for o in objects}
    assert by_ref[hub]["parent_id"] is None
    assert by_ref[one]["parent_id"] == by_ref[hub]["id"]
    assert by_ref[loose]["parent_id"] == by_ref[hub]["id"]
    #: Each object gets its own node's place, not its neighbour's: the root
    #: in the middle, its children a column out on either side.
    assert (by_ref[hub]["x"], by_ref[hub]["y"]) == (0, 0)
    assert {abs(by_ref[i]["x"]) for i in (one, loose)} == {300}
    links = [s for s in state["sketches"] if "sourceId" in str(s["data"])]
    assert len(links) == 1, "the one link the tree could not hold is a cross-link"


def test_the_route_refuses_nothing_to_map(client):
    r = client.post("/whiteboard/maps/from-notes", json={"name": "x", "note_ids": [999999]})
    assert r.status_code == 422


def test_topic_text_is_linear_on_bracket_runs():
    """CodeQL (PR 192): "[" or "[](" repeated made the link pattern quadratic."""
    import time

    from tessellate.api.routes_map_from_notes import _topic_text

    assert _topic_text("see [the plan](http://x) and ![img](a.png)") == "see the plan and img"
    for bait in ("[\\" * 20000, "[](" * 20000):
        started = time.perf_counter()
        _topic_text(bait)
        assert time.perf_counter() - started < 0.5
