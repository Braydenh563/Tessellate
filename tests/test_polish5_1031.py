"""polish5-1031: the leftovers of the 1031 phone, label and Library blind passes.

Each test names the measurement it pins (docs/roadmap/agent-remaining/polish5-1031.md).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_back_to_top_clears_the_floating_new_button_on_a_phone():
    # Measured at 390x844 on Notes: the arrow at y 710 to 754 sat under the New
    # note fab (730 to 774, z 44); `elementFromPoint` at its centre answered the fab.
    src = _src("navigation.js")
    assert 'document.getElementsByClassName("dock-fab")' in src
    body = src[src.index("function aboveDockFab()") :]
    body = body[: body.index("\n}\n")]
    assert "max-width: 599.98px" in body and "r.top" in body
    pos = src[src.index("function positionScrollTopForNested") :]
    pos = pos[: pos.index("\n}\n")]
    assert "aboveDockFab()" in pos


def test_the_boards_picker_face_runs_to_two_lines_on_a_phone():
    # Measured at 390x844 on a 49-character map name: the face had 90px of
    # text and cut at "Quarterly roadmap for ..."; with the side padding given back
    # and a two-line clamp it holds 100px by two lines in the same 44px opener
    # (bar height 54 before and after).
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    block = css[css.index("the board picker's face on a phone") :]
    assert ".wb-topbar .select-shell .select-value" in block
    assert "-webkit-line-clamp: 2" in block
    assert "padding-inline: var(--space-2)" in block


def test_a_spilling_tidy_fits_the_map_on_desktop_and_frames_only_a_narrow_canvas():
    # Review finding: wbMapTidy called wbFrameMapOnOpen, which on desktop jumps
    # a large map to its root at 1:1 instead of fitting it.
    src = _src("whiteboard-map.js")
    tidy = src[src.index("async function wbMapTidy(") :]
    tidy = tidy[: tidy.index("\n}\n")]
    assert "wbFrameSpilledMap()" in tidy and "wbFrameMapOnOpen" not in tidy
    helper = src[src.index("function wbFrameSpilledMap()") :]
    helper = helper[: helper.index("\n}\n")]
    assert "wbMapFrameScales(container).open < 1" in helper
    assert "wbFrameMapOnOpen()" in helper
    assert "wbZoomToFit({ animate: false })" in helper


def test_resetting_shortcuts_waits_for_the_lazy_list():
    # Review finding: renderShortcutList lives in reveal-targets.js, which the
    # reset button can beat to a ReferenceError.
    src = _src("settings-wiring.js")
    body = src[src.index("function resetShortcuts()") :]
    body = body[: body.index("\n}\n")]
    assert 'ensureModule("reveal").then(() => renderShortcutList())' in body
    assert "\n  renderShortcutList();" not in body


def test_a_search_already_on_still_seeds_the_documents_for_the_first_reorder():
    # Measured at 1440 with "a" in the search box before the Library list first
    # drew: `libraryDocsAll` held 0 documents while 4 were shown, so a first
    # reorder stored the visible rows only. After: 4 and 4.
    src = _src("library.js")
    render = src[src.index("async function renderLibraryDocuments()") :]
    render = render[: render.index("\n}\n")]
    assert "if (!needle) libraryDocsAll = docs;" in render
    assert "else if (!libraryDocsAll.length) seedLibraryDocsAll();" in render
    seed = src[src.index("function seedLibraryDocsAll()") :]
    seed = seed[: seed.index("\n}\n")]
    assert 'apiPagedList("/documents", DOCUMENTS_PAGE_SIZE)' in seed
    assert "if (!libraryDocsAll.length) libraryDocsAll = all;" in seed
