"""Win32 declarations for the overlay: the only file here with ctypes.

**Private DLL instances, never the shared `ctypes.windll.user32`.** pywebview
calls `SetWindowPos(hwnd, None, x, y, None, None, flags)` through the shared
object; typing its functions with `c_int` arguments would make that raise
`ArgumentError`. `ctypes.WinDLL("user32", use_last_error=True)` is a separate
object, so the types set here touch nobody else's calls.

Every function the overlay uses has its `restype` and `argtypes` in
`signatures()`; `load()` applies them all, and a test checks that each
DLL call in this package is a row there. Written against
Microsoft's documentation; not run on Windows (the sandbox has none).
"""

from __future__ import annotations

import ctypes
import logging
import sys
import ctypes.wintypes
from collections import Counter
from typing import Any, NamedTuple

wintypes = ctypes.wintypes

logger = logging.getLogger(__name__)

# --- constants ---------------------------------------------------------------
WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_APPWINDOW = 0x00040000
GA_ROOTOWNER = 3
WS_EX_NOACTIVATE = 0x08000000
EX_STYLE = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOREDRAW = 0x0008
SWP_NOACTIVATE = 0x0010
#: A move: position only, never size, stacking order or focus.
SWP_MOVE = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
#: Re-assert topmost: nothing moves, nothing redraws.
SWP_TOPMOST = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOREDRAW
HWND_TOPMOST = -1

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
BI_RGB = 0
DIB_RGB_COLORS = 0

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_SETTINGCHANGE = 0x001A
WM_MOUSEACTIVATE = 0x0021
WM_SETCURSOR = 0x0020
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_TIMER = 0x0113
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_POWERBROADCAST = 0x0218
WM_APP = 0x8000
#: A high-resolution waitable timer (Windows 10 1803 and later) and what waiting on it answers.
CREATE_WAITABLE_TIMER_HIGH_RESOLUTION = 0x00000002
TIMER_ALL_ACCESS = 0x1F0003
WAIT_OBJECT_0 = 0
MA_NOACTIVATE = 3
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMEAUTOMATIC = 0x0012
SPI_SETWORKAREA = 0x002F
SPI_GETCLIENTAREAANIMATION = 0x1042
MDT_EFFECTIVE_DPI = 0
IDC_ARROW = 32512
#: The diagonal resize cursors: top left to bottom right, and bottom left to top right.
IDC_SIZENWSE, IDC_SIZENESW = 32642, 32643
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
#: MonitorFromPoint: the nearest monitor when the point is on none.
MONITOR_DEFAULTTONEAREST = 2
#: DwmGetWindowAttribute: the visible frame (no invisible resize border) and cloaking
#: (a window on another virtual desktop, or a suspended app, is "visible" but not drawn).
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
#: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
DPI_PER_MONITOR_V2 = -4
#: SHQueryUserNotificationState: busy, a fullscreen Direct3D game, a presentation.
QUNS_BUSY, QUNS_D3D_FULL_SCREEN, QUNS_PRESENTATION = 2, 3, 4
#: Not QUNS_BUSY: Windows reports it for an ordinary maximised window too, and the figure
#: blinked out for two seconds every half minute (INBOX 1670, owner's log 12:17Z).
QUNS_HIDE = frozenset({QUNS_D3D_FULL_SCREEN, QUNS_PRESENTATION})

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

if sys.platform == "win32":
    _FUNC = ctypes.WINFUNCTYPE  # type: ignore[attr-defined]
else:  # the module imports everywhere so the tests run on any platform
    _FUNC = ctypes.CFUNCTYPE
WNDPROC = _FUNC(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
WNDENUMPROC = _FUNC(wintypes.BOOL, wintypes.HWND, LPARAM)
MONITORENUMPROC = _FUNC(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), LPARAM)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", WPARAM), ("lParam", LPARAM),
        ("time", wintypes.DWORD), ("pt", POINT),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HANDLE),
        ("hIcon", wintypes.HANDLE), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HANDLE),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]


ABM_GETSTATE = 4
ABM_GETTASKBARPOS = 5
ABS_AUTOHIDE = 1


class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
        ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
    ]


