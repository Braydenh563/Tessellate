"""The Linux half of the overlay: the same figure, on an X11 desktop.

`OverlayRunner` takes a backend that offers `load`, `monitors`, `windows`,
`last_input_age`, `caret_rect`, `text_zone`, `notification_state`, `animations_enabled`, `dpi_at_point` and a
`Host`; `win32` is one and this is the other. The engine is not touched: it gets
the same monitors, window tops and pointer events.

**The window** (`xlib.XConn.create_window`): override-redirect on a 32-bit ARGB
visual, so no window manager frames it, lists it on a taskbar or gives it focus,
and it sits exactly where the engine puts it (a managed window is clamped to the
work area, which would keep it from tucking behind an edge). Its input shape is
cut to the figure's alpha, so a click on a clear pixel reaches the window below
(click-through except the figure). Where no compositor runs, the bounding shape
is cut the same way, so the clear part is not drawn black.

**On top.** An override-redirect window is not kept above by the window manager,
so the host raises it on show and again, a fifth of a second after the root's
`_NET_CLIENT_LIST_STACKING` changes (a window opened or raised), which is an
event and not a poll.

**Facts from EWMH, not guesses.** The work area is the monitor minus the struts
that panels reserve (`_NET_WM_STRUT_PARTIAL`), else `_NET_WORKAREA`; the windows
to stand on come from `_NET_CLIENT_LIST_STACKING` with each one's state and frame
extents; something full screen (`_NET_WM_STATE_FULLSCREEN` on the top window of
the current desktop) hides the figure like a game does on Windows.

**Wayland** does not let an app put a window at a place on the whole screen or
above others, or list other apps' windows. `support()` says so and the companion
stays the in-app one with a note; `TESSELLATE_OVERLAY_X11=1` tries XWayland.

Not checked on a real desktop session here: see desk-1670.md for what ran on Xvfb.
"""

from __future__ import annotations

import logging
import os
import queue
import select
import subprocess
import threading
import time
from typing import Any, Callable

from tessellate.core import jobs
from tessellate.core.overlay import xlib
from tessellate.core.overlay.win32 import WinInfo

logger = logging.getLogger(__name__)

#: `notification_state` answers this while a full screen window is up (the Windows
#: names are numbers; the runner only asks whether the answer is in `QUNS_HIDE`).
FULLSCREEN = "fullscreen"
FREE = "free"
QUNS_HIDE = frozenset({FULLSCREEN})
#: Raised again this long after the stack changed (seconds): one raise for a burst.
RERAISE_AFTER = 0.2
UNSET = 0xFFFFFFFF
#: Window types that can be stood on; a window with no type is a normal one.
PERCHABLE = frozenset({"_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_WINDOW_TYPE_DIALOG"})
#: Types that never hide or carry anything: not listed at all.
IGNORED = frozenset({
    "_NET_WM_WINDOW_TYPE_DESKTOP", "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU", "_NET_WM_WINDOW_TYPE_POPUP_MENU",
    "_NET_WM_WINDOW_TYPE_TOOLTIP", "_NET_WM_WINDOW_TYPE_NOTIFICATION", "_NET_WM_WINDOW_TYPE_COMBO",
    "_NET_WM_WINDOW_TYPE_DND",
})
TITLE = "Tessellate companion"


# --- session ------------------------------------------------------------------------------


def support(env: "dict[str, str] | None" = None, have_lib: "Callable[[], bool] | None" = None) -> tuple[bool, str]:
    """(usable, one-line note). The note is empty when the see-through figure can run."""
    e = os.environ if env is None else env
    wayland = e.get("XDG_SESSION_TYPE", "").lower() == "wayland" or bool(e.get("WAYLAND_DISPLAY"))
    if wayland and e.get("TESSELLATE_OVERLAY_X11") != "1":
        return False, "This is a Wayland session, which does not let an app place a window above others, so the companion stays in the app."
    if not e.get("DISPLAY"):
        return False, "No X11 display was found, so the companion stays in the app."
    if not (have_lib or xlib.libraries_present)():
        return False, "libX11 is not installed, so the companion stays in the app."
    return True, ""


