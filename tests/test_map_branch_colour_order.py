"""The owner, 2026-10-10: "when I added a mindmap node in between, it changed
the colour of the other nodes in the branch". A topic put between a root and
its child is the newest id on the map; ordered by its own id, its branch went
to the end of the palette and every branch after it shifted. A branch is as
old as its oldest topic (whiteboard-map.js `wbMapColors` agrees)."""

from tessellate.api.routes_whiteboard import MAP_BRANCH_PALETTE, _map_branch_colors


def test_an_untouched_map_colours_its_branches_in_order():
    parents = {1: None, 2: 1, 3: 1, 4: 1, 5: 2}
    colours = _map_branch_colors(parents, {})
    assert [colours[i] for i in (2, 3, 4)] == MAP_BRANCH_PALETTE[:3]
    assert colours[5] == colours[2]


def test_a_topic_inserted_between_keeps_every_branch_its_colour():
    before = _map_branch_colors({1: None, 2: 1, 3: 1, 4: 1, 5: 3}, {})
    # 9 is put between the root and 3: 3 (with 5 under it) now hangs off 9.
    # In id order, as the rows are read.
    after = _map_branch_colors({1: None, 2: 1, 3: 9, 4: 1, 5: 3, 9: 1}, {})
    for node in (2, 3, 4, 5):
        assert after[node] == before[node], node
    assert after[9] == before[3]


def test_a_cycle_still_ends():
    colours = _map_branch_colors({1: None, 2: 3, 3: 2, 4: 1}, {})
    assert colours[4] == MAP_BRANCH_PALETTE[0]


def test_rainbow_colours_every_level_by_sibling_and_never_repeats_its_parent():
    # Rainbow every level (F3, MINDMAP_PLAN gap 10): a theme option, so the thumbnail agrees with the canvas.
    parents = {1: None, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 4}
    plain = _map_branch_colors(parents, {})
    assert plain[4] == plain[2] == plain[5]
    rainbow = _map_branch_colors(parents, {}, None, rainbow=True)
    assert [rainbow[i] for i in (2, 3)] == MAP_BRANCH_PALETTE[:2]
    assert len({rainbow[4], rainbow[5], rainbow[6]}) == 3
    for child, parent in ((4, 2), (5, 2), (6, 2), (7, 4)):
        assert rainbow[child] != rainbow[parent], child


def test_a_node_with_its_own_colour_still_wins_under_rainbow():
    rainbow = _map_branch_colors({1: None, 2: 1, 3: 2}, {3: "#123456"}, None, rainbow=True)
    assert rainbow[3] == "#123456"


def test_rainbow_is_a_map_level_boolean_theme_field():
    from tessellate.api.wb_board import _clean_theme
    from tessellate.api.wb_model import MAP_LEVEL_THEME_FIELDS

    assert _clean_theme({"rainbow": True}) == {"rainbow": True}
    assert _clean_theme({"rainbow": False}) == {}
    assert "rainbow" in MAP_LEVEL_THEME_FIELDS