def signatures() -> dict[str, dict[str, tuple[Any, list[Any]]]]:
    """DLL name -> function name -> (restype, argtypes). The one list every
    call in this package must come from."""
    H, U, INT, B = wintypes.HANDLE, wintypes.UINT, ctypes.c_int, wintypes.BOOL
    P = ctypes.POINTER
    UINT_PTR = ctypes.c_size_t
    return {
        "user32": {
            "RegisterClassExW": (wintypes.ATOM, [P(WNDCLASSEXW)]),
            "UnregisterClassW": (B, [wintypes.LPCWSTR, H]),
            "CreateWindowExW": (H, [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, INT, INT, INT, INT, H, H, H, ctypes.c_void_p]),
            "DestroyWindow": (B, [H]),
            "DefWindowProcW": (LRESULT, [H, U, WPARAM, LPARAM]),
            "GetMessageW": (INT, [P(MSG), H, U, U]),
            "TranslateMessage": (B, [P(MSG)]),
            "DispatchMessageW": (LRESULT, [P(MSG)]),
            "PostMessageW": (B, [H, U, WPARAM, LPARAM]),
            "PostQuitMessage": (None, [INT]),
            "SetTimer": (UINT_PTR, [H, UINT_PTR, U, ctypes.c_void_p]),
            "KillTimer": (B, [H, UINT_PTR]),
            "ShowWindow": (B, [H, INT]),
            "SetWindowPos": (B, [H, H, INT, INT, INT, INT, U]),
            "GetWindowRect": (B, [H, P(wintypes.RECT)]),
            "UpdateLayeredWindow": (B, [H, H, P(POINT), P(SIZE), H, P(POINT), wintypes.DWORD, P(BLENDFUNCTION), wintypes.DWORD]),
            "GetDC": (H, [H]),
            "ReleaseDC": (INT, [H, H]),
            "GetCursorPos": (B, [P(POINT)]),
            "GetLastInputInfo": (B, [P(LASTINPUTINFO)]),
            "GetForegroundWindow": (H, []),
            "GetGUIThreadInfo": (B, [wintypes.DWORD, P(GUITHREADINFO)]),
            "ClientToScreen": (B, [H, P(POINT)]),
            "SetCapture": (H, [H]),
            "ReleaseCapture": (B, []),
            "LoadCursorW": (H, [H, ctypes.c_void_p]),
            "SetCursor": (H, [H]),
            "RegisterWindowMessageW": (U, [wintypes.LPCWSTR]),
            "EnumDisplayMonitors": (B, [H, P(wintypes.RECT), MONITORENUMPROC, LPARAM]),
            "GetMonitorInfoW": (B, [H, P(MONITORINFO)]),
            "SetThreadDpiAwarenessContext": (ctypes.c_void_p, [ctypes.c_void_p]),
            "SystemParametersInfoW": (B, [U, U, ctypes.c_void_p, U]),
            "EnumWindows": (B, [WNDENUMPROC, LPARAM]),
            "IsWindowVisible": (B, [H]),
            "GetAncestor": (H, [H, U]),
            "FindWindowW": (H, [wintypes.LPCWSTR, wintypes.LPCWSTR]),
            "FindWindowExW": (H, [H, H, wintypes.LPCWSTR, wintypes.LPCWSTR]),
            "GetClassNameW": (INT, [H, wintypes.LPWSTR, INT]),
            "GetLastActivePopup": (H, [H]),
            "IsIconic": (B, [H]),
            "IsZoomed": (B, [H]),
            "GetWindowLongW": (ctypes.c_long, [H, INT]),
            "GetWindowTextLengthW": (INT, [H]),
            "GetWindowThreadProcessId": (wintypes.DWORD, [H, P(wintypes.DWORD)]),
            "MonitorFromPoint": (H, [POINT, wintypes.DWORD]),
        },
        "dwmapi": {
            "DwmGetWindowAttribute": (ctypes.c_long, [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]),
        },
        "gdi32": {
            "CreateCompatibleDC": (H, [H]),
            "DeleteDC": (B, [H]),
            "CreateDIBSection": (H, [H, P(BITMAPINFO), U, P(ctypes.c_void_p), H, wintypes.DWORD]),
            "SelectObject": (H, [H, H]),
            "DeleteObject": (B, [H]),
        },
        "kernel32": {
            "GetModuleHandleW": (H, [wintypes.LPCWSTR]),
            "GetTickCount": (wintypes.DWORD, []),
            "CreateWaitableTimerExW": (ctypes.c_void_p, [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]),
            "SetWaitableTimer": (B, [ctypes.c_void_p, P(ctypes.c_longlong), ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, B]),
            "CancelWaitableTimer": (B, [ctypes.c_void_p]),
            "WaitForSingleObject": (wintypes.DWORD, [ctypes.c_void_p, wintypes.DWORD]),
            "CloseHandle": (B, [ctypes.c_void_p]),
            "GetSystemPowerStatus": (B, [P(_PowerStatus)]),
        },
        "shcore": {
            "GetDpiForMonitor": (ctypes.c_long, [H, INT, P(U), P(U)]),
        },
        "shell32": {
            "SHQueryUserNotificationState": (ctypes.c_long, [P(INT)]),
            "SHAppBarMessage": (ctypes.c_size_t, [wintypes.DWORD, P(APPBARDATA)]),
        },
    }