def load() -> Any:
    """The display connection (OSError when there is none)."""
    return xlib.XConn.open()


# --- what the desktop says ------------------------------------------------------------------


def _scale(w: Any) -> float:
    dpi = w.resource_dpi()
    if dpi and 48 <= dpi <= 480:
        return dpi
    try:
        factor = float(os.environ.get("GDK_SCALE") or os.environ.get("QT_SCALE_FACTOR") or 1)
    except ValueError:
        factor = 1.0
    return 96.0 * factor if 0.5 <= factor <= 5 else 96.0


def _struts(w: Any) -> list[tuple[int, int, int, int, int, int, int, int, int, int, int, int]]:
    found = []
    for win in w.prop(w.root, "_NET_CLIENT_LIST") or []:
        if not isinstance(win, int):
            continue
        s = w.prop(win, "_NET_WM_STRUT_PARTIAL")
        if isinstance(s, list) and len(s) >= 12:
            found.append(tuple(int(v) for v in s[:12]))
    return found  # type: ignore[return-value]


def work_areas(w: Any) -> list[tuple[int, int, int, int]]:
    """Each monitor as (left, top, right, bottom) minus the panels' struts; when no panel
    reserves any, the monitor clipped to `_NET_WORKAREA` of the current desktop."""
    shapes = [(x, y, x + wd, y + ht) for x, y, wd, ht in w.rr_monitors()]
    struts = _struts(w)
    out = []
    for left, top, right, bottom in shapes:
        a = [left, top, right, bottom]
        for sl, sr, st, sb, lys, lye, rys, rye, txs, txe, bxs, bxe in struts:
            if sl and lys < bottom and lye >= top:
                a[0] = max(a[0], sl)
            if sr:
                screen_right = max(s[2] for s in shapes)
                if rys < bottom and rye >= top and screen_right - sr < right:
                    a[2] = min(a[2], screen_right - sr)
            if st and txs < right and txe >= left:
                a[1] = max(a[1], st)
            if sb and bxs < right and bxe >= left:
                screen_bottom = max(s[3] for s in shapes)
                if screen_bottom - sb < bottom:
                    a[3] = min(a[3], screen_bottom - sb)
        out.append(tuple(a))
    if not struts:
        wa = w.prop(w.root, "_NET_WORKAREA")
        desk = w.prop(w.root, "_NET_CURRENT_DESKTOP")
        index = desk[0] if isinstance(desk, list) and desk else 0
        if isinstance(wa, list) and len(wa) >= 4 * (index + 1):
            x, y, wd, ht = wa[4 * index: 4 * index + 4]
            out = [
                (max(a[0], x), max(a[1], y), min(a[2], x + wd), min(a[3], y + ht)) if min(a[2], x + wd) > max(a[0], x) and min(a[3], y + ht) > max(a[1], y) else a
                for a in out
            ]
    return [a for a in out if a[2] > a[0] and a[3] > a[1]]  # type: ignore[misc]


def monitors(w: Any) -> list[tuple[tuple[int, int, int, int], int]]:
    """(work area, dpi) of each monitor, primary first. X reports physical pixels, so the
    dpi is the desktop's own (Xft.dpi, else GDK_SCALE) and the figure is drawn at that size."""
    dpi = int(round(_scale(w)))
    return [(a, dpi) for a in work_areas(w)]


def dpi_at_point(w: Any, x: int, y: int) -> int | None:
    try:
        return int(round(_scale(w)))
    except Exception:  # noqa: BLE001 - the runner has its own list to fall back on
        return None


def cursor_pos(w: Any) -> tuple[int, int]:
    return w.pointer()


def last_input_age(w: Any) -> float | None:
    ms = w.idle_ms()
    return None if ms is None else ms / 1000.0


def caret_rect(_w: Any) -> None:
    """X11 offers no text caret to other apps (AT-SPI would, but it is not asked): the engine's
    text-zone stand-in is not used here either, so the figure only keeps its home by an edge."""
    return None


def text_zone(_w: Any) -> None:
    return None


