"""The documents focus mode's "Fill the whole screen" fills it in the desktop
window too (INBOX 426 z, images 93 and 94).

In WebView2 the page's `requestFullscreen()` was granted to the web view, the
button turned to "Leave full screen", and the window stayed the size it was:
resizing the window is the host's job and pywebview does not do it. The
desktop launcher now registers the window's own toggle (core/window_hook.py)
and the page asks for it through `/desktop/fullscreen` when it is there.
The real window is not driven here (no display in the sandbox); a stand-in
toggle is.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import documents_text

from tessellate.core import window_hook

ROOT = Path(__file__).resolve().parent.parent


def test_without_a_window_the_page_is_told_to_use_the_browser(client):
    window_hook.set_fullscreen_handler(None)
    assert client.get("/desktop/fullscreen").json() == {"available": False, "fullscreen": False}
    assert client.post("/desktop/fullscreen").json() == {"available": False, "fullscreen": False}


def test_the_window_is_asked_and_its_state_kept(client):
    calls = []
    window_hook.set_fullscreen_handler(lambda: calls.append(1))
    try:
        assert client.get("/desktop/fullscreen").json() == {"available": True, "fullscreen": False}
        assert client.post("/desktop/fullscreen").json() == {"available": True, "fullscreen": True}
        assert client.post("/desktop/fullscreen").json() == {"available": True, "fullscreen": False}
        assert len(calls) == 2
    finally:
        window_hook.set_fullscreen_handler(None)


def test_a_failing_toggle_reports_not_available(client):
    def boom():
        raise RuntimeError("no window")

    window_hook.set_fullscreen_handler(boom)
    try:
        assert client.post("/desktop/fullscreen").json()["available"] is False
        assert window_hook.is_fullscreen() is False
    finally:
        window_hook.set_fullscreen_handler(None)


def test_the_desktop_launcher_registers_the_window_toggle():
    main = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
    assert 'getattr(window, "toggle_fullscreen", None)' in main
    assert "window_hook.set_fullscreen_handler(toggle_fullscreen)" in main


def test_the_page_prefers_the_window_where_there_is_one():
    docs = documents_text()
    toggle = docs[docs.index("async function docFocusToggleFullscreen"):]
    toggle = toggle[: toggle.index("\n}\n")]
    assert toggle.index("docDesktopFs().available") < toggle.index("requestFullscreen")