#: Functions an older Windows may lack: left unset (the caller checks `hasattr`).
OPTIONAL = frozenset({"SetThreadDpiAwarenessContext", "GetDpiForMonitor", "SHQueryUserNotificationState", "DwmGetWindowAttribute", "SHAppBarMessage"})


class Win32:
    """The typed private DLLs: `.user32`, `.gdi32`, `.kernel32`, `.shcore`, `.shell32`, `.dwmapi`."""

    def __init__(self, dlls: dict[str, Any]) -> None:
        for name, dll in dlls.items():
            setattr(self, name, dll)


def apply_signatures(dlls: dict[str, Any]) -> list[str]:
    """Set `restype` and `argtypes` on every function in `signatures()`;
    returns the names that are missing from a DLL (only OPTIONAL ones may be)."""
    missing: list[str] = []
    for dll_name, table in signatures().items():
        dll = dlls.get(dll_name)
        if dll is None:
            missing.extend(f"{dll_name}.{fn}" for fn in table)
            continue
        for fn, (restype, argtypes) in table.items():
            try:
                func = getattr(dll, fn)
            except AttributeError:
                if fn not in OPTIONAL:
                    raise
                missing.append(f"{dll_name}.{fn}")
                continue
            func.restype = restype
            func.argtypes = argtypes
    return missing


def load() -> Win32:
    """Private, typed DLL instances. Windows only (raises OSError elsewhere)."""
    if sys.platform != "win32":
        raise OSError("the overlay needs Windows")
    dlls: dict[str, Any] = {}
    for name in ("user32", "gdi32", "kernel32", "shcore", "shell32", "dwmapi"):
        try:
            dlls[name] = ctypes.WinDLL(name, use_last_error=True)  # type: ignore[attr-defined]
        except OSError:
            if name not in ("shcore", "shell32", "dwmapi"):
                raise
            logger.info("overlay: %s is not available; its calls are skipped", name)
    missing = apply_signatures(dlls)
    if missing:
        logger.info("overlay: not on this Windows: %s", ", ".join(missing))
    return Win32(dlls)


# --- small helpers over the typed calls (shared by host and the coordinator) ----

Rect = tuple[int, int, int, int]
#: ABE_LEFT to ABE_BOTTOM, the order Windows numbers a taskbar's edge in.
EDGES = ("left", "top", "right", "bottom")
#: Windows that cover a monitor without being a program in front of it (the desktop, the taskbar itself).
SHELL_CLASSES = frozenset({"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"})


class BarInfo(NamedTuple):
    """One strip along a monitor's edge: a taskbar window (`taskbar`) or the strip a docked appbar or sidebar
    reserves (its inset between the monitor and its work area). `rect` is in screen pixels; `shown` is whether it
    is there to be tucked behind: visible, not set to auto-hide and not under a full-screen window."""

    edge: str
    rect: Rect
    visible: bool = True
    autohide: bool = False
    taskbar: bool = True
    covered: bool = False

    @property
    def shown(self) -> bool:
        return self.visible and not self.autohide and not self.covered


class MonitorInfo(NamedTuple):
    """A monitor as the engine plays on it: `area` is the floor, ceiling and sides (the work area with the strip of
    every bar that is not shown given back), `screen` the whole monitor (rcMonitor), `bars` what is along its edges."""

    area: Rect
    dpi: int
    screen: Rect
    bars: tuple[BarInfo, ...] = ()


def _class_name(w: Any, hwnd: Any) -> str:
    buf = ctypes.create_unicode_buffer(64)
    return buf.value if w.user32.GetClassNameW(hwnd, buf, 64) else ""


def _edge_of(rect: Rect, screen: Rect) -> str:
    """The side of `screen` a strip lies along, by its shape and where it sits (when the shell does not say)."""
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    if rect[2] - rect[0] >= rect[3] - rect[1]:
        return "top" if cy < (screen[1] + screen[3]) / 2 else "bottom"
    return "left" if cx < (screen[0] + screen[2]) / 2 else "right"


def _nearest(screens: list[tuple[Rect, Rect, int]], rect: Rect) -> int | None:
    """Index of the monitor a rectangle belongs to: the one whose whole rectangle its centre is nearest (an
    auto-hidden taskbar rests half outside the screen)."""
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    best: tuple[float, int] | None = None
    for i, (_work, full, _dpi) in enumerate(screens):
        if full[2] <= full[0] or full[3] <= full[1]:
            continue
        dx, dy = max(full[0] - cx, 0, cx - full[2]), max(full[1] - cy, 0, cy - full[3])
        if best is None or dx * dx + dy * dy < best[0]:
            best = (dx * dx + dy * dy, i)
    return None if best is None else best[1]