def animations_enabled(w: Any) -> bool:
    """GNOME's `enable-animations`; true where it cannot be asked (KDE and the rest do not
    switch the figure to still: the Companion movement setting does)."""
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"],
            capture_output=True, text=True, timeout=1.5, check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return True
    return out != "false"


def _stack(w: Any) -> list[int]:
    return [v for v in (w.prop(w.root, "_NET_CLIENT_LIST_STACKING") or []) if isinstance(v, int)]


def _current_desktop(w: Any) -> int | None:
    d = w.prop(w.root, "_NET_CURRENT_DESKTOP")
    return d[0] if isinstance(d, list) and d else None


def _on_desktop(w: Any, win: int, current: int | None) -> bool:
    d = w.prop(win, "_NET_WM_DESKTOP")
    if not isinstance(d, list) or not d or current is None:
        return True
    return d[0] in (current, UNSET)


def _state(w: Any, win: int) -> set[str]:
    s = w.prop(win, "_NET_WM_STATE")
    return {v for v in s if isinstance(v, str)} if isinstance(s, list) else set()


def notification_state(w: Any) -> str | None:
    """`fullscreen` while the top window of the current desktop is full screen (a video,
    a game, a presentation), else `free`; None when the desktop gives no window list."""
    ids = _stack(w)
    if not ids and w.prop(w.root, "_NET_CLIENT_LIST_STACKING") is None:
        return None
    current = _current_desktop(w)
    for win in reversed(ids):
        state = _state(w, win)
        if "_NET_WM_STATE_HIDDEN" in state or not _on_desktop(w, win, current):
            continue
        if w.geometry(win) is None:
            continue
        return FULLSCREEN if "_NET_WM_STATE_FULLSCREEN" in state else FREE
    return FREE


def _read_window(w: Any, win: int, own_pid: int, ignore: Any, areas: list[tuple[int, int, int, int]], current: int | None) -> WinInfo | None:
    if win == ignore:
        return None
    state = _state(w, win)
    if "_NET_WM_STATE_HIDDEN" in state or not _on_desktop(w, win, current):
        return None
    kinds = w.prop(win, "_NET_WM_WINDOW_TYPE")
    kinds = {k for k in kinds if isinstance(k, str)} if isinstance(kinds, list) else set()
    if kinds & IGNORED:
        return None
    geo = w.geometry(win)
    if geo is None:
        return None
    x, y, wd, ht = geo
    ext = w.prop(win, "_NET_FRAME_EXTENTS")
    left, right, top, bottom = (ext[:4] if isinstance(ext, list) and len(ext) >= 4 else [0, 0, 0, 0])
    rect = (x - left, y - top, x + wd + right, y + ht + bottom)
    pid = w.prop(win, "_NET_WM_PID")
    title = w.prop(win, "_NET_WM_NAME") or w.prop(win, "WM_NAME")
    maximised = {"_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ"} <= state
    fills = any(rect[0] <= a[0] and rect[1] <= a[1] and rect[2] >= a[2] and rect[3] >= a[3] for a in areas)
    normal = not kinds or bool(kinds & PERCHABLE)
    mine = isinstance(pid, list) and bool(pid) and pid[0] == own_pid
    perch = normal and not mine and not maximised and not (state & {"_NET_WM_STATE_FULLSCREEN"}) and not fills and bool(title)
    return WinInfo(win, rect, perch)


def windows(w: Any, own_pid: int, ignore: int | None, monitors_: list[tuple[int, int, int, int]]) -> list[WinInfo]:
    """Visible windows of the current desktop, topmost first. Read only."""
    current = _current_desktop(w)
    found: list[WinInfo] = []
    for win in reversed(_stack(w)):
        try:
            info = _read_window(w, win, own_pid, ignore, monitors_, current)
        except Exception:  # noqa: BLE001 - one odd window never ends the walk
            logger.debug("overlay: a window could not be read", exc_info=True)
            continue
        if info is not None:
            found.append(info)
    return found


# --- the window and its loop ----------------------------------------------------------------

