"""The Linux overlay (INBOX 1670, row D): the X11 host, the EWMH readers and the runner on a fake X
connection. The same runner and engine drive both platforms; what is checked here is the Linux
half. A real X server (Xvfb) is used where one is installed (`test_on_a_real_server...`)."""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import runner as runner_mod  # noqa: E402
from tessellate.core.overlay import x11, xlib  # noqa: E402
from tests._x11_fake import FakeX  # noqa: E402
from tests.test_desk_companion import prefs  # noqa: E402,F401

FRAMES = Path(__file__).resolve().parent.parent / "frontend" / "img" / "desk"
FULL = "_NET_WM_STATE_FULLSCREEN"


def wait_for(cond: Any, timeout: float = 2.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


# --- the session ---------------------------------------------------------------------------------


def test_support_says_why_wayland_and_a_missing_display_keep_the_in_app_companion() -> None:
    have = lambda: True  # noqa: E731
    assert x11.support({"DISPLAY": ":0"}, have) == (True, "")
    ok, note = x11.support({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}, have)
    assert not ok and "Wayland" in note and note.endswith("stays in the app.") and "\n" not in note
    assert not x11.support({"WAYLAND_DISPLAY": "wayland-0"}, have)[0]
    assert x11.support({"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0", "TESSELLATE_OVERLAY_X11": "1"}, have)[0]
    ok, none_note = x11.support({}, have)
    assert not ok and "X11 display" in none_note
    assert not x11.support({"DISPLAY": ":0"}, lambda: False)[0]
    for text in (none_note, note):
        assert "\u2014" not in text and "!" not in text


# --- work area, from the panels' struts or _NET_WORKAREA -----------------------------------------------


def test_the_work_area_is_the_monitor_minus_the_panel_that_reserves_space() -> None:
    w = FakeX()
    w.add_window(10, (0, 1040, 1920, 40), kinds=["_NET_WM_WINDOW_TYPE_DOCK"])
    w.props[10]["_NET_WM_STRUT_PARTIAL"] = [0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 1919]
    assert x11.work_areas(w) == [(0, 0, 1920, 1040)]


def test_a_panel_on_one_monitor_does_not_shrink_the_other() -> None:
    w = FakeX()
    w.monitor_list = [(0, 0, 1920, 1080), (1920, 0, 1280, 1024)]
    w.add_window(10, (0, 0, 1920, 32), kinds=["_NET_WM_WINDOW_TYPE_DOCK"])
    w.props[10]["_NET_WM_STRUT_PARTIAL"] = [0, 0, 32, 0, 0, 0, 0, 0, 0, 1919, 0, 0]
    assert x11.work_areas(w) == [(0, 32, 1920, 1080), (1920, 0, 3200, 1024)]


def test_without_struts_the_work_area_is_net_workarea_of_the_current_desktop() -> None:
    w = FakeX()
    w.props[w.root] = {"_NET_WORKAREA": [0, 0, 1920, 1080, 0, 28, 1920, 1000], "_NET_CURRENT_DESKTOP": [1]}
    assert x11.work_areas(w) == [(0, 28, 1920, 1028)]
    w.props[w.root] = {}
    assert x11.work_areas(w) == [(0, 0, 1920, 1080)]  # a bare desktop: the whole monitor


def test_dpi_is_the_desktops_own_scale() -> None:
    w = FakeX()
    assert x11.monitors(w) == [((0, 0, 1920, 1080), 96)]
    w.dpi = 144.0
    assert x11.monitors(w)[0][1] == 144 and x11.dpi_at_point(w, 5, 5) == 144


def test_idle_age_is_in_seconds_and_unknown_is_none() -> None:
    w = FakeX()
    assert x11.last_input_age(w) is None
    w.idle = 2500
    assert x11.last_input_age(w) == 2.5


# --- the window list ---------------------------------------------------------------------------------


def desk() -> FakeX:
    w = FakeX()
    w.props[w.root]["_NET_CURRENT_DESKTOP"] = [0]
    return w


def test_windows_come_topmost_first_with_the_frame_and_a_perch_only_where_one_can_be_stood_on() -> None:
    w = desk()
    area = [(0, 0, 1920, 1080)]
    w.add_window(20, (100, 200, 800, 500), extents=(1, 1, 30, 1))  # bottom of the stack
    w.add_window(21, (300, 300, 400, 300), title="")  # no title
    w.add_window(22, (50, 50, 300, 200), pid=99)  # the app's own
    w.add_window(23, (0, 0, 1920, 1080))  # fills the monitor
    w.add_window(24, (0, 100, 600, 400), state=["_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ"])
    w.add_window(25, (700, 100, 200, 100), kinds=["_NET_WM_WINDOW_TYPE_UTILITY"])
    w.add_window(26, (1000, 100, 300, 300), kinds=["_NET_WM_WINDOW_TYPE_DIALOG"])
    got = x11.windows(w, 99, None, area)
    assert [i.key for i in got] == [26, 25, 24, 23, 22, 21, 20]
    by = {i.key: i for i in got}
    assert by[20].rect == (99, 170, 901, 701) and by[20].perch  # the frame, title bar included
    assert [by[k].perch for k in (21, 22, 23, 24, 25)] == [False] * 5
    assert by[26].perch


def test_hidden_other_desktop_and_ignored_windows_are_not_listed() -> None:
    w = desk()
    w.add_window(30, (0, 0, 400, 300), state=["_NET_WM_STATE_HIDDEN"])
    w.add_window(31, (0, 0, 400, 300), desktop=2)
    w.add_window(32, (0, 0, 400, 300), desktop=0xFFFFFFFF)  # on every desktop
    w.add_window(33, (0, 0, 400, 300), kinds=["_NET_WM_WINDOW_TYPE_TOOLTIP"])
    w.add_window(34, (0, 0, 400, 300))
    assert [i.key for i in x11.windows(w, 1, 34, [(0, 0, 1920, 1080)])] == [32]


def test_an_unreadable_window_does_not_end_the_walk() -> None:
    w = desk()
    w.add_window(40, (10, 10, 400, 300))
    w.props[w.root]["_NET_CLIENT_LIST_STACKING"].append(41)  # no geometry, no properties
    w.add_window(42, (500, 10, 400, 300))
    assert [i.key for i in x11.windows(w, 1, None, [])] == [42, 40]


def test_a_full_screen_top_window_hides_the_figure_and_a_maximised_one_does_not() -> None:
    w = desk()
    assert x11.notification_state(w) is None  # the desktop gives no list at all
    w.add_window(50, (0, 0, 1920, 1080), state=[FULL])
    assert x11.notification_state(w) == x11.FULLSCREEN and x11.FULLSCREEN in x11.QUNS_HIDE
    w.add_window(51, (100, 100, 800, 600))  # a normal window opened over it
    assert x11.notification_state(w) == x11.FREE
    w.props[51]["_NET_WM_STATE"] = ["_NET_WM_STATE_HIDDEN"]  # minimised again: the full screen one is on top
    assert x11.notification_state(w) == x11.FULLSCREEN
    w.props[50]["_NET_WM_DESKTOP"] = [3]  # and on another desktop it is nothing
    assert x11.notification_state(w) == x11.FREE


# --- the host ----------------------------------------------------------------------------------------


class Sink:
    def __init__(self) -> None:
        self.events: list[tuple[str, int, int]] = []
        self.next_wake: int | None = None

    def __call__(self, kind: str, x: int, y: int) -> int | None:
        self.events.append((kind, x, y))
        return self.next_wake if kind != "ready" else None


def host(w: FakeX | None = None, **kw: Any) -> tuple[x11.X11Host, FakeX, Sink]:
    w = w or FakeX()
    sink = Sink()
    return x11.X11Host(w, on_event=sink, **kw), w, sink


def frame(n: int = 4) -> bytes:
    return bytes([0, 0, 200, 255]) * (n * n)


def test_the_host_makes_the_window_reports_ready_and_stops_cleanly() -> None:
    h, w, sink = host()
    assert h.start() and h.alive and sink.events[0][0] == "ready"
    assert h.stop() and not h.alive
    assert w.names()[0] == "create" and "destroy" in w.names()


def test_a_window_that_cannot_be_made_fails_the_start() -> None:
    w = FakeX()
    w.fail_create = True
    h, _w, _s = host(w)
    assert h.start() is False and not h.alive


def test_present_move_show_and_hide_reach_the_window_in_order_and_a_move_to_the_same_place_is_skipped() -> None:
    h, w, _s = host()
    h.start()
    h.present(frame(), 4, 4, 100, 200)
    h.move(100, 200)
    h.move(110, 200)
    h.show()
    h.hide()
    assert wait_for(lambda: "unmap" in w.names())
    assert [c for c in w.calls if c[0] in ("present", "move", "map", "raise", "unmap")] == [
        ("present", 4242, 4, 4, 100, 200), ("move", 4242, 110, 200), ("map", 4242), ("raise", 4242), ("unmap", 4242),
    ]
    assert h.pos == (110, 200) and not h.visible
    h.stop()


def test_pointer_events_become_down_move_up_right_with_a_grab_held_while_dragging() -> None:
    h, w, sink = host()
    w.cursor = (640, 360)
    h.start()
    for kind in ("down", "move", "move", "up", "right"):
        w.inject(kind, 1, 1)
    assert wait_for(lambda: len(sink.events) >= 6)
    assert [e[0] for e in sink.events] == ["ready", "down", "move", "move", "up", "right"]
    assert all(e[1:] == (640, 360) for e in sink.events[1:])
    assert w.names().count("grab") == 1 and w.names().index("grab") < w.names().index("ungrab")
    h.stop()


def test_an_expose_redraws_the_last_frame() -> None:
    h, w, _s = host()
    h.start()
    w.inject("expose")
    assert wait_for(lambda: "redraw" in w.names())
    h.stop()


def test_a_wake_comes_back_as_one_tick_after_the_time_asked_and_never_sooner_than_10_ms() -> None:
    h, _w, sink = host()
    h.start()
    t0 = time.monotonic()
    h.wake(1)
    assert wait_for(lambda: any(e[0] == "tick" for e in sink.events))
    assert 0.009 <= time.monotonic() - t0 < 0.5
    n = sum(e[0] == "tick" for e in sink.events)
    time.sleep(0.1)
    assert sum(e[0] == "tick" for e in sink.events) == n  # one-shot: nothing polls
    h.stop()


def test_the_handler_sets_the_next_wake_and_hide_cancels_a_pending_one() -> None:
    h, w, sink = host()
    h.start()
    sink.next_wake = 20
    w.inject("move")
    assert wait_for(lambda: any(e[0] == "tick" for e in sink.events))
    sink.next_wake = None
    h.wake(60_000)
    h.show()
    h.hide()
    assert wait_for(lambda: "unmap" in w.names())
    assert h._deadline is None
    h.stop()


def test_a_change_of_the_window_stack_raises_the_window_once_for_a_burst() -> None:
    h, w, _s = host()
    h.start()
    h.show()
    assert wait_for(lambda: h.visible)
    before = w.names().count("raise")
    for _ in range(5):
        w.inject("stack")
    assert wait_for(lambda: w.names().count("raise") > before)
    time.sleep(0.3)
    assert w.names().count("raise") == before + 1
    h.stop()


def test_a_display_change_is_passed_on_and_the_window_raised() -> None:
    h, w, sink = host()
    h.start()
    h.show()
    w.inject("display")
    assert wait_for(lambda: ("display", *w.cursor) in sink.events)
    assert wait_for(lambda: w.names().count("raise") >= 2)
    h.stop()


def test_a_loop_that_dies_calls_on_exit_but_a_stop_does_not() -> None:
    died: list[int] = []
    h, _w, _s = host(on_exit=lambda: died.append(1))
    h.start()
    h.stop()
    assert died == []
    w2 = FakeX()
    h2 = x11.X11Host(w2, on_event=Sink(), on_exit=lambda: died.append(2))
    h2.start()
    w2.events = lambda: (_ for _ in ()).throw(RuntimeError("connection lost"))  # type: ignore[method-assign]
    w2.inject("move")
    assert wait_for(lambda: died == [2])


def test_calls_after_the_thread_ended_do_not_write_to_a_reused_descriptor() -> None:
    h, _w, _s = host()
    h.start()
    h.stop()
    h.present(frame(), 4, 4, 0, 0)
    h.wake(5)
    h.hide()  # all quietly dropped
    assert h._wr == -1


# --- the runner on this host ----------------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def make(w: FakeX | None = None, **kw: Any):
    w = w or FakeX()
    clicks: list[Any] = []
    kw.setdefault("home", (800, 920))
    r = runner_mod.OverlayRunner(
        backend=x11, w=w, clock=Clock(), frames=FRAMES, on_click=lambda *a: clicks.append(a), dispatch=lambda n, f: f(), reduced=False, **kw,
    )
    r.clock_hour = 13
    return r, w, clicks


def test_the_runner_picks_the_backend_from_the_connection_it_is_given() -> None:
    from tessellate.core.overlay import win32
    from tests._overlay_fake import FakeWin32

    assert runner_mod.default_backend(FakeWin32()) is win32


def test_start_draws_the_first_frame_hidden_and_the_engine_has_the_work_area() -> None:
    r, w, _c = make()
    assert r.start() and r.engine is not None
    assert [m.area for m in r.monitors] == [(0, 0, 1920, 1080)]
    assert w.presented and "map" not in w.names()
    first = w.presented[0]
    assert len(first["bgra"]) == first["w"] * first["h"] * 4
    r.show()
    assert wait_for(lambda: "map" in w.names())
    r.stop()
    assert "destroy" in w.names()


def test_the_figure_stands_on_the_bottom_edge_of_the_work_area_not_the_screen() -> None:
    w = FakeX()
    w.add_window(10, (0, 1040, 1920, 40), kinds=["_NET_WM_WINDOW_TYPE_DOCK"])
    w.props[10]["_NET_WM_STRUT_PARTIAL"] = [0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 1919]
    r, w, _c = make(w, home=(800, 1070))
    r.start()
    left, top, width, height = r.drawn_rect(round(r.engine.x), round(r.engine.y))
    assert top + height <= 1040 + 4, (top, height)  # the drawn feet within a few pixels of the panel's top, with the bob
    assert r.engine.ground_y() <= 1040
    r.stop()


def test_a_click_on_the_figure_is_handed_on_with_its_drawn_box() -> None:
    r, w, clicks = make()
    r.start()
    r.show()
    wait_for(lambda: "map" in w.names())
    p = w.presented[-1]
    px, py = p["x"] + p["w"] // 2, p["y"] + p["h"] // 2
    w.cursor = (px, py)
    w.inject("down", px, py)
    w.inject("up", px, py)
    assert wait_for(lambda: bool(clicks))
    kind, rect, dpi = clicks[0]
    assert kind == "left" and dpi == 96 and rect[2] > 0 and rect[3] > 0
    r.stop()


def test_a_full_screen_window_hides_the_figure_and_it_comes_back() -> None:
    r, w, _c = make()
    r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    w.add_window(60, (0, 0, 1920, 1080), state=[FULL])
    r.clock.t += 10
    r.host.wake(1)
    assert wait_for(lambda: r.busy and not r.host.visible)
    w.props[60]["_NET_WM_STATE"] = []
    r.clock.t += 10
    r.host.wake(1)
    assert wait_for(lambda: not r.busy and r.host.visible)
    r.stop()


def test_typing_is_read_from_the_screensaver_idle_time() -> None:
    r, w, _c = make()
    r.start()
    r.show()
    wait_for(lambda: r.host.visible)
    w.idle = 300  # a key a third of a second ago
    r.clock.t += 5
    r.host.wake(1)
    assert wait_for(lambda: r.engine.quiet)
    w.idle = 600_000
    r.clock.t += 5
    r.host.wake(1)
    assert wait_for(lambda: not r.engine.quiet)
    r.stop()


def test_other_windows_tops_reach_the_engine_as_perches_when_roaming() -> None:
    w = desk()
    w.add_window(70, (400, 300, 900, 600))
    r, w, _c = make(w)
    r.start()
    r.show()
    wait_for(lambda: r.host.visible)
    r.engine.trip_ready = 0.0
    r.clock.t += 20
    r.host.wake(1)
    assert wait_for(lambda: bool(r.engine.windows))
    r.stop()


def test_an_x_connection_that_cannot_be_opened_fails_the_start_so_the_in_app_companion_stays() -> None:
    w = FakeX()
    w.fail_create = True
    r, _w, _c = make(w)
    assert r.start() is False


# --- a real X server -------------------------------------------------------------------------------------


def _xvfb(attempt: int = 0) -> Any:
    # An explicit display number per process, not `-displayfd` alone: with no number, Xvfb scans from :0 and
    # binds each candidate's socket before it checks the lock, unlinking the socket of a sibling server that
    # already owns that number (CI, Python 3.13 on 3fe47f5: three tries in a row on :0, "cannot open the X
    # display"). Given a number, Xvfb checks the lock first and exits if it is taken, so a clash costs a retry.
    if not (shutil.which("Xvfb") and xlib.libraries_present()):
        pytest.skip("Xvfb or libX11 is not installed")
    number = 1000 + (os.getpid() * 37 + attempt * 7919) % 30000
    rd, wr = os.pipe()
    proc = subprocess.Popen(["Xvfb", f":{number}", "-displayfd", str(wr), "-screen", "0", "1024x768x24", "-nolisten", "tcp"], pass_fds=(wr,), stderr=subprocess.DEVNULL)
    os.close(wr)
    # Read to the newline before closing the pipe (INBOX 1683 s, the real race: Xvfb writes the number and the newline
    # as two writes, and a reader that took the number alone and closed its end made the second write fail, "Cannot
    # write display number to fd", and the server exit, which only happened when the box was loaded enough to split
    # them). End of file (the server died) also ends the read.
    raw = b""
    while not raw.endswith(b"\n"):
        chunk = os.read(rd, 16)
        if not chunk:
            break
        raw += chunk
    num = raw.decode().strip()
    os.close(rd)
    if not num:
        proc.kill()
        proc.wait()
        return None, f":{number}"
    return proc, f":{num}"


def _connect(display: str, seconds: float = 60.0, proc: Any = None) -> Any:
    # Wait on the server, not on a guess (INBOX 1683 s: the test failed once in a few runs under -n 4, three attempts of
    # 15 s each "cannot open the X display" while the server was alive but starved of CPU, compiling its keymap): the
    # wait ends when the server process has exited (retry with a new one) or after a minute, whichever comes first.
    end = time.monotonic() + seconds
    while True:
        try:
            return xlib.XConn.open(display)
        except OSError:
            if time.monotonic() > end or (proc is not None and proc.poll() is not None):
                raise
            time.sleep(0.1)


def _server() -> Any:
    """(process, connection): a server started again when two runs of this test (a gate beside a
    test run) raced for the same display number and one of them lost its socket."""
    proc, conn, _display = _server_at()
    return proc, conn


def _server_at() -> Any:
    """(process, connection, display name), with `_server`'s retry."""
    last: Exception | None = None
    started = False
    for attempt in range(3):
        proc, display = _xvfb(attempt)
        if proc is None:
            last = OSError(f"Xvfb did not start on {display}")
            continue
        started = True
        try:
            return proc, _connect(display, proc=proc), display
        except OSError as exc:
            last = exc
            proc.kill()
            proc.wait()
    if not started:
        pytest.skip(f"Xvfb did not start: {last}")
    raise AssertionError(f"no X server could be reached: {last}")


def test_on_a_real_server_the_window_is_placed_shaped_to_the_figure_and_the_desktop_is_read() -> None:
    proc, conn = _server()
    try:
        assert conn.rr_monitors() == [(0, 0, 1024, 768)]
        win = conn.create_window("t")
        w, h = 40, 40
        rows = b"".join((bytes([0, 0, 200, 255]) * 20 + bytes(80)) if y < 20 else bytes(160) for y in range(h))  # opaque top-left quarter
        conn.present(win, rows, w, h, 100, 100)
        conn.map(win)
        assert conn.geometry(win) == (100, 100, 40, 40)
        assert conn.depth == 32
        conn.move(win, 300, 200)
        assert conn.geometry(win) == (300, 200, 40, 40)
        bits = xlib.alpha_bitmap(rows[3::4], w, h)
        stride = (w + 7) // 8
        assert bits is not None and len(bits) == stride * h and bits[0] == 0xFF and bits[stride * 25] == 0
        conn.set_prop(conn.root, "_NET_WORKAREA", "CARDINAL", [0, 0, 1024, 740])
        assert conn.prop(conn.root, "_NET_WORKAREA") == [0, 0, 1024, 740]
        assert x11.work_areas(conn) == [(0, 0, 1024, 740)]
        conn.close()
    finally:
        proc.terminate()  # not kill: SIGTERM lets Xvfb remove its lock and socket for the next test
        proc.wait()


def test_on_a_real_server_a_destroyed_window_is_an_error_value_not_a_process_exit() -> None:
    """Xlib's default error handler calls exit(); the runner scans windows that can close at any moment."""
    code = (
        "import sys; from tessellate.core.overlay import xlib\n"
        "c = xlib.XConn.open(sys.argv[1])\n"
        "gone = 0x600001\n"
        "assert c.prop(gone, '_NET_WM_STATE') is None\n"
        "assert c.geometry(gone) is None\n"
        "c.window_xy(gone)\n"
        "assert c.errors and c.errors[0][0] == 3\n"
        "print('survived')\n"
    )
    # A server this process could reach (with _server's retry), so the child does not lose a race
    # for the display with another real-server test running beside it (-n).
    proc, conn, display = _server_at()
    try:
        conn.close()
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        out = subprocess.run([sys.executable, "-c", code, display], capture_output=True, text=True, timeout=30, env=env)
        if "cannot open the X display" in out.stderr:  # CI without a reachable server: skip, as the siblings do
            pytest.skip("no X server reachable from the child process")
        assert "survived" in out.stdout, (out.returncode, out.stderr)
    finally:
        proc.terminate()  # not kill: SIGTERM lets Xvfb remove its lock and socket for the next test
        proc.wait()


def test_two_different_frames_never_share_a_cut_shape_key() -> None:
    a, b = bytes(range(256)) * 4, bytes(reversed(range(256))) * 4
    assert xlib.shape_key(a[3::4], 16, 16) != xlib.shape_key(b[3::4], 16, 16)
    assert xlib.shape_key(a[3::4], 16, 16) != xlib.shape_key(a[3::4], 8, 32)


# --- the companion's wiring on Linux ----------------------------------------------------------------------


def test_the_default_factory_is_the_overlay_on_x11_and_none_with_a_note_on_wayland(monkeypatch, caplog) -> None:
    from tessellate.core import desk_companion as dc

    monkeypatch.setattr(dc.sys, "platform", "linux")
    for k in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "TESSELLATE_OVERLAY_X11"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(xlib, "libraries_present", lambda: True)
    monkeypatch.setenv("DISPLAY", ":0")
    assert dc._default_overlay_factory() is runner_mod.OverlayRunner and dc.OVERLAY_NOTE == ""
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    caplog.set_level("INFO", logger=dc.logger.name)
    assert dc._default_overlay_factory() is None
    assert "Wayland" in dc.OVERLAY_NOTE and any("Wayland" in r.getMessage() for r in caplog.records)
    monkeypatch.setattr(dc.sys, "platform", "darwin")
    assert dc._default_overlay_factory() is None and dc.OVERLAY_NOTE == ""


def test_the_cards_menu_carries_the_note_and_the_panel_is_a_plain_window_when_the_figure_runs(monkeypatch, prefs) -> None:  # noqa: F811
    from tessellate.core import desk_companion as dc
    from tests.test_desk_companion import FakeWebview, FakeWindow

    monkeypatch.setattr(dc, "_default_overlay_factory", lambda: None)
    monkeypatch.setattr(dc, "OVERLAY_NOTE", "This is a Wayland session, so the companion stays in the app.")
    c = dc.attach(FakeWebview(), FakeWindow(), lambda *_a: None, lambda: "http://x", transparent=None)
    assert c.overlay_note.endswith("stays in the app.") and dc.DeskApi(c).panel_motion()["note"] == c.overlay_note
    c.overlay_note = ""
    assert "note" not in dc.DeskApi(c).panel_motion()


def test_the_work_area_on_linux_is_read_from_the_x_server_in_logical_pixels(monkeypatch) -> None:
    from tessellate.core import desk_companion as dc

    w = FakeX()
    w.dpi = 192.0
    w.add_window(10, (0, 1040, 1920, 40), kinds=["_NET_WM_WINDOW_TYPE_DOCK"])
    w.props[10]["_NET_WM_STRUT_PARTIAL"] = [0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 1919]
    monkeypatch.setattr(dc.sys, "platform", "linux")
    monkeypatch.setattr(dc, "overlay_support", lambda: (True, ""))
    monkeypatch.setattr(x11, "load", lambda: w)
    assert dc.monitor_areas() == [(0, 0, 960, 520)] and dc.work_area() == (0, 0, 960, 520)
    monkeypatch.setattr(dc, "overlay_support", lambda: (False, "wayland"))
    assert dc.monitor_areas() == [] and dc.work_area() is None


# --- both platforms, one contract ---------------------------------------------------------------------------


def _windows_side():
    from tessellate.core.overlay import win32
    from tests._overlay_fake import FakeWin32

    fake = FakeWin32()
    return win32, fake, lambda: len(fake.layered), lambda: "ShowWindow" in fake.names()


def _x_side():
    fake = FakeX()
    return x11, fake, lambda: len(fake.presented), lambda: "map" in fake.names()


@pytest.mark.parametrize("side", [_windows_side, _x_side], ids=["windows", "x11"])
def test_the_runner_and_engine_behave_the_same_on_both_hosts(side) -> None:
    backend, fake, drawn, shown = side()
    clock = Clock()
    r = runner_mod.OverlayRunner(backend=backend, w=fake, clock=clock, frames=FRAMES, dispatch=lambda n, f: f(), home=(800, 920), reduced=False)
    r.clock_hour = 13
    assert r.start() and r.engine is not None and r.sprites is not None
    assert drawn() >= 1 and not shown()  # the first frame, hidden
    assert r.engine.size == r.sprites.size(96) and r.engine.current_monitor().area == (0, 0, 1920, 1040 if backend.__name__.endswith("win32") else 1080)
    r.show()
    assert wait_for(shown)
    before = drawn()
    for _ in range(40):  # a walk of the engine: positions are whole pixels inside the work area, and frames are drawn
        clock.t += 0.05
        out = r.engine.update(clock.t)
        assert isinstance(out.x, int) and isinstance(out.y, int)
        area = r.engine.current_monitor().area
        assert area[0] <= out.x <= area[2] and out.y <= area[3]
        r._apply(out)
    assert drawn() >= before
    r.hide()
    host = r.host
    r.stop()
    assert not host.alive


def test_linux_areas_reads_the_monitors_once(monkeypatch) -> None:
    from tessellate.core import desk_companion as dc

    calls = []

    class Conn:
        def close(self) -> None:
            pass

    monkeypatch.setattr(dc, "overlay_support", lambda: (True, ""))
    monkeypatch.setattr(x11, "load", lambda: Conn())
    monkeypatch.setattr(x11, "monitors", lambda conn: calls.append(1) or [((0, 0, 100, 100), 96)])
    monkeypatch.setattr(x11, "work_areas", lambda conn: [(0, 0, 100, 90)])
    assert dc._linux_areas() == [(0, 0, 100, 90)] and len(calls) == 1


def test_a_failed_overlay_start_shows_the_note_on_every_platform(monkeypatch, prefs) -> None:  # noqa: F811
    from tessellate.core import desk_companion as dc
    from tests.test_desk_companion import FakeWebview, FakeWindow

    monkeypatch.setattr(dc.sys, "platform", "win32")
    c = dc.attach(FakeWebview(), FakeWindow(), lambda *_a: None, lambda: "http://x", transparent=None, overlay_factory=None)
    c.overlay_failed = True
    assert "could not start" in dc.DeskApi(c).panel_motion()["note"]
