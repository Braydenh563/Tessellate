"""The image viewer's layout (§ lightbox).

Reported with two screenshots after the first version of the info panel
shipped:

    "the lightbox arrow icons in are not centred, same with the caption and
     ocr text at the bottom. is the lightbox scrollable?? maybe it can have
     the image information and other info about it below the image with the
     caption and ocr text??"

All three were the same cause. `.lightbox` was a fixed, non-scrolling box with
`place-content: center`, which centres a column and then clips whatever does
not fit: at both ends. Adding a caption panel made the column taller than the
viewport, so the panel was cut off with no way to scroll to it, and the arrows
(`position: fixed; top: 50%`) were centred on the viewport rather than on an
image that was no longer in the middle of it.

These are lints: nothing here renders a page. They pin the structure that
makes the geometry correct without measuring, so it cannot silently regress
the way the JS-measured version did.
"""

from __future__ import annotations

import re

from pathlib import Path
from tests._app_js import app_js_text, frontend_text

JS = app_js_text()
CSS = Path("frontend/css/lightbox-lazy.css").read_text(encoding="utf-8") + Path("frontend/css/02-chat-graph.css").read_text(encoding="utf-8")
LIGHTBOX = JS.split("function openLightbox(")[1].split("\n// ")[0]


def test_the_arrows_share_a_positioned_box_with_the_image():
    """This is what makes "centred on the image" true by construction. Two
    earlier versions computed it, `top: 50%` of the viewport, then a measured
    `getBoundingClientRect` written back on every `show()`, and both were
    wrong the moment anything else in the dialog had height."""
    assert "lightbox-stage" in LIGHTBOX
    assert "stage.append(img, broken);" in LIGHTBOX
    stage = CSS.split(".lightbox-stage {")[1].split("}")[0]
    assert "position: relative" in stage
    nav = CSS.split(".lightbox-nav {")[1].split("}")[0]
    assert "position: absolute" in nav
    assert "top: 50%" in nav and "translateY(-50%)" in nav


def test_the_picture_never_goes_under_an_arrow():
    """The owner, 2026-09-24: "the image clashes with the side left and right
    arrow buttons". `scratchpad/ui-sweeps/lightboxfit.js` measured 976px2 of
    a wide picture under each arrow at Fit at 1440, and a zoomed one under
    them at every width. The stage (the scrollport) is narrowed by the
    arrows' room whenever there are arrows, and the picture is capped by it."""
    assert 'stageWrap.classList.add("lightbox-paged")' in LIGHTBOX
    rule = re.search(r"\.lightbox-stage-wrap\.lightbox-paged > \.lightbox-stage \{([^}]*)\}", CSS)
    assert rule and "var(--lightbox-nav-room)" in rule.group(1)
    capped = re.search(r"\.lightbox-stage > img,\s*\.lightbox-stage > \.lightbox-doc \{([^}]*)\}", CSS)
    assert capped and "100%" in capped.group(1)


def test_the_info_card_is_one_width_under_the_toolbar():
    """It shrank to its words: 383, 768 and 314px on three pictures at 1440
    under a 350px toolbar. Both now take the one shared width."""
    for selector in (r"\.lightbox-info", r"\.lightbox-actions"):
        rule = re.search(selector + r" \{([^}]*)\}", CSS)
        assert rule and "width: var(--lightbox-panel-w)" in rule.group(1), selector


def test_nothing_measures_the_image_to_place_the_arrows():
    """The measured version had to be re-run on every image change and every
    resize, and was one forgotten call away from being wrong again."""
    # In code, not in the comment explaining why it went.
    code = "\n".join(
        line for line in LIGHTBOX.splitlines() if not line.strip().startswith("//")
    )
    assert "positionNav" not in code
    assert 'addEventListener("resize"' not in code


def test_the_overlay_scrolls():
    """"is the lightbox scrollable??", it was not, and a column taller than
    the viewport simply lost its ends."""
    block = CSS.split(".lightbox {")[1].split("}")[0]
    assert "overflow-y: auto" in block
    assert "place-content: center" not in block, (
        "place-content centres and then clips; that is the bug"
    )


