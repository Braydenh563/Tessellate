"""The Library's media poll must not outlive the Library tab (INBOX 424 d).

`startLibraryImagesPoll` (library.js) refetches `/media` every six seconds
while the Images or Files sub-tab is showing. Only the other Library
sub-tabs stopped it, so leaving the Library for any other tab kept the
request going there, measured at one `/media` fetch per six seconds on the
Dashboard. `switchTab` (app.js) is the one place every tab change passes
through, so that is where it has to stop.
"""

import re
from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent


def _switch_tab_body() -> str:
    src = app_js_text()
    start = src.index("async function switchTab(name) {")
    end = src.index("\n}\n", start)
    return src[start:end]


def test_switch_tab_stops_the_media_poll_when_leaving_the_library():
    body = _switch_tab_body()
    assert re.search(r'if \(name !== "library"\) stopLibraryImagesPoll\(\);', body)


def test_switch_tab_restarts_it_only_when_the_media_sub_tab_is_showing():
    body = _switch_tab_body()
    assert "startLibraryImagesPoll()" in body
    assert '"library-view-media"' in body


def test_the_poll_functions_still_exist_in_library_js():
    lib = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert "function startLibraryImagesPoll()" in lib
    assert "function stopLibraryImagesPoll()" in lib


def _poll_source() -> str:
    lib = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    start = lib.index("function startLibraryImagesPoll()")
    return lib[start : lib.index("function stopLibraryImagesPoll()", start)]


def test_the_poll_skips_a_hidden_window_and_backs_off_when_nothing_changes():
    """The poll refetched every `/media` and `/files/gallery` page every six
    seconds while the gallery showed, hidden window or not, for a caption
    that may never come (no vision model). The jobs stream
    (`/jobs/stream`, routes_tasks.py) does report captions, but only
    Settings, Running jobs opens it (chat-tasks.js), and a second held stream
    for the gallery costs more code than it saves; so the poll skips a hidden
    window and doubles its wait after each look that changed nothing, from
    six seconds to a minute, back to six on a change."""
    body = _poll_source()
    assert "setInterval" not in body
    assert "document.hidden" in body
    assert "60000" in body
    assert re.search(r"6000 \* 2 \*\* ", body)
