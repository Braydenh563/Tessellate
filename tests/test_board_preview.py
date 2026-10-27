"""A board's thumbnail: its shape, its branch colours, and the cache.

The picture on a Library card used to be a scatter of one-grey dots in a box
the shape of the card rather than the shape of the board, recomputed from
scratch on every visit. This file gates the three things that changed:

- **aspect**, so the miniature is letterboxed at the board's own ratio
  instead of stretched (`preview_aspect`, drawn by `mapPreview` in app.js);
- **colour**, so a map's thumbnail is the same picture as its canvas, branch
  by branch (`MAP_BRANCH_PALETTE`, Coggle's rule, which `wbMapColors`
  implements client-side);
- **the cache**, which is invisible in the response by construction: an
  identical answer is exactly what a cache is for, so the only way to assert
  it is the counter it keeps (`PREVIEW_CACHE_STATS`).

The staleness cases have their own tests here, because a preview cache that
serves the old picture is worse than no cache at all: the board a person is
looking at is the one they just changed.
"""

from __future__ import annotations

from tessellate.api.routes_whiteboard import (
    MAP_BRANCH_PALETTE,
    PREVIEW_ASPECT_RANGE,
    PREVIEW_CACHE_STATS,
    _preview_fields,
)


def _map(client, name="Shape map"):
    board = client.post(
        "/whiteboard/boards", json={"name": name, "type": "map", "layout": "tree-right"}
    )
    assert board.status_code == 201, board.text
    return board.json()


