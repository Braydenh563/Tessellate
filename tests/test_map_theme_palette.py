"""The rest of a map's own look (MINDMAP_PLAN.md §13e, decisions 8 and 9).

Three things the first half of the theme left open, each gated here:

- **a branch palette a person picks**, drawn in two places (the canvas and
  the Library thumbnail). Decision 8 asked that the two be one: the server's
  `MAP_BRANCH_PALETTES` is the only list, `/tree` hands the resolved colours
  to the canvas, and the thumbnail and its cache key read the same name;
- **a font for the whole map**, a map-level fact like the palette, so neither
  is ever written onto a topic's style on the way out to a file;
- **decision 9's narrow case**: a topic on a themed map can be pulled back to
  the app's own default for a field the map themes. Each such field has a
  stored name for its default (`MAP_APP_DEFAULT_PINS`), which beats the theme
  the way any value a topic carries does, and which an export writes as the
  absence it means.
"""

from __future__ import annotations

from tests._app_js import frontend_text
from tessellate.api.routes_whiteboard import (
    MAP_APP_DEFAULT_PINS,
    MAP_BRANCH_PALETTE,
    MAP_BRANCH_PALETTES,
    _themed_style,
)


def _map(client, name="Palette map"):
    board = client.post(
        "/whiteboard/boards", json={"name": name, "type": "map", "layout": "tree-right"}
    )
    assert board.status_code == 201, board.text
    return board.json()


