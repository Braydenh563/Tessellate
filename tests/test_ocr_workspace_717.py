"""The OCR workspace's controls, redesigned (INBOX 717).

The owner, 2026-10-06, with screenshots: "these arent aligned. and can you
redesign the ocr worspace controls to be more modern, professional, learnable,
accessible, usable and better ui/ux?? they also go onto two rows. the whole
ocr workspace is just a bit iffy to use and interact with", and then, after
the chat button dropped the page's whole text into the chat composer: "I
pressed the comment button on the ocr workspace and idk what just happened".

Measured before (`scratchpad/ui-sweeps/ocr717.js`, 1440, a three-page PDF,
Tesseract faked ready): the head was 116px in three rows, the title row, a
36px tool row of ten controls (a Regions switch, Fit and 100%, the zoom pair,
One page and Scroll, the reader select, Read this page, a bare "all" field and
Read pages), and a 32px engine line under it ("Tesseract 5.5.3 is ready" as a
filled badge, "Reads in" and its select, Manage).

What these hold, from the markup and the code (the sweep holds the geometry):

- the tools are one `.dock` on the dock grammar (`data-dock-name="ocr"`),
  grouped View then Read, and never scroll sideways or wrap: what does not fit
  folds into the dock's own menu;
- the bare range field is gone: one filled Read split button whose menu holds
  this page, every page and a range;
- the engine's state is a dot inside the reader button, and its language and
  install live in that button's popover, not on a row of their own; Manage is
  a row of a menu;
- one '?' in the head, short;
- the chat button asks about the page with a context chip, never by writing
  the page into the composer, and says what it did;
- the rail and the reading walk with the arrow keys, and typing in a reading
  never turns the page.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = ROOT / "frontend" / "js"
LIBRARY = (JS / "library.js").read_text(encoding="utf-8")
ENGINE = (JS / "ocr-engine.js").read_text(encoding="utf-8")
CHAT_ATTACH = (JS / "chat-attach.js").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _markup() -> str:
    """The workspace's markup, comments out."""
    start = INDEX.index('<div id="ocr-workspace"')
    end = INDEX.index("<!-- **Managing the dictionary**", start)
    return re.sub(r"<!--.*?-->", "", INDEX[start:end], flags=re.S)


def _body(source: str, name: str) -> str:
    match = re.search(rf"(?:async )?function {name}\(", source)
    assert match, name
    depth, i = 0, source.index(") {", match.end()) + 2
    for j in range(i, len(source)):
        depth += {"{": 1, "}": -1}.get(source[j], 0)
        if depth == 0:
            return source[i : j + 1]
    raise AssertionError(name)


def _handler(element_id: str) -> str:
    """The body of the click listener registered on `element_id`."""
    at = LIBRARY.index(f'$("{element_id}")?.addEventListener("click"')
    depth, i = 0, LIBRARY.index("{", at)
    for j in range(i, len(LIBRARY)):
        depth += {"{": 1, "}": -1}.get(LIBRARY[j], 0)
        if depth == 0:
            return LIBRARY[i : j + 1]
    raise AssertionError(element_id)


def test_the_tools_are_one_dock_on_the_grammar():
    html = _markup()
    dock = re.search(r'<div id="ocr-dock" class="([^"]*)"[^>]*>', html)
    assert dock, "the tool row is #ocr-dock"
    assert {"dock", "ocr-toolbar"} <= set(dock.group(1).split())
    assert 'data-dock-name="ocr"' in dock.group(0)
    assert 'role="toolbar"' in dock.group(0)
    # View, then Read: the grammar's arrange zone, then its actions.
    assert re.search(r'class="dock-arrange dock-group[^"]*"[^>]*aria-label="View"', html)
    assert re.search(r'class="dock-actions[^"]*"[^>]*aria-label="Read"', html)


def test_the_row_folds_rather_than_scrolling_or_wrapping():
    rules = re.findall(r"\.ocr-dock\s*\{([^}]*)\}", CSS)
    assert rules, "the .ocr-dock rule is missing"
    joined = "\n".join(rules)
    assert re.search(r"flex-wrap:\s*nowrap", joined)
    assert "overflow-x: auto" not in joined
    assert "--control-h" in joined
    # The fold is measured, not a breakpoint: the row is watched and the
    # folded controls are offered in the dock's own menu.
    # The fit searches the steps and `ocrDockApply` sets them (28.4 row 9).
    fit = _body(LIBRARY, "ocrFitDock")
    assert "ResizeObserver" in LIBRARY[LIBRARY.index("function ocrWatchDock") :][:1500]
    assert "ocrDockApply(dock, count)" in fit and "ocrDockFits(dock)" in fit
    assert "is-folded" in _body(LIBRARY, "ocrDockApply")
    menu = _body(LIBRARY, "ocrSyncToolsMenu")
    assert "kebabMenu(" in menu and "is-folded" in menu


