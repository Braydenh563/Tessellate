"""Source text: UI_MODERNISATION_PLAN 13.2, the Library row: "`filterLibraryImagesGallery`
1,546 lines ... split along the seams (Brief 45)" (L-ui-modernisation-17).

The gallery builds a tile in named steps, each under 320 lines, and the
wrapper adds one name to the shared scope, not one per step."""

import re

from tests._app_js import frontend_text

STEPS = ("Thumb", "Caption", "Ocr", "VisionOcr", "Actions", "Fields", "Usage", "Frame")


def _wrapper() -> str:
    src = frontend_text("library.js")
    start = src.index("const filterLibraryImagesGallery = (() => {")
    return src[start : src.index("\n})();", start)]


def test_a_tile_is_built_in_named_steps_in_order():
    body = _wrapper()
    tile = body[body.index("function galleryTile(image, images, grid)") :]
    calls = re.findall(r"galleryTile(\w+)\(t\)", tile)
    assert tuple(calls) == STEPS


def test_no_step_is_a_monolith():
    lines = _wrapper().split("\n")
    starts = [i for i, l in enumerate(lines) if re.match(r"  function galleryTile\w+\(t\) \{", l)]
    assert len(starts) == len(STEPS)
    for i in starts:
        end = next(j for j in range(i, len(lines)) if lines[j] == "  }")
        assert end - i < 320, lines[i]


def test_the_steps_stay_out_of_the_shared_scope():
    src = frontend_text("library.js")
    assert not re.search(r"^(?:async\s+)?function galleryTile", src, re.M)
    assert "return function filterLibraryImagesGallery()" in _wrapper()
