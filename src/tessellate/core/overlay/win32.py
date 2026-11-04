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
from ctypes import wintypes
from typing import Any

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
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_TIMER = 0x0113
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_POWERBROADCAST = 0x0218
WM_APP = 0x8000
MA_NOACTIVATE = 3
PBT_APMSUSPEND = 0x0004
PBT_APMRESUMEAUTOMATIC = 0x0012
SPI_SETWORKAREA = 0x002F
SPI_GETCLIENTAREAANIMATION = 0x1042
MDT_EFFECTIVE_DPI = 0
IDC_ARROW = 32512
#: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
DPI_PER_MONITOR_V2 = -4
#: SHQueryUserNotificationState: busy, a fullscreen Direct3D game, a presentation.
QUNS_BUSY, QUNS_D3D_FULL_SCREEN, QUNS_PRESENTATION = 2, 3, 4
QUNS_HIDE = frozenset({QUNS_BUSY, QUNS_D3D_FULL_SCREEN, QUNS_PRESENTATION})

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t

if sys.platform == "win32":
    _FUNC = ctypes.WINFUNCTYPE  # type: ignore[attr-defined]
else:  # the module imports everywhere so the tests run on any platform
    _FUNC = ctypes.CFUNCTYPE
WNDPROC = _FUNC(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)
MONITORENUMPROC = _FUNC(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), LPARAM)


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
            "SetCapture": (H, [H]),
            "ReleaseCapture": (B, []),
            "LoadCursorW": (H, [H, ctypes.c_void_p]),
            "RegisterWindowMessageW": (U, [wintypes.LPCWSTR]),
            "EnumDisplayMonitors": (B, [H, P(wintypes.RECT), MONITORENUMPROC, LPARAM]),
            "GetMonitorInfoW": (B, [H, P(MONITORINFO)]),
            "SetThreadDpiAwarenessContext": (ctypes.c_void_p, [ctypes.c_void_p]),
            "SystemParametersInfoW": (B, [U, U, ctypes.c_void_p, U]),
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
        },
        "shcore": {
            "GetDpiForMonitor": (ctypes.c_long, [H, INT, P(U), P(U)]),
        },
        "shell32": {
            "SHQueryUserNotificationState": (ctypes.c_long, [P(INT)]),
        },
    }


#: Functions an older Windows may lack: left unset (the caller checks `hasattr`).
OPTIONAL = frozenset({"SetThreadDpiAwarenessContext", "GetDpiForMonitor", "SHQueryUserNotificationState"})


class Win32:
    """The typed private DLLs: `.user32`, `.gdi32`, `.kernel32`, `.shcore`, `.shell32`."""

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
    for name in ("user32", "gdi32", "kernel32", "shcore", "shell32"):
        try:
            dlls[name] = ctypes.WinDLL(name, use_last_error=True)  # type: ignore[attr-defined]
        except OSError:
            if name not in ("shcore", "shell32"):
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