def _tray_windows(w: Any) -> list[Any]:
    """The primary taskbar (Shell_TrayWnd) and one Shell_SecondaryTrayWnd per other monitor."""
    found: list[Any] = []
    try:
        primary = w.user32.FindWindowW("Shell_TrayWnd", None)
        if primary:
            found.append(primary)

        after = None
        for _ in range(16):  # one per monitor; the bound is a guard against a loop
            after = w.user32.FindWindowExW(None, after, "Shell_SecondaryTrayWnd", None)
            if not after:
                break
            if after not in found:
                found.append(after)
    except Exception:  # noqa: BLE001 - an unreadable shell leaves the work area as it reports it
        logger.debug("overlay: the taskbars could not be listed", exc_info=True)
    return found


def _read_tray(w: Any, hwnd: Any) -> tuple[Rect | None, bool, bool, int | None]:
    """(rectangle, visible, auto-hide, uEdge or None) of one taskbar window (research T1; INBOX 1683 y)."""
    rect: Rect | None = None
    r = wintypes.RECT()
    if w.user32.GetWindowRect(hwnd, ctypes.byref(r)):
        rect = (r.left, r.top, r.right, r.bottom)
    visible = bool(w.user32.IsWindowVisible(hwnd))
    autohide, uedge = False, None
    ask = getattr(getattr(w, "shell32", None), "SHAppBarMessage", None)
    if ask is not None:
        data = APPBARDATA()
        data.cbSize, data.hWnd = ctypes.sizeof(APPBARDATA), hwnd
        autohide = bool(int(ask(ABM_GETSTATE, ctypes.byref(data))) & ABS_AUTOHIDE)
        pos = APPBARDATA()
        pos.cbSize, pos.hWnd = ctypes.sizeof(APPBARDATA), hwnd
        if int(ask(ABM_GETTASKBARPOS, ctypes.byref(pos))):
            uedge = int(pos.uEdge)
            if rect is None:
                rect = (pos.rc.left, pos.rc.top, pos.rc.right, pos.rc.bottom)
    return rect, visible, autohide, uedge


def _covering(w: Any, screens: list[tuple[Rect, Rect, int]]) -> set[int]:
    """The monitors a full-screen program in front covers: the taskbar is under it there, whatever it is set to.
    The rectangle is tested first (one call) so that a window that covers nothing costs no more."""
    try:
        front = w.user32.GetForegroundWindow()
        r = wintypes.RECT()
        if not front or not w.user32.GetWindowRect(front, ctypes.byref(r)):
            return set()
        rect = (r.left, r.top, r.right, r.bottom)  # the outer rectangle: one cheap call, and a full-screen window has no border to trim
        hit = {
            i for i, (_work, full, _dpi) in enumerate(screens)
            if full[2] > full[0] and rect[0] <= full[0] and rect[1] <= full[1] and rect[2] >= full[2] and rect[3] >= full[3]
        }
        if hit and (_unlisted(w, front, None) is not None or _class_name(w, front) in SHELL_CLASSES):
            return set()
        return hit
    except Exception:  # noqa: BLE001 - an unreadable foreground window covers nothing
        return set()


