"""perf-1031 findings 1 and 2 (perf2-1031): work the person cannot see is not done.
Each test names the cost it keeps out; the numbers are in CHANGELOG.md."""

from tests._app_js import frontend_text


def _body(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_a_list_nobody_can_see_is_not_repainted_as_pages_arrive():
    # Behind the Dashboard on a reload the Notes list was rebuilt 6 to 10 times
    # (1.4 s of main thread at 4x). The progress paint, the spaces answer and the
    # map index answer ask `renderEntriesWhenShown`; the reveal draws it once.
    notes = frontend_text("notes-list.js")
    assert "renderEntriesWhenShown();" in _body(notes, "function paintEntriesProgress(", "function renderEntriesWhenShown")
    gate = _body(notes, "function renderEntriesWhenShown()", "function flushEntriesPaint()")
    assert 'classList.contains("hidden")' in gate and 'dataset.stale = "1"' in gate
    assert "renderEntries()" in _body(notes, "function flushEntriesPaint()", "async function loadEntries")
    assert "renderEntriesWhenShown();" in _body(notes, "function ensureMapChipsFor", "\n}\n")
    assert "renderEntriesWhenShown()" in frontend_text("spaces-find.js")
    reveal = _body(frontend_text("navigation.js"), "function revealTab(name)", "window.nameMarkBuddyTabChanged")
    assert 'if (name === "notes") flushEntriesPaint();' in reveal


def test_a_real_render_clears_the_owed_paint():
    notes = frontend_text("notes-list.js")
    assert "delete $(\"entry-list\").dataset.stale;" in _body(notes, "function renderEntries() {", "closeNotePageIfGone();")


def test_a_hidden_gutter_costs_a_key_nothing():
    # `renderDocGutter` walks every `.doc-gutter` in the page before it reads one
    # (394 ms over 61 keys at 4x in a 14k-node page): the listeners look at their
    # own gutter first.
    js = frontend_text("documents.js")
    mount = _body(js, "const paint = () => {", 'textarea.addEventListener("scroll"')
    assert mount.index('gutter.classList.contains("hidden")') < mount.index("renderDocGutter(textarea)")
    assert 'textarea.addEventListener("input", paint);' in mount
    assert 'for (const type of ["focus", "blur", "keyup", "mouseup"]) textarea.addEventListener(type, paint);' in mount


def test_a_long_list_repaints_only_on_its_first_and_last_page():
    # 2,000 notes repainted the whole list about eight times as pages arrived
    # (5.7 s blocked at 4x, the last frame 910 ms). Past 600 rows a page in
    # between refreshes the status bar only; the first and last page still paint.
    notes = frontend_text("notes-list.js")
    assert "const ENTRIES_PROGRESS_LIST_MAX = 600;" in notes
    schedule = _body(notes, "function scheduleEntriesProgress()", "async function loadEntries")
    assert "allEntries.length <= ENTRIES_PROGRESS_LIST_MAX" in schedule
    paint = _body(notes, "function paintEntriesProgress(", "function renderEntriesWhenShown")
    assert "renderStatusBar();" in paint and "if (list) renderEntriesWhenShown();" in paint
    loop = _body(notes, "const lastPage = offset >= total", "renderSidebar();")
    assert "if (first || lastPage) paintEntriesProgress();" in loop