def test_the_info_panel_has_no_scrollbar_of_its_own():
    """A box that is itself cut off, with its own inner scrollbar, is the
    thing in the screenshot. The dialog scrolls; the panel just gets taller."""
    block = CSS.split(".lightbox-info {")[1].split("}")[0]
    assert "overflow-y: auto" not in block
    assert "max-height" not in block


def test_the_image_leaves_room_for_what_is_under_it():
    block = CSS.split(".lightbox img {")[1].split("}")[0]
    assert "max-height: 68vh" in block, "80vh left no room for the caption panel"


def test_the_panel_says_which_picture_this_is():
    """"maybe it can have the image information and other info about it below
    the image with the caption and ocr text??", size, when it arrived, what
    it is called."""
    assert "lightbox-facts" in LIGHTBOX
    assert "naturalWidth" in LIGHTBOX, "dimensions come from the decoded image"
    assert "item.addedAt" in LIGHTBOX


def test_the_upload_list_carries_the_date_the_panel_shows():
    """The one fact of that kind the browser cannot work out for itself."""
    routes = Path("src/tessellate/api/routes_files.py").read_text(encoding="utf-8")
    assert "created_at: str = \"\"" in routes
    assert "created_at=u.created_at.isoformat()" in routes
    library = Path("frontend/js/library.js").read_text(encoding="utf-8")
    assert "addedAt: i.created_at" in library


def test_the_panel_is_readable_over_whatever_is_behind_it():
    """At 0.45 the Library grid showed straight through a paragraph of
    transcribed text."""
    block = CSS.split(".lightbox-info {")[1].split("}")[0]
    assert "rgba(10, 12, 20, 0.86)" in block
    assert "backdrop-filter" in block


def test_every_other_caller_still_passes_only_what_it_always_did():
    """`caption`, `text`, `byline` and `addedAt` are optional. A caller that
    passes `{filename, getUrl}` must get exactly the dialog it got before."""
    assert "item.caption || \"\"" in LIGHTBOX
    assert "item.text || \"\"" in LIGHTBOX
    for other in ("frontend/js/graph.js", "frontend/js/dashboard.js"):
        source = Path(other).read_text(encoding="utf-8")
        if "openLightbox(" in source:
            assert "getUrl" in source


# --- a document, shown like a document (UI_MODERNISATION_PLAN Phase 7.1) ------
#
# Reported: "the lightbox needs improving for file and pdf previews, no
# sections or info are below it really compared to the images." An image got
# facts, caption, reading and bylines; a PDF got the pages and nothing else.
#
# These are lints for the same reason the rest of this file is: the geometry
# and the wiring were measured once in Chromium (page chips render, the stepper
# steps, the workspace opens at the page named in the readout), and a lint is
# what stops the wiring being quietly removed between sessions.


def test_the_document_block_reuses_the_image_panel():
    """"Reuse the image block's DOM builders; do not write a second block."

    The page chips and the facts line live in `.lightbox-info`, the same
    panel, the same `renderInfo`. A second panel for documents would be two
    places to keep in step, which is the shape this plan is subtracting."""
    assert "lightbox-pages" in LIGHTBOX
    # Matched as a call rather than as one line of source. The rule is that
    # the page chips go into the *existing* panel, and that is a fact about
    # which element they are appended to, not about where the formatter put
    # the line breaks: this asserted a single-line `info.append(infoFacts,
    # infoPages,` and broke the moment a second reading's two elements made
    # the argument list long enough to wrap, while the behaviour it protects
    # was untouched.
    appends = re.findall(r"\binfo\.append\(([^)]*)\)", LIGHTBOX, re.S)
    assert len(appends) == 1, (
        f"the info panel is filled by {len(appends)} append calls; one panel "
        "means one place that fills it"
    )
    arguments = appends[0]
    assert "infoFacts" in arguments and "infoPages" in arguments, (
        "the page chips belong inside the existing info panel"
    )
    assert arguments.index("infoFacts") < arguments.index("infoPages"), (
        "the facts line comes before the page chips"
    )
    # One renderer for the facts line, called from the document path too.
    assert "renderInfo(item, true);" in LIGHTBOX