def test_no_bare_range_field_one_read_split_button():
    html = _markup()
    assert 'id="ocr-read-pages"' not in html
    assert 'id="ocr-read-range"' not in html
    split = re.search(r'<div id="ocr-read-split" class="([^"]*)"', html)
    assert split and "split-button" in split.group(1).split()
    primary = re.search(r'<button id="ocr-read-page" class="([^"]*)"', html)
    assert primary and "ghost" not in primary.group(1).split(), "Read is the one filled action"
    # The caret is the menu recipe's own opener (kebabMenu: placement,
    # escape, the keys), dressed as the split's second half.
    assert 'id="ocr-read-menu-slot"' in html[split.start() : split.start() + 2000]
    build = _body(LIBRARY, "ocrSyncReadMenu")
    assert "kebabMenu(" in build and 'opener.id = "ocr-read-menu"' in build
    assert "split-button-caret" in build and "aria-label" in build
    menu = _body(LIBRARY, "ocrReadMenuItems")
    for words in ("Read this page", "Read all", "Read pages"):
        assert words in menu, words
    # The range is asked for when it is wanted, in the app's own prompt.
    assert "promptDialog(" in _body(LIBRARY, "ocrAskRange")


def test_the_ghost_split_shares_one_border():
    # INBOX 790: over a reading the pair is ghost, and the caret (kebabMenu's
    # opener, quieted by `.dock .menu-wrap > button.ghost`) drew no border of
    # its own, so it read as a second control. The rule must name `.menu-wrap`
    # to outrank the dock's.
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"\n\n\.split-button \.menu-wrap > \.split-button-caret\.ghost \{([^}]*)\}", css)
    assert rule, "the ghost caret needs a rule that outranks the dock's"
    assert "margin-inline-start: -1px" in rule.group(1)
    assert "border-start-start-radius: 0" in rule.group(1)
    both = re.search(r"\.split-button > \.split-button-main\.ghost,\s*\.split-button \.menu-wrap > \.split-button-caret\.ghost \{([^}]*)\}", css)
    assert both and "1px solid var(--ghost-btn-border)" in both.group(1)


def test_the_engine_is_a_dot_and_a_popover_not_a_row():
    html = _markup()
    menu = re.search(r'<details id="ocr-reader-menu" class="([^"]*)"', html)
    assert menu and {"dock-menu", "doc-dock-menu"} <= set(menu.group(1).split())
    inside = html[menu.start() : html.index("</details>", menu.start())]
    assert 'id="ocr-engine-dot"' in inside
    assert 'id="ocr-reader"' in inside, "the reader choice lives in the popover"
    assert 'id="ocr-engine"' in inside, "the engine's line lives in the popover"
    # The popover paints no badge and no Manage button: Manage is a menu row.
    paint = _body(ENGINE, "ocrEnginePaint")
    assert "opts.popover" in paint
    assert "ph:gear Manage" not in ENGINE
    assert "Manage" in _body(LIBRARY, "ocrSyncToolsMenu")
    # The dot carries its state and says it in words.
    dot = _body(LIBRARY, "ocrSyncReaderButton")
    assert "is-ok" in dot and "is-warn" in dot and "title" in dot


def test_the_language_label_sits_over_its_select():
    """"Reads in [Default]" with the label off the select's centre line was
    one of the screenshot's misalignments: in the popover the label is a
    section label above the select (the dock menu's own recipe)."""
    picker = _body(ENGINE, "ocrEngineLanguagePicker")
    assert "dock-menu-label" in picker


def test_icon_controls_are_named_and_say_their_keys():
    html = _markup()
    for tag in re.findall(r"<button[^>]*\bicon-only\b[^>]*>", html):
        assert "aria-label=" in tag, tag
        assert "title=" in tag, tag
    for ident, key in (("ocr-zoom-in", "+"), ("ocr-zoom-out", "-"), ("ocr-zoom-fit", "0")):
        tag = re.search(rf'<button[^>]*id="{ident}"[^>]*>', html).group(0)
        assert f'aria-keyshortcuts="{key}"' in tag, ident
        assert f"({key})" in tag, ident
    keys = LIBRARY[LIBRARY.index('document.addEventListener("keydown", (event) => {\n    const overlay = $("ocr-workspace")') :][:6000]
    for key in ('"+"', '"-"', '"0"'):
        assert key in keys, key


