"""INBOX 1530 (c): opening a document from the Library forced layout inside
the click, `openDoc` 109 ms with 83 ms forced and drag-edge.js's document
`mousedown` 54 ms with 53 ms forced in the owner's log. Traced with stacks
(Chromium `Layout` and `UpdateLayoutTree` events, the 1530 sweep): each read
came after a write in the same task, so the page was laid out once per read.
The reads now come before the writes, run after the frame's layout, or are
skipped where nothing uses them."""

from tests._app_js import frontend_text


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_reveal_tab_resets_only_a_page_that_scrolled():
    js = frontend_text("navigation.js")
    body = _body(js, "function revealTab(name) {")
    assert "revealTab.scrolled.delete(page)) page.scrollTo(" in body
    assert "scrollingPage()?.scrollTo(" not in body
    assert "revealTab.scrolled.add(event.target)" in js


def test_the_back_to_top_check_is_scheduled_for_callers():
    js = frontend_text("navigation.js")
    body = _body(js, "function initScrollTopButton(")
    assert body.rstrip().endswith("return scheduleUpdate;")


def test_a_press_reads_no_layout_before_it_drags():
    js = frontend_text("drag-edge.js")
    start = js.index('document.addEventListener("mousedown"')
    press = js[start : js.index("}, true);", start)]
    assert "dragEdgeZone" not in press and "getComputedStyle" not in press
    assert "d.el = dragEdgeZone(d.press);" in _body(js, "function dragEdgeTick() {")


def test_set_doc_view_reads_the_editor_range_only_for_read():
    body = _body(frontend_text("documents.js"), "function setDocView(mode")
    line = next(row for row in body.splitlines() if "const editorRange" in row)
    assert 'docView === "rendered"' in line.split("?")[0]


def test_the_outline_reads_the_caret_line_before_it_writes():
    js = frontend_text("documents.js")
    body = _body(js, "function renderDocOutline() {")
    read = body.index("const where = docWhereLine();")
    assert read < body.index('wrap.classList.remove("hidden")')
    assert body.count("docWhereLine()") == 1
    assert "markDocOutline(where)" in body
    opener = js[js.index("docAfterFirstPaint(seq, () => {") :]
    assert opener.index("renderDocOutline();") < opener.index("renderDocTools();")


def test_the_trail_fade_is_measured_after_the_frame():
    #: renderDocCrumbs moved to documents-outline.js, one closure (doc24-1102): its lines sit two spaces further in.
    js = frontend_text("documents-outline.js")
    start = js.index("function renderDocCrumbs(line) {")
    body = js[start : js.index("\n  }\n", start)]
    assert "afterFrames(() => setTimeout(" in body
    assert "\n    window.syncEdgeFade?.(nav);" not in body
