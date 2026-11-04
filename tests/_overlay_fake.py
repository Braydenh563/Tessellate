"""A fake `win32` for the overlay's tests: records every call and runs a real
message queue, so `OverlayHost` runs its loop on a thread exactly as it would
on Windows (the module imports and runs on any platform)."""

from __future__ import annotations

import ctypes
import queue
import threading
from typing import Any

from tessellate.core.overlay import win32 as k


class FakeDll:
    def __init__(self, owner: "FakeWin32", name: str) -> None:
        self._owner = owner
        self._name = name

    def __getattr__(self, fn: str) -> Any:
        if fn.startswith("_"):
            raise AttributeError(fn)

        def call(*args: Any) -> Any:
            return self._owner.call(self._name, fn, args)

        return call


class FakeWin32:
    def __init__(self, cursor: tuple[int, int] = (500, 400)) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self.threads: dict[str, set[int]] = {}
        self.messages: "queue.Queue[tuple[int, int, int, int]]" = queue.Queue()
        self.wndproc: Any = None
        self.cursor = cursor
        self.buffers: list[Any] = []
        self.layered: list[dict[str, Any]] = []
        self.dib_bits: Any = None
        self.timers: dict[int, int] = {}
        #: (work area, dpi) of each monitor, and the answers the shell gives.
        self.monitor_list: list[tuple[tuple[int, int, int, int], int]] = [((0, 0, 1920, 1040), 96)]
        self.notification = 5  # QUNS_ACCEPTS_NOTIFICATIONS
        self.animations = 1
        #: (GetTickCount, last input tick); None answers "unknown" like a failed call.
        self.last_input: tuple[int, int] | None = None
        #: Visible windows, topmost first, as the shell reports them:
        #: {hwnd: {"rect", "title", "pid", "ex", "iconic", "zoomed", "cloaked", "visible"}}.
        self.window_list: dict[int, dict[str, Any]] = {}
        #: The foreground window's text caret: (client rect, the client area's screen origin), or None for none.
        self.caret: tuple[tuple[int, int, int, int], tuple[int, int]] | None = None
        for name in ("user32", "gdi32", "kernel32", "shcore", "shell32", "dwmapi"):
            setattr(self, name, FakeDll(self, name))

    def names(self, dll: str | None = None) -> list[str]:
        return [fn for d, fn, _ in self.calls if dll is None or d == dll]

    def post(self, msg: int, wparam: int = 0, lparam: int = 0) -> None:
        self.messages.put((1234, msg, wparam, lparam))

    def call(self, dll: str, fn: str, args: tuple[Any, ...]) -> Any:
        self.calls.append((dll, fn, args))
        self.threads.setdefault(fn, set()).add(threading.get_ident())
        handler = getattr(self, f"_{fn}", None)
        return handler(*args) if handler else 1

    # --- the few calls with behaviour -------------------------------------------------
    def _RegisterClassExW(self, ref: Any) -> int:
        self.wndproc = ref._obj.lpfnWndProc
        return 1

    def _CreateWindowExW(self, *args: Any) -> int:
        return 1234

    def _GetModuleHandleW(self, _name: Any) -> int:
        return 77

    def _GetMessageW(self, ref: Any, *_rest: Any) -> int:
        hwnd, msg, wparam, lparam = self.messages.get()
        m = ref._obj
        m.hwnd, m.message, m.wParam, m.lParam = hwnd, msg, wparam, lparam
        return 0 if msg == k.WM_QUIT else 1

    def _DispatchMessageW(self, ref: Any) -> int:
        m = ref._obj
        return self.wndproc(m.hwnd, m.message, m.wParam, m.lParam)

    def _PostMessageW(self, hwnd: Any, msg: int, wparam: int, lparam: int) -> int:
        self.messages.put((hwnd, msg, wparam, lparam))
        return 1

    def _PostQuitMessage(self, _code: int) -> None:
        self.messages.put((0, k.WM_QUIT, 0, 0))

    def _DestroyWindow(self, hwnd: Any) -> int:
        # Windows sends WM_DESTROY synchronously from DestroyWindow.
        if self.wndproc is not None:
            self.wndproc(hwnd, k.WM_DESTROY, 0, 0)
        return 1

    def _DefWindowProcW(self, *_args: Any) -> int:
        return 0

    def _SetTimer(self, _hwnd: Any, ident: int, ms: int, _cb: Any) -> int:
        self.timers[ident] = ms
        return ident

    def _GetCursorPos(self, ref: Any) -> int:
        ref._obj.x, ref._obj.y = self.cursor
        return 1

    def _GetWindowRect(self, _hwnd: Any, ref: Any) -> int:
        ref._obj.left, ref._obj.top, ref._obj.right, ref._obj.bottom = 10, 20, 110, 170
        return 1

    def _CreateDIBSection(self, _dc: Any, info_ref: Any, _usage: int, bits_ref: Any, _sec: Any, _off: int) -> int:
        header = info_ref._obj.bmiHeader
        size = header.biWidth * abs(header.biHeight) * 4
        self.dib_bits = ctypes.create_string_buffer(size)
        self.buffers.append(self.dib_bits)
        bits_ref._obj.value = ctypes.addressof(self.dib_bits)
        return 555

    def _UpdateLayeredWindow(self, hwnd: Any, _dst: Any, at: Any, size: Any, _src: Any, origin: Any, key: int, blend: Any, flags: int) -> int:
        self.layered.append(
            {
                "at": (at._obj.x, at._obj.y), "size": (size._obj.cx, size._obj.cy), "flags": flags,
                "alpha_format": blend._obj.AlphaFormat, "const_alpha": blend._obj.SourceConstantAlpha,
                "pixels": bytes(self.dib_bits.raw),
            }
        )
        return 1

    def _EnumDisplayMonitors(self, _dc: Any, _rect: Any, callback: Any, _data: Any) -> int:
        for index in range(len(self.monitor_list)):
            callback(index + 100, None, None, 0)
        return 1

    def _GetMonitorInfoW(self, hmon: Any, ref: Any) -> int:
        left, top, right, bottom = self.monitor_list[int(hmon) - 100][0]
        work = ref._obj.rcWork
        work.left, work.top, work.right, work.bottom = left, top, right, bottom
        return 1

    def _GetDpiForMonitor(self, hmon: Any, _kind: int, x_ref: Any, y_ref: Any) -> int:
        x_ref._obj.value = y_ref._obj.value = self.monitor_list[int(hmon) - 100][1]
        return 0

    # --- windows and monitors under a point ---------------------------------------------------
    def _EnumWindows(self, callback: Any, _data: Any) -> int:
        for hwnd in list(self.window_list):
            callback(hwnd, 0)
        return 1

    def _win(self, hwnd: Any) -> dict[str, Any]:
        return self.window_list[int(hwnd)]

    def _IsWindowVisible(self, hwnd: Any) -> int:
        return int(self._win(hwnd).get("visible", True))

    def _IsIconic(self, hwnd: Any) -> int:
        return int(self._win(hwnd).get("iconic", False))

    def _IsZoomed(self, hwnd: Any) -> int:
        return int(self._win(hwnd).get("zoomed", False))

    def _GetWindowLongW(self, hwnd: Any, _index: int) -> int:
        return int(self._win(hwnd).get("ex", 0))

    def _GetWindowTextLengthW(self, hwnd: Any) -> int:
        return len(self._win(hwnd).get("title", "x"))

    def _GetForegroundWindow(self) -> int:
        return 900

    def _GetGUIThreadInfo(self, _thread: int, ref: Any) -> int:
        info = ref._obj
        if self.caret is None:
            info.hwndCaret = None
            return 1
        (left, top, right, bottom), _origin = self.caret
        info.hwndCaret = 901
        info.rcCaret.left, info.rcCaret.top, info.rcCaret.right, info.rcCaret.bottom = left, top, right, bottom
        return 1

    def _ClientToScreen(self, _hwnd: Any, ref: Any) -> int:
        ox, oy = self.caret[1] if self.caret else (0, 0)
        ref._obj.x += ox
        ref._obj.y += oy
        return 1

    def _GetWindowThreadProcessId(self, hwnd: Any, pid_ref: Any) -> int:
        if pid_ref is None:
            return 77
        pid_ref._obj.value = self._win(hwnd).get("pid", 4242)
        return 1

    def _DwmGetWindowAttribute(self, hwnd: Any, attr: int, ref: Any, _size: int) -> int:
        win = self._win(hwnd)
        if attr == k.DWMWA_CLOAKED:
            ref._obj.value = int(win.get("cloaked", False))
        else:
            r = ref._obj
            r.left, r.top, r.right, r.bottom = win["rect"]
        return 0

    def _MonitorFromPoint(self, pt: Any, _flags: int) -> int:
        best, best_d = 100, None
        for index, (area, _dpi) in enumerate(self.monitor_list):
            dx = max(area[0] - pt.x, 0, pt.x - area[2] + 1)
            dy = max(area[1] - pt.y, 0, pt.y - area[3] + 1)
            d = dx * dx + dy * dy
            if best_d is None or d < best_d:
                best, best_d = 100 + index, d
        return best

    def _GetLastInputInfo(self, ref: Any) -> int:
        if self.last_input is None:
            return 0
        ref._obj.dwTime = self.last_input[1]
        return 1

    def _GetTickCount(self) -> int:
        return self.last_input[0] if self.last_input else 0

    def _SHQueryUserNotificationState(self, ref: Any) -> int:
        ref._obj.value = self.notification
        return 0

    def _SystemParametersInfoW(self, _action: int, _param: int, ref: Any, _flags: int) -> int:
        ref._obj.value = self.animations
        return 1