def _node(client, board_id, *, parent_id=None, text="", x=None, y=None, color=None):
    body = {"kind": "topic", "parent_id": parent_id, "text": text}
    if x is not None:
        body["x"], body["y"] = x, y
    if color is not None:
        body["color"] = color
    created = client.post(f"/whiteboard/boards/{board_id}/nodes", json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _row(client, board_id):
    boards = client.get("/whiteboard/boards").json()
    return next(b for b in boards if b["id"] == board_id)


# --- aspect -----------------------------------------------------------------


def test_a_wide_board_reports_a_wide_thumbnail(client):
    """The number the client letterboxes with. Two nodes 400 apart across and
    100 apart down is a board twice as wide as it is tall, and that is the
    one fact normalising into 0..1 destroys."""
    board = _map(client)
    _node(client, board["id"], text="left", x=0, y=0)
    _node(client, board["id"], text="right", x=400, y=200)
    assert _row(client, board["id"])["preview_aspect"] == 2.0


def test_a_tall_board_reports_a_tall_thumbnail(client):
    board = _map(client)
    _node(client, board["id"], text="top", x=0, y=0)
    _node(client, board["id"], text="bottom", x=100, y=150)
    assert _row(client, board["id"])["preview_aspect"] == round(100 / 150, 3)


def test_an_extreme_board_is_clamped_rather_than_drawn_as_a_sliver(client):
    """A board 40 times wider than it is tall, drawn honestly, is a two-pixel
    band inside an otherwise empty card: past the clamp the ratio has stopped
    being information about the board."""
    board = _map(client)
    _node(client, board["id"], text="left", x=0, y=0)
    _node(client, board["id"], text="far", x=4000, y=100)
    assert _row(client, board["id"])["preview_aspect"] == PREVIEW_ASPECT_RANGE[1]


def test_a_single_node_keeps_the_square(client):
    """One node has no extent on either axis. The alternative to the square is
    a divide by zero or a shape invented out of a rounding error."""
    board = _map(client)
    _node(client, board["id"], text="only", x=10, y=10)
    assert _row(client, board["id"])["preview_aspect"] == 1.0


# --- colour -----------------------------------------------------------------


def test_each_first_level_branch_takes_the_next_palette_colour(client):
    """Coggle's rule, which the canvas already follows: the colour starts at
    the branch, not at the root, or the whole map is one colour."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], text="One")
    _node(client, board["id"], parent_id=root["id"], text="Two")

    items = {i["label"]: i for i in _row(client, board["id"])["preview_items"]}
    assert "color" not in items["Root"]
    assert items["One"]["color"] == MAP_BRANCH_PALETTE[0]
    assert items["Two"]["color"] == MAP_BRANCH_PALETTE[1]


def test_a_descendant_inherits_its_branch(client):
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    branch = _node(client, board["id"], parent_id=root["id"], text="Branch")
    _node(client, board["id"], parent_id=branch["id"], text="Leaf")

    items = {i["label"]: i for i in _row(client, board["id"])["preview_items"]}
    assert items["Leaf"]["color"] == items["Branch"]["color"] == MAP_BRANCH_PALETTE[0]


def test_a_nodes_own_colour_wins_and_carries_down(client):
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    branch = _node(client, board["id"], parent_id=root["id"], text="Branch", color="#123456")
    _node(client, board["id"], parent_id=branch["id"], text="Leaf")

    items = {i["label"]: i for i in _row(client, board["id"])["preview_items"]}
    assert items["Branch"]["color"] == "#123456"
    assert items["Leaf"]["color"] == "#123456"


def test_an_ordinary_board_ships_no_colours(client):
    """Colour on a board would be a claim about structure it does not have,
    and `color` is omitted rather than sent as null: a twenty-board list ships
    eight hundred of these items."""
    board = client.post("/whiteboard/boards", json={"name": "Plain"}).json()
    client.post(
        "/whiteboard/objects",
        json={"kind": "text", "board_id": board["id"], "data": {"content": "hi"}},
    )
    items = _row(client, board["id"])["preview_items"]
    assert items and all("color" not in item for item in items)


# --- the cache --------------------------------------------------------------


def test_the_second_board_list_draws_from_the_cache(client):
    """The Library rebuilds every thumbnail on every visit, and a thumbnail is
    a full scan of the board. The second visit to an unchanged board must not
    pay for it again."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], text="Child")

    first = _row(client, board["id"])
    before = dict(PREVIEW_CACHE_STATS)
    second = _row(client, board["id"])

    assert PREVIEW_CACHE_STATS["hits"] > before["hits"]
    assert PREVIEW_CACHE_STATS["misses"] == before["misses"]
    assert second["preview_items"] == first["preview_items"]
    assert second["preview_edges"] == first["preview_edges"]
    assert second["preview_aspect"] == first["preview_aspect"]


def test_moving_a_node_redraws_the_thumbnail(client):
    """The staleness case that matters most: the board someone is looking at
    is the board they just changed."""
    board = _map(client)
    root = _node(client, board["id"], text="Root", x=0, y=0)
    _node(client, board["id"], parent_id=root["id"], text="Child", x=100, y=100)
    before = _row(client, board["id"])["preview_aspect"]

    moved = client.put(
        f"/whiteboard/objects/{root['id']}",
        json={
            "kind": "topic",
            "board_id": board["id"],
            "data": {"content": "Root"},
            "x": 0.0,
            "y": -300.0,
        },
    )
    assert moved.status_code == 200, moved.text
    assert _row(client, board["id"])["preview_aspect"] != before


def test_renaming_a_note_redraws_the_card_that_stands_for_it(client):
    """A card's label is the note's title, and renaming a note touches nothing
    on the board at all: the fingerprint has to reach through to the entry or
    the Library shows the old name until something else changes."""
    note = client.post("/entries", json={"content": "# First name\n\nBody"}).json()
    board = client.post("/whiteboard/boards", json={"name": "Cards"}).json()
    placed = client.post(
        "/whiteboard/nodes",
        json={"entry_id": note["id"], "board_id": board["id"], "x": 0, "y": 0},
    )
    assert placed.status_code == 200, placed.text
    assert _row(client, board["id"])["preview_items"][0]["label"] == "First name"

    client.put(f"/entries/{note['id']}", json={"content": "# Second name\n\nBody"})
    assert _row(client, board["id"])["preview_items"][0]["label"] == "Second name"


def test_the_cached_lists_are_copied_on_the_way_out(client, session):
    """A caller that mutates a preview in place would otherwise poison every
    board list drawn after it, and the fault would surface somewhere else
    entirely."""
    board = _map(client)
    _node(client, board["id"], text="Root")

    first = _preview_fields(session, board["id"])
    first["preview_items"][0]["label"] = "mutated"
    assert _preview_fields(session, board["id"])["preview_items"][0]["label"] == "Root"
    assert _row(client, board["id"])["preview_items"][0]["label"] == "Root"


def test_a_sketch_is_previewed_where_it_was_drawn_at_the_size_it_was_drawn():
    """INBOX 164's "one squiggle", as the two numbers behind it.

    A sketch has no width or height columns and its `x`/`y` are **zero** for
    every stroke the drawing tools make: the path is written in absolute board
    coordinates (see the save in whiteboard.js). So a preview that read the row
    put every sketch on a board at the board's origin at one default size, and
    eight shapes drawn across a board painted as a single mark in the corner.
    Measured before the fix, on a board with eight of them: eight marks at one
    position and one size.

    `_sketch_preview` reads the path instead, the way the canvas does
    (`wbItemBBox`), and also carries the tool and the ink, which is what lets
    the thumbnail draw a rectangle as a rectangle rather than one generic wave.
    """
    from tessellate.api.routes_whiteboard import _sketch_preview

    class Row:
        def __init__(self, data, x=0.0, y=0.0):
            self.data, self.x, self.y = data, x, y

    line = _sketch_preview(
        Row('{"d": "M340 120 L520 200", "shape": "line", "color": "#d97706"}')
    )
    assert line == (340.0, 120.0, 180.0, 80.0, "line", "#d97706")

    # The ellipse tool's two half-arcs, the one curve shape the canvas's own
    # bbox reader is exact for.
    circle = _sketch_preview(
        Row('{"d": "M600 300 a90 60 0 1 0 180 0 a90 60 0 1 0 -180 0", "shape": "circle"}')
    )
    assert circle[:4] == (600.0, 240.0, 180.0, 120.0)
    assert circle[4] == "circle" and circle[5] is None

    # A stroke that was dragged after it was drawn carries the offset on the
    # row, and the canvas adds the two: so does this.
    moved = _sketch_preview(Row('{"d": "M0 0 L40 40"}', x=100.0, y=50.0))
    assert moved[:4] == (100.0, 50.0, 40.0, 40.0)

    # A horizontal line has a zero-height box, and a zero-height box normalises
    # to nothing and draws nothing: the floor is there so a drawing is never
    # left out of a picture of the drawing.
    flat = _sketch_preview(Row('{"d": "M10 10 L90 10"}'))
    assert flat[2] == 80.0 and flat[3] >= 8.0

    # Unreadable data is not a crash and not an empty board: it falls back to
    # the row's own position and the default size, which is what every sketch
    # used to get.
    for bad in ("", "{", '{"d": ""}', '{"d": "nonsense"}', "null"):
        fallback = _sketch_preview(Row(bad, x=7.0, y=9.0))
        assert fallback[0] == 7.0 and fallback[1] == 9.0
        assert fallback[2] > 0 and fallback[3] > 0


def test_the_preview_carries_the_shape_a_sketch_was_drawn_with(client):
    """The whole payload, end to end: a board with one rectangle and one pen
    stroke previews as two marks with their own shapes, not two of one."""
    board = client.post("/whiteboard/boards", json={"name": "Drawn on"}).json()
    for data in (
        '{"d": "M860 60 L1100 60 L1100 200 L860 200 Z", "shape": "rect", "color": "#d97706"}',
        '{"d": "M100 400 L140 360 L180 420", "shape": "draw"}',
    ):
        made = client.post(
            "/whiteboard/sketches",
            json={"board_id": board["id"], "x": 0, "y": 0, "z": 5, "data": data},
        )
        assert made.status_code in (200, 201), made.text

    items = _row(client, board["id"])["preview_items"]
    shapes = sorted(item.get("shape") for item in items)
    assert shapes == ["draw", "rect"], items
    # Two different places and two different sizes, which is the report.
    assert len({(item["x"], item["y"]) for item in items}) == 2, items
    assert len({(item.get("w"), item.get("h")) for item in items}) == 2, items
    # The ink travels with the stroke that has one, and is omitted for the one
    # that does not: a twenty-board list would otherwise ship hundreds of nulls.
    assert [item.get("color") for item in items].count("#d97706") == 1
    assert any("color" not in item for item in items)


def test_a_caption_steps_around_sketched_shapes_too():
    """The dashboard's board drew "Store rev…" and "Next" across its sketched
    shapes: the label pass tested captions against cards only. Sketches are
    obstacles now, and never carry a caption of their own."""
    from tests._app_js import app_js_text

    js = app_js_text()
    assert '    drawn.push({ item, x: nx, y: ny, w: size.w, h: size.h });' in js
    assert 'row.item.kind !== "sketch")' in js


def test_a_straight_link_previews_as_a_line_between_what_it_joins(client):
    """dog2 item 14: a link has no `d`, so it fell to the default box at the
    origin and drew as a pen scribble. It is a line from one joined shape's
    centre to the other's, and a rising one says so."""
    board = client.post("/whiteboard/boards", json={"name": "Joined"}).json()

    def sketch(data):
        made = client.post(
            "/whiteboard/sketches",
            json={"board_id": board["id"], "x": 0, "y": 0, "z": 5, "data": data},
        )
        assert made.status_code in (200, 201), made.text
        return made.json()["id"]

    a = sketch('{"d": "M100 400 L220 400 L220 460 L100 460 Z", "shape": "rect"}')
    b = sketch('{"d": "M500 100 L620 100 L620 160 L500 160 Z", "shape": "rect"}')
    sketch(
        '{"type": "link-straight", "sourceId": %d, "sourceKind": "sketch", '
        '"targetId": %d, "targetKind": "sketch", "color": "#111111"}' % (a, b)
    )
    sketch('{"type": "link-straight", "sourceId": 99999, "sourceKind": "sketch", "targetPoint": {"x": 1, "y": 2}}')
    # Level: centre (160, 430) to a free end at (700, 432).
    sketch('{"type": "link-straight", "sourceId": %d, "sourceKind": "sketch", "targetPoint": {"x": 700, "y": 432}}' % a)

    items = _row(client, board["id"])["preview_items"]
    shapes = sorted(item.get("shape") for item in items)
    # The dangling link (its source is gone) is left out, never a scribble.
    assert shapes == ["line-flat", "line-rise", "rect", "rect"], items
    line = next(item for item in items if item.get("shape") == "line-rise")
    assert line["color"] == "#111111"
    # Centre (160, 430) to centre (560, 130): it starts at the left shape's
    # middle, so its box begins inside the left rectangle, not at the origin.
    left = min((item for item in items if item.get("shape") == "rect"), key=lambda i: i["x"])
    assert line["x"] > left["x"] and line["y"] < left["y"] + left["h"]