def test_regions_is_a_toggle_button_not_a_loose_switch():
    html = _markup()
    tag = re.search(r'<button[^>]*id="ocr-regions"[^>]*>', html)
    assert tag and 'aria-pressed="true"' in tag.group(0)
    assert 'id="ocr-show-boxes"' not in html


def test_one_short_help_in_the_head():
    html = _markup()
    toggles = re.findall(r'data-help-for="(ocr-[a-z-]+)"', html)
    assert toggles == ["ocr-help"], toggles
    body = re.search(r'<div class="help-body hidden" id="ocr-help"[^>]*>(.*?)</div>', html, re.S)
    assert body
    lines = re.findall(r"<(?:p|li)>", body.group(1))
    words = re.sub(r"<[^>]+>|\s+", " ", body.group(1)).strip()
    assert 1 <= len(lines) <= 4 and len(words) <= 360, (len(lines), len(words))


def test_an_empty_reading_says_what_to_do_first():
    empty = _body(LIBRARY, "ocrPaintEmpty")
    assert "Nothing read yet" in empty
    assert "drag" in empty.lower()
    assert "ocrPaintEmpty(" in _body(LIBRARY, "ocrRenderRegions")


def test_the_chat_button_attaches_the_page_and_says_so():
    html = _markup()
    tag = re.search(r'<button id="ocr-to-chat"[^>]*>', html).group(0)
    assert 'aria-label="Ask about this page in chat"' in tag
    handler = _handler("ocr-to-chat")
    assert "chat-input" not in handler and ".value =" not in handler, "never writes the composer"
    assert "attachSelectionContext(" in handler
    assert 'kind: "reading"' in handler
    assert "toast(" in handler
    # The chip and what the model is told both know a reading is not a
    # selection with a line number in an editor.
    assert 'kind === "reading"' in _body(CHAT_ATTACH, "renderSelectionAttachment")
    assert 'kind === "reading"' in _body(CHAT_ATTACH, "selectionContextBlock")
    assert 'kind === "reading"' in _body(CHAT_ATTACH, "revalidateSelection")


def test_the_rail_and_the_reading_walk_with_the_arrows():
    rove = _body(LIBRARY, "ocrRoveKeys")
    for key in ("ArrowDown", "ArrowUp", "Home", "End"):
        assert key in rove, key
    assert 'ocrRoveKeys($("ocr-rail")' in LIBRARY
    assert 'ocrRoveKeys($("ocr-region-list")' in LIBRARY
    sync = _body(LIBRARY, "ocrRoveSync")
    assert "tabIndex" in sync


def test_typing_in_a_reading_never_turns_the_page():
    keys = LIBRARY[LIBRARY.index('document.addEventListener("keydown", (event) => {\n    const overlay = $("ocr-workspace")') :][:6000]
    assert "isContentEditable" in keys


def test_the_ring_has_room_in_the_dock():
    """A focus ring on the dock's first and last controls is not cut by the
    card: the dock does not clip (`overflow` stays visible)."""
    rules = "\n".join(re.findall(r"\.ocr-dock\s*\{([^}]*)\}", CSS))
    assert not re.search(r"overflow(-x|-y)?:\s*(auto|hidden|scroll|clip)", rules)


def test_rapidocr_is_a_choice_in_the_reader_popover():
    """The owner: "does the ocr worspace give rapidocr as an alternative??"
    It is an option of the reader picker; missing, the popover says so and its
    Install goes to the Packages row (the reveal recipe); the choice is
    remembered, and nothing remembered keeps the automatic pick."""
    html = _markup()
    menu = html[html.index('<details id="ocr-reader-menu"') :]
    menu = menu[: menu.index("</details>")]
    assert '<option value="rapidocr">' in menu
    assert 'id="ocr-rapidocr-missing"' in menu and 'id="ocr-rapidocr-install"' in menu
    assert 'revealFeature("extra-row", "rapidocr")' in LIBRARY
    reveal = (JS / "reveal-targets.js").read_text(encoding="utf-8")
    assert '"extra-row": { settings: "extras", sel: "#extra-row-{arg}"' in reveal
    loader = _body(LIBRARY, "ocrLoadReadersNow")
    assert "RapidOCR, not installed" in loader
    assert "prefs.get(OCR_READER_KEY" in loader
    assert "prefs.set(OCR_READER_KEY" in LIBRARY
    assert 'reader === "rapidocr" ? "&engine=rapidocr"' in _body(LIBRARY, "ocrRegionsUrl")