def test_a_document_says_how_many_pages_and_how_many_are_read():
    assert "docPageCount" in LIGHTBOX
    assert "docPagesRead" in LIGHTBOX
    assert "page-reads" in LIGHTBOX, "read pages come from the PageRead store"


def test_the_stepper_and_the_chips_are_cleared_between_files():
    """A photograph must not inherit the previous file's page count: the
    "page 4 of 9" on an image bug this reset exists to prevent."""
    assert "resetDocPages()" in LIGHTBOX
    assert LIGHTBOX.count("resetDocPages()") >= 2, (
        "reset on both the document path and the image path"
    )


def test_the_workspace_opens_at_the_page_on_screen():
    """Phase 7.1's "a way into the OCR Workspace at that page"."""
    assert "const atPage = docPageCount ? docPage : 0;" in LIGHTBOX
    assert "window.openOcrWorkspace(target, [], atPage);" in LIGHTBOX
    library = Path("frontend/js/library.js").read_text(encoding="utf-8")
    assert "function openOcrWorkspace(image, images, page = 0)" in library
    assert "ocrLoadPage(image, startPage)" in library


def test_the_lightbox_leaves_before_the_workspace_arrives():
    """Reported: "when I open a pdf file in the lighbox and press the read text
    with ai, it opens the ocr workspace but behind the lightbox so the lightbox
    needs to close when the workspace opens."

    `.lightbox` is z-index 1020 (raised there to clear the CSS full-screen
    graph) and the workspace is a `.modal-overlay` at 1010, so it opened
    underneath and every click landed on the lightbox's dismiss backdrop:
    reproduced in Chromium, where a hit test on the workspace's own first button
    returned `.lightbox-stage`.

    The close has to come before the call and the target has to be read into a
    local first, since `close()` empties the lightbox's state. Ordering is what
    this guards, because both lines on their own look correct.
    """
    body = LIGHTBOX[LIGHTBOX.index("const readWithAiBtn") :]
    body = body[: body.index("window.openOcrWorkspace(target, [], atPage);")]
    assert "const target = lightboxOcrTarget;" in body, (
        "the target is read after the dismiss, which has already cleared it"
    )
    assert body.rindex("close();") > body.rindex("const atPage"), (
        "the lightbox is still up when the workspace opens, which is the report"
    )


def test_the_workspace_target_carries_the_url_its_pages_are_served_from():
    """Measured against the running app: a `/media/` target built with only an
    id asked for `/media/pdf-page//0` and got a 404, so "open the reader here"
    opened an empty stage."""
    assert "url: `/media/${name}`" in LIGHTBOX


# The lightbox row is one height (owner 2026-10-10).
ROOT = Path(__file__).resolve().parents[1]


def test_the_lightbox_row_is_one_height():
    """"These elements in the lightbox aren't the same height" (Copy text,
    Save, Find in document). Measured at 1440 on a PDF: Save 32, Find 28, the
    ⋯ 28; after, all 32 (44 under touch, as before)."""
    css = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    rule = css[css.index(".lightbox .lightbox-find {") :]
    assert "min-height: max(2rem, var(--target-min));" in rule[: rule.index("\n}")]
    view = frontend_text("lightbox-view.js")
    assert 'opener.style.minHeight = opener.style.minWidth = "max(2rem, var(--target-min))";' in view


def test_a_picture_after_a_pdf_zooms_the_picture():
    """Found with the C30 redesign: the image path hid the document but left
    its page column showing inside it, so `zoomTarget()` still answered the
    page column and a picture paged to from a PDF zoomed the PDF."""
    image_path = LIGHTBOX[LIGHTBOX.index('    doc.classList.add("hidden");\n    //: The page column too') :][:400]
    assert 'pdfPages.classList.add("hidden");' in image_path


def test_the_viewer_keys_leave_typing_alone():
    """The find box and the file editor are inside the dialog: an arrow or a
    plus typed there is text, not a page turn or a zoom."""
    keys = LIGHTBOX[LIGHTBOX.index("const onKey = (e) =>") :][:1600]
    assert "typing(e.target)" in keys
    for key in ('"+"', '"-"', '"0"', '"1"', '"r"', '"i"', '"ArrowLeft"', '"Escape"'):
        assert key in keys, key