def _screens(w: Any) -> list[tuple[Rect, Rect, int]]:
    """(work area, whole monitor, dpi) of every monitor, in the calling thread's awareness. The whole monitor is
    (0, 0, 0, 0) when the shell does not give it."""
    found: list[tuple[Rect, Rect, int]] = []

    def each(hmon: Any, _hdc: Any, _rect: Any, _data: Any) -> int:
        try:
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if w.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                work = (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
                full = (info.rcMonitor.left, info.rcMonitor.top, info.rcMonitor.right, info.rcMonitor.bottom)
                found.append((work, full, _monitor_dpi(w, hmon)))
        except Exception:  # noqa: BLE001 - one bad monitor never ends the walk
            logger.debug("overlay: a monitor could not be read", exc_info=True)
        return 1

    callback = MONITORENUMPROC(each)
    w.user32.EnumDisplayMonitors(None, None, callback, 0)
    return found


def _bars_by_monitor(w: Any, screens: list[tuple[Rect, Rect, int]], cover: set[int]) -> list[list[BarInfo]]:
    """The bars along each monitor's edges: every taskbar window, then any edge whose work area is inset from the
    monitor by something that is not a taskbar (a docked appbar or sidebar). With no taskbar window at all (a tool
    removed it) the bottom inset is the missing taskbar's: not shown, so the strip goes back to the floor."""
    out: list[list[BarInfo]] = [[] for _ in screens]
    trays = _tray_windows(w)
    for hwnd in trays:
        bar = _read_bar(w, hwnd, screens, cover)
        if bar is not None:
            out[bar[0]].append(bar[1])
    for i, (work, full, _dpi) in enumerate(screens):
        out[i].extend(_inset_bars(work, full, {b.edge for b in out[i]}, not trays, i in cover))
    return out


def _read_bar(w: Any, hwnd: int, screens: list[tuple[Rect, Rect, int]], cover: set[int]) -> tuple[int, BarInfo] | None:
    """One taskbar window as its monitor's index and bar, or None when it cannot be read or sits on no monitor."""
    try:
        rect, visible, autohide, uedge = _read_tray(w, hwnd)
    except Exception:  # noqa: BLE001
        logger.debug("overlay: a taskbar could not be read", exc_info=True)
        return None
    i = _nearest(screens, rect) if rect is not None else None
    if rect is None or i is None:
        return None
    edge = EDGES[uedge] if uedge is not None and 0 <= uedge < 4 else _edge_of(rect, screens[i][1])
    return i, BarInfo(edge, rect, visible, autohide, True, i in cover)


def _inset_bars(work: Rect, full: Rect, have: set[str], no_taskbar: bool, covered: bool) -> list[BarInfo]:
    """The edges of one monitor whose work area is inset by something other than a taskbar window."""
    if full[2] <= full[0] or full[3] <= full[1]:
        return []
    insets = {
        "left": (full[0], full[1], work[0], full[3]), "top": (full[0], full[1], full[2], work[1]),
        "right": (work[2], full[1], full[2], full[3]), "bottom": (full[0], work[3], full[2], full[3]),
    }
    out = []
    for edge, strip in insets.items():
        if strip[2] - strip[0] <= 0 or strip[3] - strip[1] <= 0 or edge in have:
            continue
        gone_tray = edge == "bottom" and no_taskbar
        out.append(BarInfo(edge, strip, not gone_tray, False, gone_tray, covered))
    return out


def _play_area(work: Rect, full: Rect, bars_: list[BarInfo], covered: bool) -> Rect:
    """The work area with the strip of every bar that is not shown given back (and all of the monitor under a
    full-screen window). The inset on a taskbar's edge is taken to be the taskbar's: a sidebar docked on the same
    edge is not told apart from it."""
    if full[2] <= full[0] or full[3] <= full[1]:
        return work
    if covered:
        return full
    left, top, right, bottom = work
    for bar in bars_:
        if bar.shown:
            continue
        if bar.edge == "left":
            left = full[0]
        elif bar.edge == "top":
            top = full[1]
        elif bar.edge == "right":
            right = full[2]
        else:
            bottom = full[3]
    return left, top, right, bottom


def monitors_full(w: Any) -> list[MonitorInfo]:
    """Every monitor with its play area, whole rectangle and bars (INBOX 1683 y, 1692 a). A shown bar on the
    bottom edge makes the floor its top; hidden by a tool, auto-hidden or under a full-screen window, the floor is
    the bottom of the screen. The top, left and right likewise."""
    screens = _screens(w)
    try:
        cover = _covering(w, screens)
        per = _bars_by_monitor(w, screens, cover)
    except Exception:  # noqa: BLE001 - an unreadable shell leaves the work areas as the shell reports them
        logger.debug("overlay: the bars could not be read", exc_info=True)
        cover, per = set(), [[] for _ in screens]
    return [
        MonitorInfo(_play_area(work, full, per[i], i in cover), dpi, full, tuple(per[i]))
        for i, (work, full, dpi) in enumerate(screens)
    ]


def bars(w: Any) -> list[BarInfo]:
    """Every bar on every monitor (INBOX 1683 y): the taskbar windows with their rectangle, visibility,
    auto-hide state and edge (ABM_GETSTATE, ABM_GETTASKBARPOS), and each docked appbar's inset strip."""
    screens = _screens(w)
    return [bar for per in _bars_by_monitor(w, screens, _covering(w, screens)) for bar in per]


def monitors(w: Any) -> list[tuple[tuple[int, int, int, int], int]]:
    """Every monitor's play area (left, top, right, bottom) in physical pixels of the calling thread's awareness,
    with its effective dpi (`monitors_full` has the rest)."""
    return [(m.area, m.dpi) for m in monitors_full(w)]


def _monitor_dpi(w: Any, hmon: Any) -> int:
    fn = getattr(getattr(w, "shcore", None), "GetDpiForMonitor", None)
    if fn is None:
        return 96
    x, y = wintypes.UINT(96), wintypes.UINT(96)
    try:
        if fn(hmon, MDT_EFFECTIVE_DPI, ctypes.byref(x), ctypes.byref(y)) == 0:
            return int(x.value) or 96
    except Exception:  # noqa: BLE001
        logger.debug("overlay: dpi of a monitor unknown", exc_info=True)
    return 96


def dpi_at_point(w: Any, x: int, y: int) -> int | None:
    """The effective dpi of the monitor under a physical point (MonitorFromPoint,
    nearest when none holds it, then GetDpiForMonitor); None when it cannot be read."""
    fn = getattr(getattr(w, "user32", None), "MonitorFromPoint", None)
    if fn is None or getattr(getattr(w, "shcore", None), "GetDpiForMonitor", None) is None:
        return None
    try:
        hmon = fn(POINT(int(x), int(y)), MONITOR_DEFAULTTONEAREST)
        return _monitor_dpi(w, hmon) if hmon else None
    except Exception:  # noqa: BLE001
        logger.debug("overlay: dpi at a point unknown", exc_info=True)
        return None


class WinInfo(NamedTuple):
    """One visible top-level window, in z-order from the top: its frame in physical
    pixels, whether its top edge is a place to stand (`perch`), and whether it is a maximised window whose
    title bar is a place to hang from (`hang`, INBOX 1683 w)."""

    key: int
    rect: tuple[int, int, int, int]
    perch: bool
    hang: bool = False
    #: False for a layered or tool window that fills a monitor (an animated wallpaper, a screen overlay): it is
    #: drawn above the real windows but hides none of their tops (INBOX 1692 n).
    solid: bool = True


def _frame_rect(w: Any, hwnd: Any) -> tuple[int, int, int, int] | None:
    """The visible frame (DWMWA_EXTENDED_FRAME_BOUNDS), else the window rectangle. An empty frame from DWM (a window
    that draws its own, INBOX 1696 b: an Explorer window may be counted "no frame") falls back to the rectangle too."""
    r = wintypes.RECT()
    dwm = getattr(getattr(w, "dwmapi", None), "DwmGetWindowAttribute", None)
    try:
        if dwm is not None and dwm(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) == 0 and r.right > r.left and r.bottom > r.top:
            return r.left, r.top, r.right, r.bottom
        if w.user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return r.left, r.top, r.right, r.bottom
    except Exception:  # noqa: BLE001
        logger.debug("overlay: a window's frame could not be read", exc_info=True)
    return None


def _cloaked(w: Any, hwnd: Any) -> bool:
    dwm = getattr(getattr(w, "dwmapi", None), "DwmGetWindowAttribute", None)
    if dwm is None:
        return False
    flag = wintypes.DWORD(0)
    try:
        return dwm(hwnd, DWMWA_CLOAKED, ctypes.byref(flag), ctypes.sizeof(flag)) == 0 and bool(flag.value)
    except Exception:  # noqa: BLE001
        return False


def _alt_tab_listed(w: Any, hwnd: Any) -> bool:
    """Alt-Tab's rule for an owned window (Raymond Chen's): it is listed when it is the last active visible popup of
    its root owner. A dialog is, and its owner is then not. True when the shell cannot be asked."""
    try:
        walk = w.user32.GetAncestor(hwnd, GA_ROOTOWNER)
        for _ in range(16):  # an owner chain is a few deep; the bound is a guard against a cycle
            popup = w.user32.GetLastActivePopup(walk)
            if w.user32.IsWindowVisible(popup) or popup == walk:
                return bool(popup == hwnd)
            walk = popup
    except Exception:  # noqa: BLE001
        logger.debug("alt-tab rule could not be read for a window; it is treated as listed", exc_info=True)
    return True


def _unlisted(w: Any, hwnd: Any, ignore: Any) -> str | None:
    """Why a window is not listed: not visible, minimised, cloaked (another desktop, a suspended store app) or
    our own overlay; None when it is listed."""
    if hwnd == ignore:
        return "own overlay"
    if not w.user32.IsWindowVisible(hwnd):
        return "invisible"
    if w.user32.IsIconic(hwnd):
        return "minimised"
    if _cloaked(w, hwnd):
        return "cloaked"
    return None


def _framed(w: Any, hwnd: Any, ex: int) -> tuple[Any, str]:
    """The window's frame rectangle, or None and why: click-through (another overlay) or no frame."""
    if ex & WS_EX_TRANSPARENT and ex & WS_EX_LAYERED:
        return None, "click-through"
    rect = _frame_rect(w, hwnd)
    if rect is None or rect[2] <= rect[0] or rect[3] <= rect[1]:
        return None, "no frame"
    return rect, ""


def _read_window_why(w: Any, hwnd: Any, own_pid: int, ignore: Any, monitors_: list[tuple[int, int, int, int]]) -> "tuple[WinInfo | None, str, Any]":
    """One window as a WinInfo (None: not listed), the first reason it is no place to stand ("perch": it is one),
    and its frame when it was read."""
    why = _unlisted(w, hwnd, ignore)
    if why is not None:
        return None, why, None
    ex = int(w.user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    rect, why = _framed(w, hwnd, ex)
    if rect is None:
        return None, why, None
    info, why = _classify(w, hwnd, own_pid, ex, rect, monitors_)
    return info, why or "perch", rect


def _classify(w: Any, hwnd: Any, own_pid: int, ex: int, rect: Any, monitors_: list[tuple[int, int, int, int]]) -> "tuple[WinInfo, str | None]":
    """A framed window as a WinInfo, and the first reason it is no place to stand (None: it is one)."""
    pid = wintypes.DWORD(0)
    w.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    full = any(rect[0] <= a[0] and rect[2] >= a[2] and rect[1] <= a[1] and rect[3] >= a[3] for a in monitors_)
    app = bool(ex & WS_EX_APPWINDOW)  # a tool window that asks for a taskbar button is a real app window (Electron, some browsers)
    reasons = (
        ("tool window", bool(ex & WS_EX_TOOLWINDOW) and not app), ("own process", int(pid.value) == own_pid),
        ("maximised", bool(w.user32.IsZoomed(hwnd))), ("fills a monitor", full),
        ("no title", not w.user32.GetWindowTextLengthW(hwnd)),
        ("owned popup", not _alt_tab_listed(w, hwnd)),  # T7: not the window Alt-Tab lists, it still hides what is under it
    )
    why = next((name for name, hit in reasons if hit), None)
    # A maximised window is no place to stand but its title bar is a place to hang from; a tool window, the app's
    # own and one without a title are neither (INBOX 1683 w: with a maximised window up, only the taskbar was left).
    hang = reasons[2][1] and not (reasons[0][1] or reasons[1][1] or reasons[4][1])
    # A layered or tool window that fills a monitor (an animated wallpaper, a screen overlay) hides no window's top.
    solid = not (full and ex & (WS_EX_TOOLWINDOW | WS_EX_LAYERED) and not app)
    return WinInfo(int(hwnd), rect, why is None, hang, solid), why


def windows(
    w: Any, own_pid: int, ignore: int | None, monitors_: list[tuple[int, int, int, int]], tally: Counter | None = None,
    near: tuple[int, int, int] | None = None, seen: list | None = None,
) -> list[WinInfo]:
    """Visible, un-minimised, un-cloaked top-level windows, topmost first. Read only:
    nothing here moves, focuses or messages a window. `perch` is False for a tool
    window, a window with no title, this process's own windows (the app's, the
    panel), a maximised one (which is `hang`: its title bar can be held), and one that fills a monitor's work area (full screen).
    `ignore` is the overlay's own window (never in the list). `tally`, when given, is filled with the
    count of windows by outcome (the first reason each was left out), for the log. `near` (x, y, reach) with `seen`
    fills `seen` with (class, rectangle, reason) for each window, listed or not, spanning x with its top within reach
    of y: why a release over a window did or did not find its top (INBOX 1696 b; a class name, never a title)."""
    found: list[WinInfo] = []

    def each(hwnd: Any, _data: Any) -> int:
        try:
            info, why, rect = _read_window_why(w, hwnd, own_pid, ignore, monitors_)
            if tally is not None:
                tally[why] += 1
            if info is not None:
                found.append(info)
            if near is not None and seen is not None and why != "own overlay":
                _note_near(w, hwnd, rect, why, near, seen)
        except Exception:  # noqa: BLE001 - one odd window never ends the walk
            if tally is not None:
                tally["unreadable"] += 1
            logger.debug("overlay: a window could not be read", exc_info=True)
        return 1

    callback = WNDENUMPROC(each)
    w.user32.EnumWindows(callback, 0)
    return found


def _note_near(w: Any, hwnd: Any, rect: Any, why: str, near: tuple[int, int, int], seen: list) -> None:
    if rect is None:
        r = wintypes.RECT()
        if not w.user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return
        rect = (r.left, r.top, r.right, r.bottom)
    x, y, reach = near
    if rect[0] <= x < rect[2] and abs(rect[1] - y) <= reach:
        seen.append((_class_name(w, hwnd), tuple(rect), why))


def cursor_pos(w: Any) -> tuple[int, int]:
    pt = POINT()
    w.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def notification_state(w: Any) -> int | None:
    """SHQueryUserNotificationState, or None when this Windows lacks it."""
    fn = getattr(getattr(w, "shell32", None), "SHQueryUserNotificationState", None)
    if fn is None:
        return None
    state = ctypes.c_int(0)
    try:
        return int(state.value) if fn(ctypes.byref(state)) == 0 else None
    except Exception:  # noqa: BLE001
        logger.debug("overlay: notification state unknown", exc_info=True)
        return None


def last_input_age(w: Any) -> float | None:
    """Seconds since the last key or mouse input anywhere (GetLastInputInfo), or
    None when it cannot be read. Only the age is read, never what was typed."""
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    try:
        if not w.user32.GetLastInputInfo(ctypes.byref(info)) or not info.dwTime:
            return None
        now = int(w.kernel32.GetTickCount()) & 0xFFFFFFFF
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
    except Exception:  # noqa: BLE001
        logger.debug("overlay: last input unknown", exc_info=True)
        return None


def foreground(w: Any) -> int | None:
    """The foreground window's handle as a number (only that it changed is used), or None."""
    try:
        return int(w.user32.GetForegroundWindow() or 0) or None
    except Exception:  # noqa: BLE001
        logger.debug("overlay: foreground window unknown", exc_info=True)
        return None


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte), ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte), ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def battery(w: Any) -> tuple[int, bool] | None:
    """`(percent, on mains power)`, or None for a desktop with no battery (flag 128) or an unknown level (255)."""
    status = _PowerStatus()
    try:
        if not w.kernel32.GetSystemPowerStatus(ctypes.byref(status)) or status.BatteryFlag == 128 or status.BatteryLifePercent > 100:
            return None
        return int(status.BatteryLifePercent), status.ACLineStatus == 1
    except Exception:  # noqa: BLE001
        logger.debug("overlay: battery unknown", exc_info=True)
        return None