def test_turning_a_page_and_zooming_keep_the_reader_s_place():
    """Measured by `ocr717.js MODE=smooth`: a page turn emptied the reading
    for 11 of 91 frames, and one zoom step moved the view's centre from 50% of
    the page to 33%. Another page of the same file keeps its reading until the
    answer replaces it; a zoom keeps its centre; a rebuild keeps the selection."""
    load = _body(LIBRARY, "ocrLoadPage")
    assert "sameFile" in load and 'if (!sameFile) $("ocr-region-list").replaceChildren();' in load
    assert "ocrKeepCentre(() => ocrApplyZoom())" in _body(LIBRARY, "ocrSetZoom")
    assert "ocrKeepCentre(() => ocrApplyZoom())" in _body(LIBRARY, "ocrStepZoom")
    assert "ocrUi.activeRegion" in _body(LIBRARY, "ocrRenderRegions")


def test_pages_belongs_to_the_file_being_viewed():
    """The owner: "pages should only show if a file is selected and open/being
    viewed on the ocr workspace" (a screenshot: "Images 8 | Files 2 | Pages
    6" with Pages chosen). The switch read whichever file its caller passed and
    whatever page count was last set, and a page load that finished after the
    view had moved on (a PDF opened, then an image) still built its page rail.
    Now the segment is decided by the file on screen and the count recorded
    for that file, and a stale load stops before it paints."""
    switch = _body(LIBRARY, "ocrRenderRailSwitch")
    assert "const viewing = ocrWorkspaceCurrent;" in switch
    assert "ocrUi.pagesFor === ocrRailKey(viewing)" in switch
    assert "ocrIsPdf(current)" not in switch
    assert "ocrUi.pagesFor = ocrRailKey(image);" in _body(LIBRARY, "ocrBuildPageRail")
    load = _body(LIBRARY, "ocrLoadPage")
    #: The stale check moved from "is it still this file" to "is it still this
    #: load" (attach-1026 O1): it also stops page 3's answer painting page 4.
    assert load.count("if (seq !== ocrLoadSeq) return;") >= 2
    assert 'ocrRailMode = row._isImage ? "images" : "files";' in _body(LIBRARY, "ocrOpenSibling")


def test_the_pages_segment_is_not_offered_beside_images() -> None:
    """The owner, 2026-10-06: back on Images from Files, Pages was still there."""

    js = Path("frontend/js/library.js").read_text(encoding="utf-8")
    assert 'if (paged && ocrRailMode !== "images") {' in js


# The workspace paints the saved caption before the read is awaited (INBOX 803).


def test_the_ocr_workspace_paints_the_caption_before_the_read_is_awaited():
    # INBOX 803: the saved description showed only after the reader finished.
    js = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    body = js[js.index("async function ocrLoadPage("):]
    assert body.index("ocrPaintCaption(image);") < body.index("await apiJson(ocrRegionsUrl(")
    # A document's descriptions are asked for beside the read, not behind it.
    assert body.index("const storedAsked") < body.index("await apiJson(ocrRegionsUrl(")


# The OCR workspace is found by its name and pinches (owner 2026-10-10).


def test_the_ocr_workspace_is_found_by_its_name_and_pinches():
    """"there's no option to have the ocr workspace in the quick access
    section in the dashboard, it also isnt accessible in the" palette or Find
    anything (searching "ocr" found nothing: the command said "Read a
    document or image with AI"); "I cant two finger trackpad zoom". Measured:
    paletteCommands has "OCR workspace: read a document or image"; in the
    workspace a pinch (Ctrl wheel, 12 x 8 px) went Fit to 125%, a Ctrl notch
    back to 100%, the app's own zoom stayed 100."""
    panes = frontend_text("settings-panes.js")
    assert 'label: "ph:scan OCR workspace: read a document or image",' in panes
    lib = frontend_text("library.js")
    assert '$("ocr-page-pane")?.addEventListener("wheel", (event) => {' in lib
    # Continuous about the pointer, and two fingers on a touch screen too
    # (WORLD_CLASS_PLAN 28.4 row 3, scratchpad/ui-sweeps/ocr79.js).
    assert "ocrZoomAbout(ocrShownZoom() * Math.exp(-delta / 500), event.clientX, event.clientY);" in lib
    assert '$("ocr-page-pane")?.addEventListener("touchmove", (event) => {' in lib
