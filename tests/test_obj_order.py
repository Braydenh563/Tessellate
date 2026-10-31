"""INBOX 1467 part 2: a list's custom order and the arithmetic of a drop
(obj-order.js, obj-reorder.js, obj-drag.js)."""

from __future__ import annotations

import re

from tests._objmove_node import JS, needs_node, run

FILES = ["obj-order.js"]
STUBS = """
const store = {};
globalThis.prefs = { json: (k, d) => (k in store ? store[k] : d), setJSON: (k, v) => { store[k] = v; return true; } };
"""


@needs_node
def test_move_key_puts_the_item_where_it_will_end_up() -> None:
    out = run(FILES, STUBS + """__out([
      objMoveKey(["a","b","c","d"], 0, 2), objMoveKey(["a","b","c","d"], 3, 0),
      objMoveKey(["a","b","c","d"], 1, 1), objMoveKey(["a","b"], 0, 9),
    ])""")
    assert out == [["b", "c", "a", "d"], ["d", "a", "b", "c"], ["a", "b", "c", "d"], ["b", "a"]]


@needs_node
def test_a_slice_is_reordered_in_the_places_it_already_held() -> None:
    out = run(FILES, STUBS + """__out([
      // a page of three out of six: the other three keep their places
      objMergeOrder(["a","x","b","y","c","z"], ["a","b","c"], ["c","a","b"]),
      // nothing stored yet: the visible order becomes the order
      objMergeOrder([], ["a","b","c"], ["b","a","c"]),
      // a visible item the stored order has never seen is placed where it was shown
      objMergeOrder(["a","c"], ["a","b","c"], ["c","b","a"]),
    ])""")
    assert out[0] == ["c", "x", "a", "y", "b", "z"]
    assert out[1] == ["b", "a", "c"]
    assert out[2] == ["c", "b", "a"]


@needs_node
def test_a_brand_new_object_comes_first_and_the_comparator_is_stable() -> None:
    """Moved intent (review 1031): this test used to say "unlisted objects come
    first" because the first reorder of a slice stored only the slice, so every
    note off the page was unlisted and ranked above the ones just arranged. The
    first reorder now stores the whole list, so unlisted means made since."""
    out = run(FILES, STUBS + """
      objOrderSave("docs", ["document:3", "document:1", "document:2"]);
      const items = [{ id: 2 }, { id: 9 }, { id: 1 }, { id: 8 }, { id: 3 }];
      const sorted = items.slice().sort(objOrderCmp("docs", (d) => `document:${d.id}`)).map((d) => d.id);
      __out({ sorted, rank: objOrderRank("docs", "document:1"), none: objOrderRank("docs", "nope") });
    """)
    assert out["sorted"] == [9, 8, 3, 1, 2], "new ones first, in the order they came"
    assert out["rank"] == 1 and out["none"] == -1


@needs_node
def test_a_visible_item_the_order_lacks_is_placed_first_as_it_ranks() -> None:
    out = run(FILES, STUBS + """__out([
      // page one holds a new note on top; the stored order has the rest
      objMergeOrder(["a","b","c","d"], ["n","a","b"], ["a","n","b"]),
    ])""")
    assert out[0] == ["a", "n", "b", "c", "d"]


@needs_node
def test_saving_drops_the_cached_ranks_and_bounds_the_list() -> None:
    out = run(FILES, STUBS + """
      objOrderSave("notes", ["note:1", "note:2"]);
      const first = objOrderRank("notes", "note:2");
      objOrderSave("notes", ["note:2", "note:1"]);
      objOrderSave("big", Array.from({ length: 6000 }, (_, i) => `note:${i}`));
      __out({ first, second: objOrderRank("notes", "note:2"), big: objOrderLoad("big").length });
    """)
    assert out == {"first": 1, "second": 0, "big": 5000}


def _rect(left: int, top: int, w: int = 100, h: int = 40) -> str:
    return f"{{left:{left},top:{top},right:{left + w},bottom:{top + h}}}"


@needs_node
def test_the_insert_index_for_a_column_of_rows() -> None:
    rows = "[" + ",".join(_rect(0, 50 * i) for i in range(4)) + "]"
    out = run(FILES, STUBS + f"""const r = {rows};
      __out([objInsertIndex(r, 50, 5), objInsertIndex(r, 50, 30), objInsertIndex(r, 50, 75), objInsertIndex(r, 50, 400), objInsertIndex([], 5, 5)])""")
    assert out == [0, 1, 2, 4, 0]


@needs_node
def test_the_insert_index_for_a_grid_uses_the_left_half_and_the_gaps_between_rows() -> None:
    cells = "[" + ",".join(_rect(110 * (i % 3), 60 * (i // 3)) for i in range(6)) + "]"
    out = run(FILES, STUBS + f"""const r = {cells};
      __out([objInsertIndex(r, 20, 20), objInsertIndex(r, 80, 20), objInsertIndex(r, 130, 20),
             objInsertIndex(r, 20, 55), objInsertIndex(r, 20, 100), objInsertIndex(r, 300, 80), objInsertIndex(r, 400, 130)])""")
    # left half of 0, right half of 0, left half of 1, the gap above row two (before cell 3), on cell 3's edge, right half of 5, below the last
    assert out == [0, 1, 1, 3, 3, 6, 6]


def test_every_sort_with_a_custom_order_offers_it_and_ranks_by_the_stored_order() -> None:
    html = (JS.parent / "index.html").read_text(encoding="utf-8")
    for select in ("note-sort", "library-docs-sort", "library-boards-sort", "library-media-sort"):
        block = re.search(rf'<select id="{select}".*?</select>', html, re.S).group(0)
        assert '<option value="custom">Custom order</option>' in block, select
    text = "".join((JS / name).read_text(encoding="utf-8") for name in ("library.js", "whiteboard.js", "obj-reorder.js"))
    for scope in ("docs", "boards", "media"):
        assert f'libraryCustomCmp("{scope}"' in text, scope
    assert 'objOrderCmp("notes"' in text


def test_a_drop_only_stores_when_the_place_is_new_and_goes_through_the_undo_contract() -> None:
    reorder = (JS / "obj-reorder.js").read_text(encoding="utf-8")
    drop = reorder[reorder.index("function objReorderDrop") :].split("\n}\n")[0]
    assert "g.index !== g.start" in drop and "objReorderCommit" in drop
    assert "offerUndo(" in reorder, "the move is one Undo"
    drag = (JS / "obj-drag.js").read_text(encoding="utf-8")
    assert "OBJ_DRAG_PX = 4" in drag and "OBJ_DRAG_MS = 250" in drag
    assert '"Escape"' in drag