def caret_rect(w: Any) -> tuple[int, int, int, int] | None:
    """The text caret of the foreground window in screen px (left, top, right, bottom), or None when
    there is none or it cannot be read. GetGUIThreadInfo gives `rcCaret` in the caret window's client
    space, ClientToScreen maps its two corners. Only where the caret is, never what is typed."""
    try:
        hwnd = w.user32.GetForegroundWindow()
        if not hwnd:
            return None
        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not w.user32.GetGUIThreadInfo(w.user32.GetWindowThreadProcessId(hwnd, None), ctypes.byref(info)):
            return None
        if not info.hwndCaret:
            return None
        rc = info.rcCaret
        if rc.right <= rc.left and rc.bottom <= rc.top:
            return None
        a, b = POINT(rc.left, rc.top), POINT(rc.right, rc.bottom)
        if not (w.user32.ClientToScreen(info.hwndCaret, ctypes.byref(a)) and w.user32.ClientToScreen(info.hwndCaret, ctypes.byref(b))):
            return None
        return int(a.x), int(a.y), max(int(b.x), int(a.x) + 1), max(int(b.y), int(a.y) + 1)
    except Exception:  # noqa: BLE001
        logger.debug("overlay: caret unknown", exc_info=True)
        return None


#: Where a chat box sits when the app shows no system caret (Chromium, Electron, a browser canvas):
#: the bottom of the foreground window, in its middle, so the side edges stay free to step to.
TEXT_ZONE_HEIGHT = 170
TEXT_ZONE_SIDE = 0.15


