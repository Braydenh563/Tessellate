"""A tab press reads no layout it has just dirtied (INBOX 1534, second pass).

Measured at 4x CPU with `scratchpad/ui-sweeps/tabstyle1102.js` (the stack of
every forced style or layout pass in a press): the Dashboard press paid 21ms
of style and 14 of layout in `syncEdgeFade` and 60ms in `currentAccentHex`;
the Library press 101 to 130ms in the scroll-top button's `scrollTop` read and
93ms in the tab bar's glide `place`. Each is now told by an observer, which
reports after layout, or reads nothing."""

from __future__ import annotations

from tests._app_js import frontend_text


def _body(text: str, head: str) -> str:
    start = text.index(head)
    return text[start:text.index("\n}\n", start)]


def test_the_kept_accent_ignores_class_flips_and_sees_this_tasks_writes():
    body = _body(frontend_text("settings.js"), "function currentAccentHex(")
    assert 'attributeName !== "class"' in body, "html.status-bar-idle flips forgot it every few seconds"
    assert "observe(document.body" not in body, "no rule keys --accent on the body"
    assert "takeRecords()" in body, "applyAccent redraws the emblem in the task that set the colour"


def test_a_strip_is_measured_by_its_observer_not_where_it_is_wired():
    wire = _body(frontend_text("shell-reminders.js"), "function edgeFadeWire(")
    assert "new ResizeObserver(() => syncEdgeFade(bar)).observe(bar)" in wire
    assert "  syncEdgeFade(bar);\n  bar.addEventListener" not in wire


def test_the_scroll_top_button_reads_a_scroller_only_after_it_has_scrolled():
    js = frontend_text("navigation.js")
    body = js[js.index("const update = () => {"):js.index("const scheduleUpdate")]
    assert "scrolled.has(target) ? target.scrollTop : 0" in body
    assert "scrollHeight" not in body, "Chat never shows the button: its distance is not measured"
    assert "scrolled.add(e.target)" in js


def test_the_glide_is_placed_from_the_observers_report_not_a_timer():
    js = frontend_text("shell-reminders.js")
    glide = js[js.index("function glideStrip("):js.index("function syncEdgeFade(")]
    assert "sized.unobserve(strip);\n    sized.observe(strip);" in glide
    assert "setTimeout" not in glide
