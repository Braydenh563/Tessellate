"""Every place that lists a mind map topic's shape lists the same shapes.

The shape set lives in five places: the API's validation (`WhiteboardObjectData.shape`,
`MAP_THEME_FIELDS`, `MAP_LEVEL_FIELDS`), the strip's `<select id="wb-map-shape">`
in index.html, the per-level and theme pickers in whiteboard-map.js, the picker
glyphs, and the stylesheet. Adding Chevron and Underline (K15) found the strip's
select still at nine, so a template could store a shape its own menu could not
show; and a nine-wide row of previews that never wrapped had pushed Cloud and
Plain past the menu's edge (measured at 1440: 306px in a 220px cell).
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.routes_whiteboard import MAP_LEVEL_FIELDS, MAP_THEME_FIELDS, WhiteboardObjectData

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
BOOT_CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")

#: What a topic can be drawn in, as the object data accepts it.
_PATTERN = next(m.pattern for m in WhiteboardObjectData.model_fields["shape"].metadata if hasattr(m, "pattern"))
SHAPES = set(re.search(r"\^\((.*?)\)\$", _PATTERN).group(1).split("|"))


def test_the_api_accepts_the_same_shapes_everywhere():
    assert {"chevron", "underline"} <= SHAPES
    assert SHAPES - {"rounded"} == set(MAP_THEME_FIELDS["shape"])
    assert SHAPES == set(MAP_LEVEL_FIELDS["shape"])


def test_the_strips_box_select_offers_every_shape():
    block = re.search(r'<select id="wb-map-shape".*?</select>', HTML, re.S).group(0)
    offered = {v or "rounded" for v in re.findall(r'<option value="([^"]*)"', block)}
    assert offered == SHAPES, offered ^ SHAPES


def test_the_pickers_and_their_glyphs_know_every_shape():
    glyphs = re.search(r'"wb-map-shape": \{(.*?)\},\n', MAP_JS, re.S).group(1)
    keys = set(re.findall(r'(\w+): "svg:', glyphs))
    assert SHAPES <= keys, SHAPES - keys
    for shape in SHAPES - {"rounded"}:
        assert f'["{shape}", ' in MAP_JS, shape


def test_every_shape_but_the_card_ones_has_a_stylesheet_rule():
    for shape in SHAPES - {"rounded"}:
        assert f'data-shape="{shape}"' in BOOT_CSS + LAZY_CSS, shape


def test_a_long_row_of_previews_is_a_grid_not_a_run():
    """Nine previews in one never-wrapping run were wider than the menu."""
    assert 'select.options.length > 7) row.classList.add("is-grid")' in MAP_JS