def _node(client, board_id, *, parent_id=None, text=""):
    created = client.post(
        f"/whiteboard/boards/{board_id}/nodes",
        json={"kind": "topic", "parent_id": parent_id, "text": text},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _theme(client, board_id, patch):
    saved = client.put(f"/whiteboard/boards/{board_id}", json={"theme": patch})
    assert saved.status_code == 200, saved.text


def _tree(client, board_id):
    return client.get(f"/whiteboard/boards/{board_id}/tree").json()


def _put_data(client, board_id, node, patch):
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


def _preview(client, board_id):
    boards = client.get("/whiteboard/boards").json()
    row = next(b for b in boards if b["id"] == board_id)
    return {i["label"]: i for i in row["preview_items"]}


# --- the palette --------------------------------------------------------------


def test_the_classic_palette_is_the_one_every_map_had():
    """An unthemed map draws exactly what it drew before a palette could be
    picked: the classic list is `MAP_BRANCH_PALETTE`, unchanged."""
    assert MAP_BRANCH_PALETTES["classic"] == MAP_BRANCH_PALETTE
    assert len(MAP_BRANCH_PALETTE) == 10
    for name, colours in MAP_BRANCH_PALETTES.items():
        assert len(colours) >= 8, name
        assert len(set(colours)) == len(colours), name


def test_eight_curated_palettes_and_the_picker_offers_each():
    """MINDMAP_PLAN §12.2 item 7: "auto-colour by branch ... with eight
    curated palettes". Every stored name is one the theme accepts, and the
    canvas's picker offers exactly the server's names (no colour lives in
    the client), so a palette added on one side is never missing on the
    other."""
    import re

    from tessellate.api.routes_whiteboard import MAP_THEME_FIELDS

    assert len(MAP_BRANCH_PALETTES) == 8
    assert set(MAP_BRANCH_PALETTES) - {"classic"} == set(MAP_THEME_FIELDS["palette"])
    js = frontend_text("whiteboard-map.js")
    block = js[js.index('key: "palette"'):]
    block = block[: block.index("] },")]
    offered = set(re.findall(r'\["([a-z]*)", "', block))
    assert offered == (set(MAP_BRANCH_PALETTES) - {"classic"}) | {""}


def test_every_palette_colour_is_a_line_on_the_light_paper():
    """A branch colour is drawn as a 3px line on the page; one that nearly
    vanishes on white (Set1's yellow, Pastel's tints) is not curated. The four
    added 2026-10-05 hold 1.6:1 against white at least; the first four are
    what maps already wear and are pinned as they are."""
    def lum(hex_colour):
        rgb = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    for name in ("bold", "paired", "bright", "earth"):
        for colour in MAP_BRANCH_PALETTES[name]:
            assert 1.05 / (lum(colour) + 0.05) >= 1.6, (name, colour)


def test_the_tree_hands_the_canvas_its_resolved_palette(client):
    """The canvas no longer keeps its own copy: `/tree` says which colours."""
    board = _map(client)
    assert _tree(client, board["id"])["palette"] == MAP_BRANCH_PALETTES["classic"]
    _theme(client, board["id"], {"palette": "deep"})
    tree = _tree(client, board["id"])
    assert tree["theme"] == {"palette": "deep"}
    assert tree["palette"] == MAP_BRANCH_PALETTES["deep"]


def test_an_unknown_palette_or_font_is_dropped(client):
    board = _map(client)
    _theme(client, board["id"], {"palette": "neon", "font": "comic", "shape": "pill"})
    assert _tree(client, board["id"])["theme"] == {"shape": "pill"}


def test_the_thumbnail_draws_the_picked_palette_and_its_cache_notices(client):
    """The second of decision 8's two places. A thumbnail cached under the old
    palette is the bug this would be without the name in the cache key: the
    board's rows did not change, only its settings."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    _node(client, board["id"], parent_id=root["id"], text="One")
    _node(client, board["id"], parent_id=root["id"], text="Two")
    before = _preview(client, board["id"])
    assert before["One"]["color"] == MAP_BRANCH_PALETTES["classic"][0]

    _theme(client, board["id"], {"palette": "soft"})
    after = _preview(client, board["id"])
    assert after["One"]["color"] == MAP_BRANCH_PALETTES["soft"][0]
    assert after["Two"]["color"] == MAP_BRANCH_PALETTES["soft"][1]

    _theme(client, board["id"], {"palette": None})
    assert _preview(client, board["id"])["One"]["color"] == MAP_BRANCH_PALETTES["classic"][0]


# --- the font -------------------------------------------------------------------


def test_a_font_is_stored_and_read_back(client):
    board = _map(client)
    _theme(client, board["id"], {"font": "serif"})
    assert _tree(client, board["id"])["theme"] == {"font": "serif"}
    _theme(client, board["id"], {"font": None})
    assert _tree(client, board["id"])["theme"] == {}


def test_the_map_level_fields_never_land_on_a_topic():
    """A palette and a font describe the map; a file's node has no place for
    either, and a re-import would otherwise read them back as a topic's own."""
    filled = _themed_style({"bold": True}, {"palette": "deep", "font": "mono", "shape": "pill"})
    assert filled == {"bold": True, "shape": "pill"}


def test_an_export_of_a_map_with_a_palette_and_font_writes_neither(client):
    board = _map(client)
    _node(client, board["id"], text="Root")
    _theme(client, board["id"], {"palette": "vivid", "font": "serif"})
    for fmt in ("freemind", "opml"):
        text = client.get(f"/whiteboard/boards/{board['id']}/export?format={fmt}").text
        assert "vivid" not in text and "serif" not in text, fmt


# --- decision 9: back to the app's own default -------------------------------


def test_every_themed_select_field_has_a_stored_name_for_the_apps_default():
    """The theme's select fields, less the two map-level ones, each need one,
    or that field is the case decision 9 recorded as unsolved."""
    assert set(MAP_APP_DEFAULT_PINS) == {"font_size", "align", "shape", "spine", "edge_width", "edge_style"}


def test_a_topic_pinned_to_the_apps_default_keeps_it_against_the_theme(client):
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    pinned = _node(client, board["id"], parent_id=root["id"], text="Pinned")
    patch = {field: value for field, value in MAP_APP_DEFAULT_PINS.items()}
    saved = _put_data(client, board["id"], pinned, patch)
    assert saved.status_code == 200, saved.text
    _theme(
        client,
        board["id"],
        {"shape": "pill", "spine": "dashed", "align": "center", "font_size": 19,
         "edge_width": "thick", "edge_style": "elbow"},
    )
    child = _tree(client, board["id"])["roots"][0]["children"][0]
    for field, value in MAP_APP_DEFAULT_PINS.items():
        assert child["style"].get(field) == value, field
    # Resolved for paint, the pin is what the topic draws, never the theme.
    drawn = _themed_style(child["style"], _tree(client, board["id"])["theme"])
    assert drawn["shape"] == "rounded"
    assert drawn["edge_width"] == "normal"


def test_an_export_writes_a_pin_as_the_default_it_names(client):
    """A file has no word for "the app's own, against a theme": it says the
    default by saying nothing, which is what the pin means."""
    board = _map(client)
    root = _node(client, board["id"], text="Root")
    pinned = _node(client, board["id"], parent_id=root["id"], text="Pinned")
    assert _put_data(client, board["id"], pinned, {"shape": "rounded", "font_size": 0}).status_code == 200
    _theme(client, board["id"], {"shape": "pill", "font_size": 25})
    text = client.get(f"/whiteboard/boards/{board['id']}/export?format=freemind").text
    assert "rounded" not in text
    assert 'SIZE="0"' not in text
    # The root follows the theme, so the theme still reaches the file.
    assert 'shape="pill"' in text


def test_a_tiny_font_size_is_still_refused(client):
    """0 is the pin; 1 to 7 are a map nobody can read, refused as before."""
    board = _map(client)
    node = _node(client, board["id"], text="Root")
    assert _put_data(client, board["id"], node, {"font_size": 4}).status_code == 422
    assert _put_data(client, board["id"], node, {"font_size": 0}).status_code == 200
