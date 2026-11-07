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
        },
    }


#: Functions an older Windows may lack: left unset (the caller checks `hasattr`).
OPTIONAL = frozenset({"SetThreadDpiAwarenessContext", "GetDpiForMonitor", "SHQueryUserNotificationState", "DwmGetWindowAttribute"})


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

def monitors(w: Any) -> list[tuple[tuple[int, int, int, int], int]]:
    """Every monitor's work area (left, top, right, bottom) in physical pixels
    of the calling thread's awareness, with its effective dpi."""
    found: list[tuple[tuple[int, int, int, int], int]] = []

    def each(hmon: Any, _hdc: Any, _rect: Any, _data: Any) -> int:
        try:
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if w.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                area = (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
                found.append((area, _monitor_dpi(w, hmon)))
        except Exception:  # noqa: BLE001 - one bad monitor never ends the walk
            logger.debug("overlay: a monitor could not be read", exc_info=True)
        return 1

    callback = MONITORENUMPROC(each)
    w.user32.EnumDisplayMonitors(None, None, callback, 0)
    return found


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


def _frame_rect(w: Any, hwnd: Any) -> tuple[int, int, int, int] | None:
    """The visible frame (DWMWA_EXTENDED_FRAME_BOUNDS), else the window rectangle."""
    r = wintypes.RECT()
    dwm = getattr(getattr(w, "dwmapi", None), "DwmGetWindowAttribute", None)
    try:
        if dwm is not None and dwm(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) == 0:
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


def _read_window(
    w: Any, hwnd: Any, own_pid: int, ignore: Any, monitors_: list[tuple[int, int, int, int]], tally: Counter | None = None,
) -> "WinInfo | None":
    """One window as a WinInfo, or None when it is not listed, click-through or has no frame. `tally` counts
    why each window was left out or not made a perch (counts only, never a title)."""
    def note(why: str) -> None:
        if tally is not None:
            tally[why] += 1

    why = _unlisted(w, hwnd, ignore)
    if why is not None:
        note(why)
        return None
    ex = int(w.user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    rect, why = _framed(w, hwnd, ex)
    if rect is None:
        note(why)
        return None
    pid = wintypes.DWORD(0)
    w.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    full = any(rect[0] <= a[0] and rect[2] >= a[2] and rect[1] <= a[1] and rect[3] >= a[3] for a in monitors_)
    reasons = (
        ("tool window", bool(ex & WS_EX_TOOLWINDOW)), ("own process", int(pid.value) == own_pid),
        ("maximised", bool(w.user32.IsZoomed(hwnd))), ("fills a monitor", full),
        ("no title", not w.user32.GetWindowTextLengthW(hwnd)),
    )
    why = next((name for name, hit in reasons if hit), None)
    note(why or "perch")
    # A maximised window is no place to stand but its title bar is a place to hang from; a tool window, the app's
    # own and one without a title are neither (INBOX 1683 w: with a maximised window up, only the taskbar was left).
    hang = reasons[2][1] and not (reasons[0][1] or reasons[1][1] or reasons[4][1])
    return WinInfo(int(hwnd), rect, why is None, hang)


def windows(
    w: Any, own_pid: int, ignore: int | None, monitors_: list[tuple[int, int, int, int]], tally: Counter | None = None,
) -> list[WinInfo]:
    """Visible, un-minimised, un-cloaked top-level windows, topmost first. Read only:
    nothing here moves, focuses or messages a window. `perch` is False for a tool
    window, a window with no title, this process's own windows (the app's, the
    panel), a maximised one (which is `hang`: its title bar can be held), and one that fills a monitor's work area (full screen).
    `ignore` is the overlay's own window (never in the list). `tally`, when given, is filled with the
    count of windows by outcome (the first reason each was left out), for the log."""
    found: list[WinInfo] = []

    def each(hwnd: Any, _data: Any) -> int:
        try:
            info = _read_window(w, hwnd, own_pid, ignore, monitors_, tally)
            if info is not None:
                found.append(info)
        except Exception:  # noqa: BLE001 - one odd window never ends the walk
            if tally is not None:
                tally["unreadable"] += 1
            logger.debug("overlay: a window could not be read", exc_info=True)
        return 1

    callback = WNDENUMPROC(each)
    w.user32.EnumWindows(callback, 0)
    return found


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
