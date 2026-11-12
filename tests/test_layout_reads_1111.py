"""Settings, the log view and the tab change read layout only when they must (INBOX 1111).

The owner's Long Animation Frame log showed forced style and layout inside presses and
scrolls: `focus()` on a just-shown window, a `scrollTop` read per scroll region on every
tab change, one full log draw per streamed record, and a `scrollHeight` read per scroll
event. Each was measured at 4x CPU throttling; these pin the shape that removed it."""

from __future__ import annotations

import re
import subprocess

from tests._app_js import APP_JS, frontend_text

SETTINGS = frontend_text("settings.js")
CONTROLS = frontend_text("settings-controls.js")
REMINDERS = frontend_text("shell-reminders.js")
APP = APP_JS.read_text(encoding="utf-8")


def test_opening_settings_focuses_a_frame_later():
    assert 'afterFrames(() => $("settings-close").focus(), 1);' in SETTINGS
    assert re.search(r"^\s*\$\(\"settings-close\"\)\.focus\(\);", SETTINGS, re.M) is None


def test_a_section_heading_takes_focus_a_frame_after_the_switch():
    assert "afterFrames(() => head.focus({ preventScroll: true }), 1);" in SETTINGS
    assert re.search(r"^\s*head\.focus\(", SETTINGS, re.M) is None


def test_a_streamed_record_asks_for_a_draw_and_does_not_make_one():
    assert "if (logScreenOpen) renderActiveLogView.soon();" in SETTINGS
    assert "if (logScreenOpen) renderActiveLogView.soon(true);" in APP
    assert not re.search(r"if \(logScreenOpen\) renderActiveLogView\(\);", SETTINGS)


def _soon_draws(requests: str) -> list[int]:
    """Run `renderActiveLogView.soon` under a fake timer: how many draws, and how many scrolls."""
    start = CONTROLS.index("renderActiveLogView.soon = (toBottom) => {")
    body = CONTROLS[start : CONTROLS.index("\n};\n", start) + 4]
    script = (
        "let draws = 0, scrolls = 0, timers = [];"
        "const setTimeout = (fn) => timers.push(fn);"
        "const scrollLogToBottom = () => scrolls++;"
        "function renderActiveLogView() { draws++; }"
        f"{body}"
        f"{requests}"
        "const due = timers.splice(0); due.forEach((fn) => fn());"
        "process.stdout.write(JSON.stringify([due.length, draws, scrolls]));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return [int(n) for n in out.strip("[]").split(",")]


def test_fifty_streamed_records_make_one_draw():
    assert _soon_draws("for (let i = 0; i < 50; i++) renderActiveLogView.soon();") == [1, 1, 0]


def test_a_browser_error_among_them_still_scrolls_to_the_end_once():
    assert _soon_draws("renderActiveLogView.soon(); renderActiveLogView.soon(true); renderActiveLogView.soon();") == [1, 1, 1]


def test_the_log_scroll_listener_is_passive_and_reads_a_frame_later():
    start = CONTROLS.index('for (const id of ["log-list", "log-terminal"]) {')
    block = CONTROLS[start : CONTROLS.index("\n}\n", start)]
    assert "{ passive: true }" in block
    assert block.index("afterFrames") < block.index("nearLogBottom()")
    assert "if (queued ||" in block


def test_a_tab_change_asks_only_the_regions_last_seen_scrolled():
    assert "scrollEdgeLastState.get(region) && page.contains(region) && region.scrollTop > 1" in REMINDERS


def test_the_idle_warm_fetches_scripts_only_so_it_restyles_nothing():
    """library-lazy.css is 288 KB: adding it to the page restyled the Dashboard in whatever the person was
    doing (125 to 159ms of style at 4x). Its first real ask (`ensureModule`) still brings every stylesheet."""
    entries = frontend_text("lazy-entries.js")
    assert 'LAZY_MODULES.library].filter((f) => f[1] > "c")' in entries
    lazy = APP_JS.read_text(encoding="utf-8")
    for name in ("graph", "library"):
        assert re.search(rf"{name}: \[[^\]]*\"/css/\w+-lazy\.css\"", lazy), name
    sample = ["/js/a.js", "/vendor/d3.js", "/css/a.css"]
    assert [f for f in sample if f[1] > "c"] == ["/js/a.js", "/vendor/d3.js"]