def text_zone(w: Any, hwnd: int | None = None) -> tuple[int, int, int, int] | None:
    """A stand-in for the caret while the person types in an app that exposes none: the bottom band of
    the foreground window's frame (its middle 70% across), in screen px, or None when unreadable or
    too small to hold a text box. Only a rectangle, never what is typed."""
    try:
        hwnd = hwnd or w.user32.GetForegroundWindow()
        frame = _frame_rect(w, hwnd) if hwnd else None
    except Exception:  # noqa: BLE001
        logger.debug("overlay: text zone unknown", exc_info=True)
        return None
    if frame is None:
        return None
    left, top, right, bottom = frame
    width = right - left
    if width < 240 or bottom - top < 2 * TEXT_ZONE_HEIGHT:
        return None
    side = int(width * TEXT_ZONE_SIDE)
    return left + side, bottom - TEXT_ZONE_HEIGHT, right - side, bottom


def animations_enabled(w: Any) -> bool:
    """SPI_GETCLIENTAREAANIMATION: False when the person turned animations off."""
    flag = wintypes.BOOL(1)
    try:
        if w.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(flag), 0):
            return bool(flag.value)
    except Exception:  # noqa: BLE001
        logger.debug("overlay: animation setting unknown", exc_info=True)
    return True


def last_error() -> int:
    """GetLastError of the calling thread as ctypes saved it (0 off Windows)."""
    getter = getattr(ctypes, "get_last_error", None)
    return int(getter()) if getter else 0
