"""The overlay's window and message loop: one layered popup on its own thread.

A `WS_POPUP` window with `WS_EX_LAYERED | TOOLWINDOW | TOPMOST | NOACTIVATE`:
no taskbar button, no Alt+Tab entry, never takes focus. It is drawn with
`UpdateLayeredWindow` (`ULW_ALPHA`) from a reusable DIB section holding
premultiplied BGRA, so the clear pixels are truly clear and, because Windows
does not hit-test alpha-0 pixels of a layered window, let clicks through.
A move is a bare `SetWindowPos` (position only); a redraw happens only when the
frame changes.

**Threads.** Win32 state belongs to the thread that made the window. Every
other thread calls `present`, `move`, `show`, `hide`, `wake` or `stop`, which
queue a command and `PostMessage(WM_APP + 1)` to the window; the window
procedure drains the queue. The loop blocks in `GetMessageW` (no sleep-and-poll)
and is woken by `SetTimer` only when the behaviour asks for a next step, so a
standing figure costs nothing between blinks.

**Never raises into Windows.** The window procedure is held in a module-level
reference (a garbage-collected callback crashes the process) and wrapped so any
exception is logged and answered with `DefWindowProcW`.

The thread opts into per-monitor-V2 dpi awareness for itself, so its pixels
are physical whatever the rest of the process (pywebview's system awareness) does.

Not run on Windows (the sandbox has none): the tests drive a fake `win32`.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
from typing import Any, Callable

from tessellate.core.overlay import win32 as k

logger = logging.getLogger(__name__)

CLASS_NAME = "TessellateOverlayWindow"
#: Posted by other threads: "the queue has something".
WM_QUEUE = k.WM_APP + 1
TIMER_ID = 1
#: A timer shorter than this is a busy loop (Windows rounds to about 15.6 ms anyway).
MIN_WAKE_MS = 10

#: window procedures in use, by host: kept alive for as long as Windows may call them.
_CALLBACKS: list[Any] = []

#: What `on_event` hears: (kind, screen x, screen y) -> the next wake in ms, or None.
EventHandler = Callable[[str, int, int], "int | None"]


def premultiplied_dib_bytes(width: int, height: int) -> int:
    """Bytes in a 32-bit bitmap of this size."""
    return int(width) * int(height) * 4


class OverlayHost:
    def __init__(self, w: Any, on_event: EventHandler | None = None) -> None:
        self.w = w
        self.on_event = on_event
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: str | None = None
        self._queue: queue.SimpleQueue[tuple[Any, ...]] = queue.SimpleQueue()
        self.hwnd: int | None = None
        self._tid: int | None = None
        self._proc: Any = None
        self._screen_dc: Any = None
        self._mem_dc: Any = None
        self._bitmap: Any = None
        self._old_bitmap: Any = None
        self._bits = ctypes.c_void_p()
        self._size = (0, 0)
        self.pos = (0, 0)
        self.visible = False
        self._taskbar_msg = 0
        self._handlers = self._build_handlers()
        self._drawn = False
        self._logged_ok = False

    # --- life ------------------------------------------------------------------

    def start(self, timeout: float = 3.0) -> bool:
        """Make the window on its own thread; True once it exists."""
        if self._thread is not None:
            return self.alive
        self._thread = threading.Thread(target=self._run, name="tessellate-overlay", daemon=True)
        self._thread.start()
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
        """WM_CLOSE to the window, then wait for its thread. True when it ended in time."""
        thread = self._thread
        if thread is None:
            return True
        if self.hwnd:
            self.w.user32.PostMessageW(self.hwnd, k.WM_CLOSE, 0, 0)
        thread.join(timeout)
        ended = not thread.is_alive()
        if not ended:
            logger.warning("overlay: the window thread did not end within %.1f s", timeout)
        return ended

    # --- calls from any thread ------------------------------------------------------

    def _call(self, *command: Any) -> None:
        if threading.get_ident() == self._tid:
            self._apply(command)
            return
        self._queue.put(command)
        if self.hwnd:
            self.w.user32.PostMessageW(self.hwnd, WM_QUEUE, 0, 0)

    def present(self, bgra: bytes, width: int, height: int, x: int, y: int) -> None:
        """Draw a premultiplied BGRA frame with its top-left at (x, y)."""
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

    # --- the window's thread ------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._setup()
            if self.on_event is not None:
                #: Once, on this thread, with the window made: the owner builds what
                #: needs this thread's dpi awareness. An exception is a failed start.
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
            logger.warning("overlay: the message loop failed", exc_info=True)
        finally:
            self._teardown()

    def _setup(self) -> None:
        u = self.w.user32
        self._tid = threading.get_ident()
        aware = getattr(u, "SetThreadDpiAwarenessContext", None)
        if aware is not None:
            try:
                aware(k.DPI_PER_MONITOR_V2)
            except Exception:  # noqa: BLE001 - an older Windows: pixels stay as the process has them
                logger.debug("overlay: per-monitor dpi awareness not set", exc_info=True)
        self._taskbar_msg = int(u.RegisterWindowMessageW("TaskbarCreated") or 0)
        instance = self.w.kernel32.GetModuleHandleW(None)
        self._proc = k.WNDPROC(self._wndproc)
        _CALLBACKS.append(self._proc)
        cls = k.WNDCLASSEXW()
        cls.cbSize = ctypes.sizeof(k.WNDCLASSEXW)
        cls.lpfnWndProc = self._proc
        cls.hInstance = instance
        cls.hCursor = u.LoadCursorW(None, k.IDC_ARROW)
        cls.lpszClassName = CLASS_NAME
        if not u.RegisterClassExW(ctypes.byref(cls)):
            raise OSError(f"RegisterClassExW failed (error {k.last_error()})")
        hwnd = u.CreateWindowExW(
            k.EX_STYLE, CLASS_NAME, "Tessellate companion", k.WS_POPUP, 0, 0, 1, 1, None, None, instance, None
        )
        if not hwnd:
            raise OSError(f"CreateWindowExW failed (error {k.last_error()})")
        self.hwnd = int(hwnd)
        self._screen_dc = self.w.user32.GetDC(None)
        self._mem_dc = self.w.gdi32.CreateCompatibleDC(self._screen_dc)

    def _pump(self) -> None:
        u = self.w.user32
        msg = k.MSG()
        while True:
            got = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if got <= 0:
                return
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))

    def _teardown(self) -> None:
        g, u = self.w.gdi32, self.w.user32
        for step in (
            lambda: self._old_bitmap and g.SelectObject(self._mem_dc, self._old_bitmap),
            lambda: self._bitmap and g.DeleteObject(self._bitmap),
            lambda: self._mem_dc and g.DeleteDC(self._mem_dc),
            lambda: self._screen_dc and u.ReleaseDC(None, self._screen_dc),
            lambda: self.hwnd and u.DestroyWindow(self.hwnd),
            lambda: u.UnregisterClassW(CLASS_NAME, self.w.kernel32.GetModuleHandleW(None)),
        ):
            try:
                step()
            except Exception:  # noqa: BLE001 - tearing down: keep going to the next resource
                logger.debug("overlay: a resource was not released", exc_info=True)
        self._bitmap = self._mem_dc = self._screen_dc = None
        self.hwnd = None
        self.visible = False
        if self._proc in _CALLBACKS:
            _CALLBACKS.remove(self._proc)

    # --- the window procedure ----------------------------------------------------------

    def _wndproc(self, hwnd: Any, msg: int, wparam: int, lparam: int) -> int:
        try:
            handled = self._message(hwnd, msg, wparam, lparam)
            if handled is not None:
                return handled
        except Exception:  # noqa: BLE001 - an exception must never cross into Windows
            logger.warning("overlay: message %#x failed", msg, exc_info=True)
        return int(self.w.user32.DefWindowProcW(hwnd, msg, wparam, lparam) or 0)

    def _message(self, hwnd: Any, msg: int, wparam: int, lparam: int) -> int | None:
        """The result for a message this window handles, else None (DefWindowProcW)."""
        if self._taskbar_msg and msg == self._taskbar_msg:
            #: The taskbar was rebuilt (Explorer restarted): topmost is lost with it.
            self.reassert_now()
            self._event("taskbar")
            return 0
        handler = self._handlers.get(msg)
        return handler(hwnd, wparam) if handler else None

    def _build_handlers(self) -> dict[int, Callable[[Any, int], int | None]]:
        return {
            WM_QUEUE: self._on_queue,
            k.WM_TIMER: self._on_timer,
            k.WM_LBUTTONDOWN: self._on_down,
            k.WM_MOUSEMOVE: lambda _h, _w: self._answered("move"),
            k.WM_LBUTTONUP: self._on_up,
            k.WM_RBUTTONUP: lambda _h, _w: self._answered("right"),
            k.WM_MOUSEACTIVATE: lambda _h, _w: k.MA_NOACTIVATE,
            k.WM_DISPLAYCHANGE: self._on_display,
            k.WM_DPICHANGED: self._on_display,
            k.WM_SETTINGCHANGE: self._on_setting,
            k.WM_POWERBROADCAST: self._on_power,
            k.WM_CLOSE: self._on_close,
            k.WM_DESTROY: self._on_destroy,
        }

    def _answered(self, kind: str) -> int:
        self._event(kind)
        return 0

    def _on_queue(self, _hwnd: Any, _wparam: int) -> int:
        while True:
            try:
                command = self._queue.get_nowait()
            except queue.Empty:
                return 0
            try:
                self._apply(command)
            except Exception:  # noqa: BLE001 - one bad command leaves the rest
                logger.warning("overlay: command %s failed", command[0], exc_info=True)

    def _on_timer(self, hwnd: Any, _wparam: int) -> int:
        self.w.user32.KillTimer(hwnd, TIMER_ID)
        return self._answered("tick")

    def _on_down(self, hwnd: Any, _wparam: int) -> int:
        self.w.user32.SetCapture(hwnd)
        return self._answered("down")

    def _on_up(self, _hwnd: Any, _wparam: int) -> int:
        self.w.user32.ReleaseCapture()
        return self._answered("up")

    def _on_display(self, _hwnd: Any, _wparam: int) -> int:
        self._event("display")
        self.reassert_now()
        return 0

    def _on_setting(self, hwnd: Any, wparam: int) -> int | None:
        if wparam == k.SPI_SETWORKAREA:
            return self._on_display(hwnd, wparam)
        return None

    def _on_power(self, _hwnd: Any, wparam: int) -> int:
        if wparam == k.PBT_APMSUSPEND:
            self._event("suspend")
        elif wparam == k.PBT_APMRESUMEAUTOMATIC:
            self.reassert_now()
            self._event("resume")
        return 1

    def _on_close(self, hwnd: Any, _wparam: int) -> int:
        self.w.user32.DestroyWindow(hwnd)
        self.hwnd = None
        return 0

    def _on_destroy(self, hwnd: Any, _wparam: int) -> int:
        self.w.user32.KillTimer(hwnd, TIMER_ID)
        self.w.user32.PostQuitMessage(0)
        return 0

    def _event(self, kind: str) -> None:
        if self.on_event is None:
            return
        x, y = k.cursor_pos(self.w)
        try:
            wake = self.on_event(kind, x, y)
        except Exception:  # noqa: BLE001 - a behaviour bug never reaches Windows
            logger.warning("overlay: handler failed on %s", kind, exc_info=True)
            return
        if wake is not None:
            self._set_timer(wake)

    def _set_timer(self, ms: int) -> None:
        self.w.user32.SetTimer(self.hwnd, TIMER_ID, max(MIN_WAKE_MS, int(ms)), None)

    # --- commands, on the window's thread -------------------------------------------------

    def _apply(self, command: tuple[Any, ...]) -> None:
        if not self.hwnd:
            return
        name = command[0]
        if name == "present":
            self._draw(*command[1:])
        elif name == "move":
            self._move(command[1], command[2])
        elif name == "show":
            self.w.user32.ShowWindow(self.hwnd, k.SW_SHOWNOACTIVATE)
            self.visible = True
            self.reassert_now()
            self._log_ok()
        elif name == "hide":
            self.w.user32.KillTimer(self.hwnd, TIMER_ID)
            self.w.user32.ShowWindow(self.hwnd, k.SW_HIDE)
            self.visible = False
        elif name == "wake":
            self._set_timer(command[1])
        elif name == "topmost":
            self.reassert_now()

    def reassert_now(self) -> None:
        if self.hwnd and self.visible:
            self.w.user32.SetWindowPos(self.hwnd, k.HWND_TOPMOST, 0, 0, 0, 0, k.SWP_TOPMOST)

    def _move(self, x: int, y: int) -> None:
        if (x, y) == self.pos:
            return
        self.pos = (x, y)
        self.w.user32.SetWindowPos(self.hwnd, None, x, y, 0, 0, k.SWP_MOVE)

    def _ensure_bitmap(self, width: int, height: int) -> None:
        if (width, height) == self._size and self._bitmap:
            return
        g = self.w.gdi32
        info = k.BITMAPINFO()
        header = info.bmiHeader
        header.biSize = ctypes.sizeof(k.BITMAPINFOHEADER)
        header.biWidth, header.biHeight = width, -height  # negative: top-down rows
        header.biPlanes, header.biBitCount, header.biCompression = 1, 32, k.BI_RGB
        bits = ctypes.c_void_p()
        bitmap = g.CreateDIBSection(self._screen_dc, ctypes.byref(info), k.DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not bitmap or not bits.value:
            raise OSError(f"CreateDIBSection failed (error {k.last_error()})")
        old = g.SelectObject(self._mem_dc, bitmap)
        if self._bitmap:
            g.DeleteObject(self._bitmap)
        else:
            self._old_bitmap = old
        self._bitmap, self._bits, self._size = bitmap, bits, (width, height)

    def _draw(self, bgra: bytes, width: int, height: int, x: int, y: int) -> None:
        if len(bgra) != premultiplied_dib_bytes(width, height):
            raise ValueError(f"frame is {len(bgra)} bytes, a {width}x{height} bitmap needs {premultiplied_dib_bytes(width, height)}")
        self._ensure_bitmap(width, height)
        ctypes.memmove(self._bits.value, bgra, len(bgra))
        blend = k.BLENDFUNCTION(k.AC_SRC_OVER, 0, 255, k.AC_SRC_ALPHA)
        at, size, origin = k.POINT(x, y), k.SIZE(width, height), k.POINT(0, 0)
        ok = self.w.user32.UpdateLayeredWindow(
            self.hwnd, self._screen_dc, ctypes.byref(at), ctypes.byref(size), self._mem_dc,
            ctypes.byref(origin), 0, ctypes.byref(blend), k.ULW_ALPHA,
        )
        if not ok:
            raise OSError(f"UpdateLayeredWindow failed (error {k.last_error()})")
        self.pos = (x, y)
        self._drawn = True

    def rect(self) -> tuple[int, int, int, int] | None:
        """The window's rectangle as Windows has it."""
        if not self.hwnd:
            return None
        r = k.wintypes.RECT()
        if not self.w.user32.GetWindowRect(self.hwnd, ctypes.byref(r)):
            return None
        return r.left, r.top, r.right, r.bottom

    def _log_ok(self) -> None:
        if self._logged_ok:
            return
        self._logged_ok = True
        logger.info(
            "overlay: layered window ok, rect=%s, exstyle=%#x (requested), drawn=%s",
            self.rect(), k.EX_STYLE, self._drawn,
        )