EventHandler = Callable[[str, int, int], "int | None"]


class X11Host:
    """What `OverlayHost` is on Windows: one window on its own thread, driven by calls
    from any thread (`present`, `move`, `show`, `hide`, `wake`, `stop`) and answering the
    runner's `on_event`. The loop blocks in `select` on the X connection and a wake pipe,
    for as long as the next timer asks, so a standing figure costs nothing between blinks."""

    def __init__(self, w: Any, on_event: EventHandler | None = None, on_exit: Callable[[], Any] | None = None) -> None:
        self.w = w
        self.on_event = on_event
        self.on_exit = on_exit
        self._stopping = False
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: str | None = None
        self._queue: queue.SimpleQueue[tuple[Any, ...]] = queue.SimpleQueue()
        self._rd, self._wr = os.pipe()
        self.hwnd: int | None = None
        self._tid: int | None = None
        self._deadline: float | None = None
        self._reraise_at: float | None = None
        self._done = False
        self._grabbed = False
        self.pos = (0, 0)
        self._size = (0, 0)
        self.visible = False
        self._drawn = False
        self._logged_ok = False

    # --- life ------------------------------------------------------------------------------

    def start(self, timeout: float = 3.0) -> bool:
        if self._thread is not None:
            return self.alive
        self._thread = jobs.thread("tessellate-overlay-x11", self._run)
        if not self._ready.wait(timeout):
            logger.warning("overlay: the window thread did not start within %.1f s", timeout)
            return False
        if self._error:
            logger.warning("overlay: the window could not be made (%s)", self._error)
            return False
        return True

    @property
    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self.hwnd)

    def stop(self, timeout: float = 1.0) -> bool:
        thread = self._thread
        if thread is None:
            return True
        self._stopping = True
        self._queue.put(("close",))
        self._poke()
        thread.join(timeout)
        ended = not thread.is_alive()
        if not ended:
            logger.warning("overlay: the window thread did not end within %.1f s", timeout)
        return ended

    # --- calls from any thread ----------------------------------------------------------------

    def _poke(self) -> None:
        if self._wr < 0:
            return  # the thread has ended and its pipe is closed (the number may be someone else's now)
        try:
            os.write(self._wr, b"x")
        except OSError:
            pass

    def _call(self, *command: Any) -> None:
        if threading.get_ident() == self._tid:
            self._apply(command)
            return
        self._queue.put(command)
        self._poke()

    def present(self, bgra: bytes, width: int, height: int, x: int, y: int) -> None:
        self._call("present", bgra, int(width), int(height), int(x), int(y))

    def move(self, x: int, y: int) -> None:
        self._call("move", int(x), int(y))

    def show(self) -> None:
        self._call("show")

    def hide(self) -> None:
        self._call("hide")

    def wake(self, ms: int) -> None:
        self._call("wake", int(ms))

    def reassert(self) -> None:
        self._call("topmost")

    # --- the window's thread ----------------------------------------------------------------

    def _run(self) -> None:
        self._tid = threading.get_ident()
        try:
            self.hwnd = int(self.w.create_window(TITLE))
            if self.on_event is not None:
                self.on_event("ready", 0, 0)
        except Exception as exc:  # noqa: BLE001 - reported to start(); the coordinator falls back
            logger.warning("overlay: setup failed", exc_info=True)
            self._error = f"{type(exc).__name__}: {exc}"
            self._ready.set()
            self._teardown()
            return
        self._ready.set()
        try:
            self._pump()
        except Exception:  # noqa: BLE001 - the thread ends, the app does not
            logger.warning("overlay: the event loop failed", exc_info=True)
        finally:
            self._teardown()
        if self.on_exit is not None and not self._stopping:
            try:
                self.on_exit()
            except Exception:  # noqa: BLE001
                logger.warning("overlay: the exit callback failed", exc_info=True)

    def _pump(self) -> None:
        fd = self.w.fileno()
        while not self._done:
            self._drain()
            self._read_events()
            if self._done:
                return
            now = time.monotonic()
            due = [t for t in (self._deadline, self._reraise_at) if t is not None]
            wait = None if not due else max(0.0, min(due) - now)
            ready, _, _ = select.select([fd, self._rd], [], [], wait)
            if self._rd in ready:
                try:
                    os.read(self._rd, 4096)
                except OSError:
                    return
            now = time.monotonic()
            if self._reraise_at is not None and now >= self._reraise_at:
                self._reraise_at = None
                self.reassert_now()
            if self._deadline is not None and now >= self._deadline:
                self._deadline = None
                self._event("tick")

    def _drain(self) -> None:
        while True:
            try:
                command = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                self._apply(command)
            except Exception:  # noqa: BLE001 - one bad command leaves the rest
                logger.warning("overlay: command %s failed", command[0], exc_info=True)

    def _read_events(self) -> None:
        for kind, x, y in self.w.events():
            if kind == "down":
                if not self._grabbed:
                    self.w.grab_pointer(self.hwnd)
                    self._grabbed = True
                self._event("down")
            elif kind == "up":
                self._release()
                self._event("up")
            elif kind in ("move", "right"):
                self._event(kind)
            elif kind == "expose":
                self.w.redraw(self.hwnd)
            elif kind == "display":
                self._event("display")
                self._reraise_at = time.monotonic() + RERAISE_AFTER
            elif kind == "stack":
                self._reraise_at = time.monotonic() + RERAISE_AFTER

    def _release(self) -> None:
        if self._grabbed:
            self._grabbed = False
            self.w.ungrab_pointer()

    def _teardown(self) -> None:
        for step in (self._release, lambda: self.hwnd and self.w.destroy(self.hwnd)):
            try:
                step()
            except Exception:  # noqa: BLE001 - tearing down: keep going to the next resource
                logger.debug("overlay: a resource was not released", exc_info=True)
        self.hwnd = None
        self.visible = False
        self._done = True
        rd, wr, self._rd, self._wr = self._rd, self._wr, -1, -1
        for fd in (rd, wr):
            try:
                os.close(fd)
            except OSError:
                pass

    def _event(self, kind: str) -> None:
        if self.on_event is None:
            return
        x, y = cursor_pos(self.w)
        try:
            wake = self.on_event(kind, x, y)
        except Exception:  # noqa: BLE001 - a behaviour bug never reaches the loop
            logger.warning("overlay: handler failed on %s", kind, exc_info=True)
            return
        if wake is not None:
            self._set_timer(wake)

    def _set_timer(self, ms: int) -> None:
        self._deadline = time.monotonic() + max(10, int(ms)) / 1000.0

    # --- commands, on the window's thread ----------------------------------------------------

    def _apply(self, command: tuple[Any, ...]) -> None:
        name = command[0]
        if name == "close":
            self._done = True
            return
        if not self.hwnd:
            return
        if name == "present":
            _n, bgra, width, height, x, y = command
            self.w.present(self.hwnd, bgra, width, height, x, y)
            self.pos, self._size, self._drawn = (x, y), (width, height), True
        elif name == "move":
            if (command[1], command[2]) != self.pos:
                self.pos = (command[1], command[2])
                self.w.move(self.hwnd, *self.pos)
        elif name == "show":
            self.w.map(self.hwnd)
            self.visible = True
            self.reassert_now()
            self._log_ok()
        elif name == "hide":
            self._deadline = None
            self._release()
            self.w.unmap(self.hwnd)
            self.visible = False
        elif name == "wake":
            self._set_timer(command[1])
        elif name == "topmost":
            self.reassert_now()

    def reassert_now(self) -> None:
        if self.hwnd and self.visible:
            self.w.raise_window(self.hwnd)

    def rect(self) -> tuple[int, int, int, int] | None:
        if not self.hwnd:
            return None
        return self.pos[0], self.pos[1], self.pos[0] + self._size[0], self.pos[1] + self._size[1]

    def _log_ok(self) -> None:
        if self._logged_ok:
            return
        self._logged_ok = True
        logger.info("overlay: X11 window ok, rect=%s, drawn=%s", self.rect(), self._drawn)


Host = X11Host
