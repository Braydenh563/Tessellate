"""Source text: UI_MODERNISATION_PLAN 13.2, the Library row: "`filterLibraryImagesGallery`
1,546 lines ... split along the seams (Brief 45)" (L-ui-modernisation-17).

The gallery builds a tile in named steps, each split by job until it is under
the size ratchet's cap, and the steps hang off `filterLibraryImagesGallery.steps`,
so they add no name to the shared scope. (Moved out of a wrapping closure on
2026-11-22: the closure counted as one 1,620-line arrow in tests/js_size_seed.json.)"""

import re

from tests._app_js import frontend_text

STEPS = ("thumb", "caption", "ocr", "visionOcr", "actions", "fields", "usage", "frame")


def _steps() -> str:
    src = frontend_text("library.js")
    start = src.index("filterLibraryImagesGallery.steps = {")
    return src[start : src.index("\n};", start)]


def test_a_tile_is_built_in_named_steps_in_order():
    body = _steps()
    tile = body[body.index("  tile(image, images, grid) {") :]
    calls = re.findall(r"this\.(\w+)\(t\)", tile)
    assert tuple(calls) == STEPS


def test_no_step_is_a_monolith():
    lines = _steps().split("\n")
    starts = [i for i, line in enumerate(lines) if re.match(r"  \w+\(t\) \{", line)]
    assert len(starts) >= len(STEPS)
    for i in starts:
        end = next(j for j in range(i, len(lines)) if lines[j] == "  },")
        assert end - i < 150, lines[i]


def test_the_steps_stay_out_of_the_shared_scope():
    src = frontend_text("library.js")
    assert not re.search(r"^(?:async\s+)?function galleryTile", src, re.M)
    assert not re.search(r"^(?:const|let|var)\s+galleryTile", src, re.M)
    assert re.search(r"^function filterLibraryImagesGallery\(\) \{", src, re.M)
