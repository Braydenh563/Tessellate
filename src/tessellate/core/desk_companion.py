"""The desktop companion: a small window of its own at the screen's corner.

The owner, 2026-10-27 (BACKLOG 16; INBOX 1464): "is it possible to have the
companion be like a corner thing that can actually show on the user's main
screen outside of the app if they dont have the window open?? like the
chatgpt pets and then if the user clicks it ... a window to quick add a note,
quick search, or to open the app window."

A second pywebview window, frameless and on top, that draws the chosen
companion (`frontend/desktop-companion.html`, which loads the app's own
drawing files) and is visible only while the preference `desktop_companion`
is on and the main window is minimised or hidden in the tray. The page's own requests are
the app's (the same sign-in token, the same origin check); what the page asks
of the *window* (resize, move, open the app, hide) goes through pywebview's
`js_api`, not an HTTP route, so nothing on the network can raise or move a
window and the locked page can still say "Open Tessellate".

Created lazily, the first time it is due: a notebook that never turns the
preference on never pays for a second web view. pywebview has no "window
hidden" event, so `attach` wraps the main window's own `show` and `hide`,
which every way in and out of the tray already goes through (the tray's
items, the close button, a reminder's click, a second launch).

**Not verified on a real Windows desktop** (the sandbox has none): whether the
window is transparent (it is asked to be only off Windows, where the page draws
a small rounded card instead), whether it stays above the taskbar, and how the
position scales on a high-DPI screen.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from typing import Any, Callable

from tessellate.core import jobs

logger = logging.getLogger(__name__)

#: The preference the Settings switch and the tray item write.
PREF = "desktop_companion"
#: Where the person dragged it: the bottom-right corner of the resting window.
POS_PREF = "desktop_companion_pos"

#: The resting window, and the bounds a page may resize it within (a panel for
#: a note or a search is the biggest it gets).
#: The resting window is the character's own box (96 by 138 drawn, plus a
#: margin) and no bigger: a window cannot let clicks through its clear parts
#: without a native region, so the least it covers is what it leaves clickable.
REST_SIZE = (112, 152)
MIN_SIZE = (96, 96)
MAX_SIZE = (480, 560)
#: Clear of the screen's edge and of the taskbar's.
MARGIN = 12
#: The overlay's saved place: its top-left in physical pixels (the card's POS_PREF
#: is a logical bottom-right corner, a different thing).
OVERLAY_POS_PREF = "desktop_companion_overlay_pos"
#: The quick panel opened by a click on the overlay figure, and its gap to it.
PANEL_SIZE = (208, 312)
PANEL_GAP = 8
LOOK_WAIT = 1.5
#: A click on the figure this soon after the panel closed itself on losing focus
#: is the press that took the focus: it closes the panel, it does not reopen it.
BLUR_GRACE = 0.6
#: Asks the app window which Atlas look it draws; empty when it cannot say.
LOOK_SCRIPT = "(function(){try{return typeof atlasLook==='function'?atlasLook():''}catch(e){return ''}})()"

_KIND = re.compile(r"[a-z]{1,16}")
_lock = threading.RLock()
_active: DeskCompanion | None = None


def _config():  # noqa: ANN202
    """The notebook's preferences: the running app's, else read off disk (the
    server may not be up yet when the tray is first asked)."""
    try:
        from tessellate.core import deps

        return deps.get_config()
    except Exception:  # noqa: BLE001 - before the server has built its state
        from tessellate.core.config import ConfigManager

        return ConfigManager()


def _pref(key: str, default: Any) -> Any:
    try:
        return _config().get_preference(key, default)
    except Exception:  # noqa: BLE001 - a notebook we cannot read has it off
        logger.debug("could not read %s", key, exc_info=True)
        return default


def enabled() -> bool:
    return bool(_pref(PREF, False))


def _set_pref(key: str, value: Any) -> None:
    try:
        _config().set_preference(key, value)
    except Exception:  # noqa: BLE001 - remembering is a nicety, the window still works
        logger.warning("could not save %s", key, exc_info=True)


def to_logical(area: tuple[int, int, int, int], dpi: Any) -> tuple[int, int, int, int]:
    """A Win32 rectangle (physical pixels: pywebview makes the process DPI aware)
    in the logical pixels pywebview's `create_window` and `move` take, which it
    multiplies by the display's scale (winforms.py, `Location` and `move`).

    **Why the companion was never seen** (the owner, 2026-11-04, INBOX 1633: the
    log said "window made at (2436, 1340)", "shown", "raised above the desktop:
    True"): that corner was physical, pywebview scaled it again, and at 125% or
    150% the window sat past the screen's right edge. A dpi that is missing or
    not sane reads as 96 (no scaling)."""
    try:
        scale = float(dpi) / 96.0
    except (TypeError, ValueError):
        scale = 1.0
    if not 0.5 <= scale <= 5.0:
        scale = 1.0
    return tuple(int(round(v / scale)) for v in area)  # type: ignore[return-value]


def _system_dpi() -> int:
    try:
        import ctypes

        return int(ctypes.windll.user32.GetDpiForSystem())
    except Exception:  # noqa: BLE001 - before Windows 10 1607
        logger.debug("could not read the system dpi", exc_info=True)
        return 96


def work_area() -> tuple[int, int, int, int] | None:
    """The screen minus the taskbar, as (left, top, right, bottom) in logical
    pixels, or None where it cannot be asked (every platform but Windows)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT()
        # SPI_GETWORKAREA: what a window may use without covering the taskbar.
        if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            return None
        return to_logical((rect.left, rect.top, rect.right, rect.bottom), _system_dpi())
    except Exception:  # noqa: BLE001
        logger.debug("could not read the work area", exc_info=True)
        return None


def monitor_areas() -> list[tuple[int, int, int, int]]:
    """Every connected monitor's work area (left, top, right, bottom) in logical
    pixels at that monitor's own scale, primary first; empty where it cannot be
    asked (every platform but Windows)."""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        import ctypes.wintypes

        wt = ctypes.wintypes

        class _MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

        found: list[tuple[int, int, int, int]] = []
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HANDLE, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)

        def _each(monitor: Any, _dc: Any, _rect: Any, _data: Any) -> int:
            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                area = to_logical((work.left, work.top, work.right, work.bottom), _monitor_dpi(monitor))
                # MONITORINFOF_PRIMARY (1) goes first.
                found.insert(0, area) if info.dwFlags & 1 else found.append(area)
            return 1

        def _monitor_dpi(monitor: Any) -> int:
            dpi_x, dpi_y = wt.UINT(96), wt.UINT(96)
            try:
                # MDT_EFFECTIVE_DPI (0): the scale Settings, Display sets.
                if ctypes.windll.shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                    return int(dpi_x.value)
            except Exception:  # noqa: BLE001 - before Windows 8.1
                logger.debug("could not read a monitor's dpi", exc_info=True)
            return _system_dpi()

        user32.EnumDisplayMonitors(None, None, callback_type(_each), 0)
        return found
    except Exception:  # noqa: BLE001
        logger.debug("could not list the monitors", exc_info=True)
        return []


def pick_area(
    corner: tuple[int, int], areas: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int] | None:
    """The work area a bottom-right `corner` belongs to: the one that holds it
    (its right and bottom edges count), else the primary (first), so a place saved
    on a monitor that has been unplugged comes back onto one that is there."""
    for left, top, right, bottom in areas:
        if left < corner[0] <= right and top < corner[1] <= bottom:
            return left, top, right, bottom
    return areas[0] if areas else None


def _screen_area(webview: Any, corner: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    areas = monitor_areas()
    if areas:
        picked = pick_area(corner, areas) if corner is not None else areas[0]
        if picked:
            return picked
    area = work_area()
    if area:
        return area
    try:
        screen = webview.screens[0]
        return 0, 0, int(screen.width), int(screen.height)
    except Exception:  # noqa: BLE001 - an older pywebview, or no screens
        return 0, 0, 1280, 720


def clamp_corner(corner: tuple[int, int], size: tuple[int, int], area: tuple[int, int, int, int]) -> tuple[int, int]:
    """The bottom-right corner moved the least that keeps a `size` window
    wholly inside `area` (a saved place can be on a screen that is gone)."""
    left, top, right, bottom = area
    x = min(max(int(corner[0]), left + size[0]), right)
    y = min(max(int(corner[1]), top + size[1]), bottom)
    return x, y


def panel_corner(
    pet: tuple[int, int, int, int], size: tuple[int, int], area: tuple[int, int, int, int]
) -> tuple[int, int]:
    """The bottom-right corner for a `size` panel beside the figure `pet`
    (x, y, width, height, logical pixels): to its left when that fits inside
    `area`, else to its right, bottoms level; held inside `area` either way."""
    x, y, w, h = pet
    right = x - PANEL_GAP
    if right - size[0] < area[0]:
        right = x + w + PANEL_GAP + size[0]
    return clamp_corner((right, y + h), size, area)


#: Win32 extended window styles. A tool window has no taskbar button and no
#: Alt+Tab entry; no-activate means showing it never steals the keyboard from
#: what the person is typing in. APPWINDOW would force a taskbar button back.
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_APPWINDOW = 0x00040000


def companion_ex_style(style: int) -> int:
    """`style` (a window's extended style) as the companion needs it: a tool
    window that does not take focus, never an app window."""
    return (int(style) | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW


#: SetWindowPos: HWND_TOPMOST, and the flags that move nothing, resize nothing,
#: take no focus, show the window and do not wait for its thread
#: (SWP_ASYNCWINDOWPOS; see `raise_on_desktop`).
HWND_TOPMOST = -1
SWP_FLAGS = 0x0001 | 0x0002 | 0x0010 | 0x0040 | 0x4000  # NOSIZE | NOMOVE | NOACTIVATE | SHOWWINDOW | ASYNCWINDOWPOS
SW_HIDE = 0
SW_RESTORE = 9
SW_SHOWNOACTIVATE = 4
#: How long a show or hide waits for another one before it gives up (seconds):
#: a stuck window never holds the tray's menu with it.
LOCK_WAIT = 5.0


def window_handle(window: Any) -> int | None:
    """The native handle of a pywebview window on Windows (its WinForms form), or None.
    Read only once the window is shown, so the handle already exists: reading it
    earlier would make the form on this (worker) thread."""
    try:
        return int(window.native.Handle.ToInt64())
    except Exception as exc:  # noqa: BLE001 - not WinForms, or not built yet
        logger.debug("desk companion: no native handle (%s); the window stays an ordinary one", exc)
        return None


#: SetWindowPos for an exact place: no activate, show, async (never waits on the
#: window's own thread); size and position both applied.
SWP_PLACE = 0x0010 | 0x0040 | 0x4000


def physical_rect(rect: tuple[int, int, int, int], dpi: Any) -> tuple[int, int, int, int]:
    """A logical (x, y, width, height) in the physical pixels SetWindowPos takes.

    **Why it is set by hand** (the owner, 2026-11-04, 200% scaling: the companion
    showed as a card twice its size running off the screen's right edge, its
    left edge in the right place): pywebview sets the form's size in physical
    pixels and WinForms' `AutoScaleMode.Dpi` scales it again when the form first
    shows. The place after every show is the one this returns."""
    try:
        scale = float(dpi) / 96.0
    except (TypeError, ValueError):
        scale = 1.0
    if not 0.5 <= scale <= 5.0:
        scale = 1.0
    return tuple(int(round(v * scale)) for v in rect)  # type: ignore[return-value]


def raise_on_desktop(window: Any, rect: tuple[int, int, int, int] | None = None) -> bool:
    """Windows only: make the shown window a tool window (no taskbar button),
    topmost and not minimised, and put it back above the other topmost windows.

    Why a window can be invisible although the taskbar's thumbnail shows it:
    Wallpaper Engine and similar tools parent their wallpaper under the desktop's
    WorkerW layer, and a window that is minimised, off every monitor, or not
    topmost when the wallpaper window is re-stacked can end up behind it. Called
    after every show, so the order is reasserted each time it is due.

    **Only Win32 calls that do not wait** (the owner, 2026-11-04: the companion
    "not responding" on the taskbar and the tray icon frozen). This runs on a
    worker thread. Setting WinForms' `ShowInTaskbar` here re-made the form's
    handle on that thread, which runs no message loop: the window hung, and the
    next show waited on it for good while holding the lock the tray's toggle
    needs. The taskbar button goes with the extended style instead (hidden,
    restyled, shown again), and every call is the async kind."""
    if sys.platform != "win32":
        return False
    handle = window_handle(window)
    if not handle:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        get_style, set_style = user32.GetWindowLongPtrW, user32.SetWindowLongPtrW
        get_style.restype = set_style.restype = ctypes.c_ssize_t
        gwl_exstyle = -20
        was = get_style(handle, gwl_exstyle)
        want = companion_ex_style(was)
        if want != was:
            #: A taskbar button follows the style only from the next show.
            user32.ShowWindowAsync(handle, SW_HIDE)
            set_style(handle, gwl_exstyle, want)
        if user32.IsIconic(handle):
            user32.ShowWindowAsync(handle, SW_RESTORE)
        user32.ShowWindowAsync(handle, SW_SHOWNOACTIVATE)
        if rect is None:
            user32.SetWindowPos(handle, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        else:
            try:
                dpi = int(user32.GetDpiForWindow(handle)) or 96
            except Exception:  # noqa: BLE001 - before Windows 10 1607
                dpi = _system_dpi()
            x, y, width, height = physical_rect(rect, dpi)
            user32.SetWindowPos(handle, HWND_TOPMOST, x, y, width, height, SWP_PLACE)
            #: The move is posted (`SWP_ASYNCWINDOWPOS`), so where it really
            #: landed is read a moment later: one log line that says whether
            #: the size and corner held (INBOX 1633, the owner's 200% display).
            #: The first show can land as a smaller square (WinForms rescales
            #: the new form after the move; INBOX 1650), so a show that did not
            #: hold is placed once more.
            _read_back(handle, (x, y, width, height), dpi, again=True)
        return True
    except Exception:  # noqa: BLE001
        logger.debug("could not raise the companion window", exc_info=True)
        return False


def place_on_screen(window: Any, rect: tuple[int, int, int, int]) -> bool:
    """Windows only: move and size the window to a logical `rect`, set in
    physical pixels at the window's own dpi, without a show or a z-order change."""
    if sys.platform != "win32":
        return False
    handle = window_handle(window)
    if not handle:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            dpi = int(user32.GetDpiForWindow(handle)) or 96
        except Exception:  # noqa: BLE001 - before Windows 10 1607
            dpi = _system_dpi()
        x, y, width, height = physical_rect(rect, dpi)
        swp_nozorder = 0x0004
        user32.SetWindowPos(handle, 0, x, y, width, height, (SWP_PLACE & ~0x0040) | swp_nozorder)
        _read_back(handle, (x, y, width, height), dpi)
        return True
    except Exception:  # noqa: BLE001
        logger.debug("could not place the companion window", exc_info=True)
        return False


def _read_back(handle: int, want: tuple[int, int, int, int], dpi: int, again: bool = False) -> None:
    """Read the window's place back half a second on, on a listed thread (the
    move is posted, so it lands a moment later)."""

    def later() -> None:
        time.sleep(0.5)
        _log_placed(handle, want, dpi, again)

    jobs.thread("desk-placed", later)


def _log_placed(handle: int, want: tuple[int, int, int, int], dpi: int, again: bool = False) -> None:
    """Log the window's real rectangle against the one asked for (physical
    pixels); with `again`, a place that did not hold is set once more."""
    try:
        import ctypes
        import ctypes.wintypes

        box = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(handle, ctypes.byref(box))
        got = (box.left, box.top, box.right - box.left, box.bottom - box.top)
        logger.info("desk companion: placed at %s, asked %s, dpi %s, held: %s", got, want, dpi, got == want)
        if again and got != want:
            ctypes.windll.user32.SetWindowPos(handle, 0, *want, (SWP_PLACE & ~0x0040) | 0x0004)
            _read_back(handle, want, dpi)
    except Exception:  # noqa: BLE001 - a log line, never worth a failure
        logger.debug("could not read the companion's place back", exc_info=True)


def clean_size(width: Any, height: Any) -> tuple[int, int]:
    """A size the page asked for, held to the bounds; junk gives the resting size."""
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return REST_SIZE
    return (
        min(max(w, MIN_SIZE[0]), MAX_SIZE[0]),
        min(max(h, MIN_SIZE[1]), MAX_SIZE[1]),
    )


def hit_script(kind: Any, ident: Any) -> str:
    """The one line of script that opens a search hit in the app window, or
    "" for anything that is not a known kind and a whole number. Both are
    checked here: the page is not trusted with a script of the app's."""
    from tessellate.search import index as search_index

    if not isinstance(kind, str) or not _KIND.fullmatch(kind) or kind not in search_index.KINDS:
        return ""
    if isinstance(ident, bool) or not isinstance(ident, int) or ident < 0:
        return ""
    return (
        "if (typeof routeHashFor === 'function') {"
        f" const h = routeHashFor({json.dumps(kind)}, {ident}); if (h) location.hash = h; }}"
    )


#: Settings, only past the lock screen, as the tray's own items go.
SETTINGS_SCRIPT = (
    "if (document.getElementById('lock-overlay')?.classList.contains('hidden')"
    " && typeof openSettingsModal === 'function') { openSettingsModal('models', 'avatar-buddy'); }"
)


class DeskApi:
    """What the companion's page may ask of its window. Only public methods
    are exposed to the page (pywebview), and each validates what it is given:
    the page is the notebook's own, but a note's text is drawn in it."""

    def __init__(self, owner: DeskCompanion) -> None:
        self._owner = owner

    def open_app(self, where: str = "") -> bool:
        return self._owner.open_main(SETTINGS_SCRIPT if where == "settings" else "")

    def open_hit(self, kind: Any, ident: Any) -> bool:
        return self._owner.open_main(hit_script(kind, ident))

    def set_size(self, width: Any, height: Any) -> list[int]:
        return list(self._owner.resize(*clean_size(width, height)))

    def drag_start(self) -> list[int]:
        return list(self._owner.top_left())

    def drag_to(self, x: Any, y: Any) -> bool:
        try:
            return self._owner.move_to(int(x), int(y))
        except (TypeError, ValueError):
            return False

    def drag_end(self) -> bool:
        return self._owner.remember_place()

    def hide_companion(self) -> bool:
        return self._owner.turn_off()

    def hide_panel(self) -> bool:
        return self._owner.hide_panel()

    def panel_blur(self) -> bool:
        return self._owner.panel_blur()

    def panel_kind(self) -> str:
        return self._owner.panel_kind()


class DeskCompanion:
    """The second window and when it is shown (see the module's docstring)."""

    def __init__(
        self,
        webview: Any,
        main_window: Any,
        open_main: Callable[[str], None],
        url: Callable[[], str],
        *,
        transparent: bool = False,
        dispatch: Callable[[str, Callable[[], None]], Any] | None = None,
        overlay_factory: Callable[..., Any] | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.webview = webview
        self.main = main_window
        self._open_main = open_main
        self._url = url
        self.transparent = transparent
        #: Where `sync` runs when a window event asks for it: pywebview waits
        #: for a new window to be shown, which on the thread that is handling
        #: an event of the main window would wait for itself.
        self._dispatch = dispatch or jobs.thread
        self.window: Any = None
        self.main_hidden = False
        self.closing = False
        self.size = REST_SIZE
        self.corner: tuple[int, int] | None = None
        self.shown = False
        #: The tray's own refresh (pystray `Icon.update_menu`): its menu is
        #: built once on Windows, so a tick it shows is only as fresh as the
        #: last rebuild (INBOX 1642: hidden from its own menu, still ticked).
        self.on_change: Callable[[], Any] | None = None
        self._ticked: bool | None = None
        #: The see-through figure that walks the desktop (`core/overlay`; Windows).
        #: None means the card window only. A failure to start it is final for the
        #: session: the card is used and a warning says why.
        self._overlay_factory = overlay_factory
        self.runner: Any = None
        self.overlay_failed = False
        self.look = "masculine"
        #: The figure's rectangle (logical pixels) at the last click, and whether
        #: `window` is the quick panel beside it rather than the card.
        self.pet_rect: tuple[int, int, int, int] | None = None
        self.panel = False
        self.panel_shown = False
        self._now = now
        self._blurred_at = -1e9
        #: Which menu the panel page opens on when it first asks (a right click
        #: on a new page cannot be sent: the page is not listening yet).
        self._pending_kind = "menu"
        #: The figure's size in physical pixels and dpi at the last click.
        self._pet_phys: tuple[int, int, int] | None = None

    # --- where it is -----------------------------------------------------------

    def _home(self) -> tuple[int, int]:
        """The saved corner, held inside the screen, else bottom-right above the taskbar."""
        saved = _pref(POS_PREF, None)
        if isinstance(saved, (list, tuple)) and len(saved) == 2 and all(isinstance(v, int) for v in saved):
            # The monitor the corner is on, else the primary: a place saved on a
            # screen that is gone must not leave the window where no one can see it.
            area = _screen_area(self.webview, (saved[0], saved[1]))
            return clamp_corner((saved[0], saved[1]), REST_SIZE, area)
        area = _screen_area(self.webview)
        return area[2] - MARGIN, area[3] - MARGIN

    def top_left(self) -> tuple[int, int]:
        corner = self.corner or self._home()
        return corner[0] - self.size[0], corner[1] - self.size[1]

    def resize(self, width: int, height: int) -> tuple[int, int]:
        """Resize about the bottom-right corner, so a panel opens up and to the
        left of the companion rather than off the screen's edge."""
        with _lock:
            self.size = (width, height)
            corner = self.corner or self._home()
            if self.panel and self.pet_rect is not None:
                self.corner = panel_corner(self.pet_rect, self.size, _screen_area(self.webview, corner))
            else:
                self.corner = clamp_corner(corner, self.size, _screen_area(self.webview, corner))
            if self.window is not None:
                self._place()
            return self.size

    def move_to(self, x: int, y: int) -> bool:
        with _lock:
            if self.window is None:
                return False
            corner = (x + self.size[0], y + self.size[1])
            self.corner = clamp_corner(corner, self.size, _screen_area(self.webview, corner))
            self._place()
            return True

    def remember_place(self) -> bool:
        """The corner it rests at: a panel's size does not move where it lives."""
        corner = self.corner
        if corner is None:
            return False
        _set_pref(POS_PREF, [int(corner[0]), int(corner[1])])
        return True

    # --- when it is shown ------------------------------------------------------

    def _make(self) -> Any:
        """The window, hidden, made the first time it is due."""
        url = self._url() + ("?card=1&overlay=1" if self.panel else "" if self.transparent else "?card=1")
        self.size = PANEL_SIZE if self.panel else REST_SIZE
        self.corner = self.corner if self.panel and self.corner else self._home()
        x, y = self.top_left()
        options: dict[str, Any] = {
            "url": url,
            "width": self.size[0],
            "height": self.size[1],
            "x": x,
            "y": y,
            "frameless": True,
            "on_top": True,
            "resizable": False,
            "easy_drag": False,
            "transparent": self.transparent,
            "hidden": True,
            "js_api": DeskApi(self),
            # Does not take focus when shown; the taskbar button is removed in
            # `raise_on_desktop` (pywebview has no option for it).
            "focus": self.panel,
            # pywebview's default minimum is 200 by 100: wider than the resting
            # 112, so the form grew to a card with the character in its right
            # half (the owner's screenshot at 200%, INBOX 1633).
            "min_size": MIN_SIZE,
        }
        try:
            return self.webview.create_window("Tessellate companion", **options)
        except TypeError:
            # An older pywebview without one of the newer options: a plainer
            # window beats none.
            for name in ("hidden", "easy_drag", "transparent", "focus", "min_size"):
                options.pop(name, None)
            return self.webview.create_window("Tessellate companion", **options)

    # --- the overlay (Windows) ---------------------------------------------------

    def _read_look(self) -> str:
        """Which Atlas look the app window draws, asked of it (its choice lives in
        that window's storage). Bounded: a hidden window may not answer, and then
        the last look stands."""
        found: list[Any] = []

        def ask() -> None:
            try:
                found.append(self.main.evaluate_js(LOOK_SCRIPT))
            except Exception:  # noqa: BLE001 - the last look stands
                logger.debug("desk companion: could not ask the app window for its look", exc_info=True)

        worker = jobs.thread("desk-look", ask)
        worker.join(LOOK_WAIT)
        if found and found[0] in ("masculine", "feminine"):
            return found[0]
        logger.info("desk companion: the app window gave no look, keeping %s", self.look)
        return self.look

    def _overlay_home(self) -> tuple[int, int] | None:
        saved = _pref(OVERLAY_POS_PREF, None)
        if isinstance(saved, (list, tuple)) and len(saved) == 2 and all(isinstance(v, int) for v in saved):
            return int(saved[0]), int(saved[1])
        return None

    def _start_overlay(self) -> bool:
        """The runner for the look in force, made when first due and again if the
        look changed; False (a warning logged) when it cannot start."""
        look = self._read_look()
        if self.runner is not None and self.look == look:
            return True
        self.look = look
        self._stop_runner()
        try:
            runner = self._overlay_factory(  # type: ignore[misc]
                look=look,
                home=self._overlay_home(),
                on_click=self._overlay_click,
                on_settle=self._overlay_settle,
                on_died=self._overlay_died,
            )
            started = runner.start()
        except Exception:  # noqa: BLE001 - any failure means the card window instead
            logger.warning("desk companion: the overlay failed to build", exc_info=True)
            started = False
        if not started:
            self.overlay_failed = True
            logger.warning("desk companion: the overlay could not start, using the card window instead")
            return False
        self.runner = runner
        logger.info("desk companion: overlay started, look=%s", look)
        return True

    def _stop_runner(self) -> None:
        runner, self.runner = self.runner, None
        if runner is not None:
            try:
                runner.stop()
            except Exception:  # noqa: BLE001 - a stuck overlay never blocks the rest
                logger.warning("desk companion: the overlay did not stop cleanly", exc_info=True)

    def _sync_overlay(self, due: bool) -> bool:
        """The overlay's half of `sync` (lock held). True when the overlay handled
        it; False sends `sync` on to the card window."""
        if self._overlay_factory is None or self.overlay_failed:
            return False
        if due:
            if not self._start_overlay():
                return False
            if self.shown:
                return True
            self.runner.show()
            self.shown = True
            logger.info("desk companion: overlay shown")
            return True
        if self.runner is not None and self.shown:
            self.runner.hide()
            self._hide_panel_window()
            self.shown = False
            logger.info("desk companion: overlay hidden")
        return self.runner is not None

    def _hide_panel_window(self) -> None:
        if self.window is not None and self.panel_shown:
            self.window.hide()
            self.panel_shown = False

    def hide_panel(self) -> bool:
        with _lock:
            try:
                self._hide_panel_window()
            except Exception:  # noqa: BLE001
                logger.warning("desk companion: the quick panel did not hide", exc_info=True)
                return False
        return True

    def _overlay_settle(self, x: int, y: int) -> None:
        """A drop: saved, and an open panel follows the figure."""
        _set_pref(OVERLAY_POS_PREF, [int(x), int(y)])
        if not self.panel_shown or self._pet_phys is None:
            return
        if not _lock.acquire(timeout=LOCK_WAIT):
            return
        try:
            if self.closing or self.window is None or not self.panel_shown:
                return
            width, height, dpi = self._pet_phys
            self.pet_rect = to_logical((int(x), int(y), width, height), dpi)
            area = _screen_area(self.webview, (self.pet_rect[0], self.pet_rect[1] + self.pet_rect[3]))
            self.corner = panel_corner(self.pet_rect, self.size, area)
            self._place()
        except Exception:  # noqa: BLE001 - the panel stays where it was
            logger.warning("desk companion: the quick panel did not follow the figure", exc_info=True)
        finally:
            _lock.release()

    def _overlay_died(self) -> None:
        """The overlay's thread ended after a good start (on a worker): the card
        window takes over, as it does when the overlay cannot start."""
        if not _lock.acquire(timeout=LOCK_WAIT):
            logger.warning("desk companion: busy, the overlay's end was not handled")
            return
        try:
            if self.closing or self.runner is None:
                return
            logger.warning("desk companion: the overlay stopped, using the card window instead")
            self._stop_runner()
            self.overlay_failed = True
            window, self.window = self.window, None
            self.panel = self.panel_shown = self.shown = False
            self.corner = None
            self.size = REST_SIZE
            if window is not None:
                try:
                    window.destroy()
                except Exception:  # noqa: BLE001
                    logger.debug("could not destroy the quick panel", exc_info=True)
            self._sync_card(enabled() and self.main_hidden)
        except Exception:  # noqa: BLE001 - never takes the app with it
            logger.warning("desk companion: the card window did not come back", exc_info=True)
        finally:
            _lock.release()

    def panel_blur(self) -> bool:
        """The panel page lost focus to something else: close it."""
        with _lock:
            if self.panel_shown:
                self._blurred_at = self._now()
                try:
                    self._hide_panel_window()
                except Exception:  # noqa: BLE001
                    logger.warning("desk companion: the quick panel did not hide", exc_info=True)
                    return False
        return True

    def panel_kind(self) -> str:
        """Which menu a new panel page opens on; asked once when it is ready."""
        with _lock:
            kind, self._pending_kind = self._pending_kind, "menu"
        return kind

    def _overlay_click(self, kind: str, rect: tuple[int, int, int, int], dpi: int) -> None:
        """A click (left: the menu; right: settings and Hide) on the figure, on a
        worker. The quick panel is the card window, made the first time, shown
        beside the figure and taking the keyboard like any window."""
        if kind not in ("left", "right"):
            return
        if not _lock.acquire(timeout=LOCK_WAIT):
            logger.warning("desk companion: busy, a click on the figure is skipped")
            return
        try:
            if self.closing:
                return
            if self.panel_shown and kind == "left":
                self._hide_panel_window()
                return
            if kind == "left" and self._now() - self._blurred_at < BLUR_GRACE:
                return
            self.pet_rect = to_logical(rect, dpi)
            self._pet_phys = (rect[2], rect[3], int(dpi) if isinstance(dpi, (int, float)) and dpi > 0 else 96)
            self._pending_kind = "context" if kind == "right" else "menu"
            area = _screen_area(self.webview, (self.pet_rect[0], self.pet_rect[1] + self.pet_rect[3]))
            self.panel = True
            self.size = PANEL_SIZE
            self.corner = panel_corner(self.pet_rect, self.size, area)
            fresh = self.window is None
            if fresh:
                self.window = self._make()
                logger.info("desk companion: quick panel made beside the figure at %s", self.top_left())
            else:
                self._place()
            self.window.show()
            self.panel_shown = True
            self._place()
            if not fresh:
                self.window.evaluate_js(
                    "window.dispatchEvent(new CustomEvent('desk-open',{detail:%s}))" % json.dumps("context" if kind == "right" else "menu")
                )
            logger.info("desk companion: quick panel shown (%s)", kind)
        except Exception:  # noqa: BLE001 - a panel that fails leaves the figure walking
            logger.warning("desk companion: the quick panel failed", exc_info=True)
        finally:
            _lock.release()

    def sync(self) -> None:
        """Show it when it is due (on, and the main window minimised or in the tray), else hide it."""
        if not _lock.acquire(timeout=LOCK_WAIT):
            logger.warning("the desktop companion is still busy with its last show or hide; this one is skipped")
            return
        try:
            on = enabled()
            if on != self._ticked:
                self._ticked = on
                self._refresh_tray()
            due = on and self.main_hidden and not self.closing
            #: One line a step (INBOX 1633: the owner could not see it; the log says where it stopped).
            logger.info("desk companion: due=%s (on=%s, window away=%s, shown=%s)", due, enabled(), self.main_hidden, self.shown)
            try:
                if not self._sync_overlay(due):
                    self._sync_card(due)
            except Exception:  # noqa: BLE001 - a companion that fails never takes the app with it
                logger.warning("the desktop companion window failed", exc_info=True)
        finally:
            _lock.release()

    def _sync_card(self, due: bool) -> None:
        """The card window's half of `sync` (lock held)."""
        if due and self.window is None:
            self.window = self._make()
            logger.info(
                "desk companion: window made at %s, size %s, in %s (logical pixels)",
                self.top_left(), self.size, _screen_area(self.webview, self.corner),
            )
        if self.window is None or due == self.shown:
            return
        (self.window.show if due else self.window.hide)()
        self.shown = due
        logger.info("desk companion: %s", "shown" if due else "hidden")
        if due:
            # Back onto a monitor that is there (one may have gone while it
            # was hidden), then a tool window above the desktop layer.
            corner = self.corner or self._home()
            fixed = clamp_corner(corner, self.size, _screen_area(self.webview, corner))
            if fixed != self.corner:
                self.corner = fixed
                self.window.move(*self.top_left())
            rect = (*self.top_left(), *self.size)
            logger.info("desk companion: raised above the desktop at %s: %s", rect, raise_on_desktop(self.window, rect))

    def set_main_hidden(self, hidden: bool) -> None:
        self.main_hidden = hidden
        self._dispatch("desk-companion", self.sync)

    def open_main(self, script: str = "") -> bool:
        try:
            self._open_main(script)
            return True
        except Exception:  # noqa: BLE001
            logger.warning("the companion could not open the app window", exc_info=True)
            return False

    def _place(self) -> None:
        """Size and place it. On Windows in physical pixels straight to the
        window (pywebview's `resize` and `move` scale them, and WinForms may
        scale the size again: the owner's log asked 224 by 304 and read back
        232 by 233, INBOX 1633); elsewhere pywebview's own calls."""
        rect = (*self.top_left(), *self.size)
        if place_on_screen(self.window, rect):
            return
        self.window.resize(*self.size)
        self.window.move(*rect[:2])

    def _refresh_tray(self) -> None:
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception:  # noqa: BLE001 - a stale tick beats a failed hide
            logger.debug("could not refresh the tray menu", exc_info=True)

    def turn_off(self) -> bool:
        """Its own Hide: off until the tray item or Settings turns it on again."""
        _set_pref(PREF, False)
        self._dispatch("desk-companion", self.sync)
        return True

    def close(self) -> None:
        """Gone for good (the app is quitting): a hidden window would keep the
        web view's loop from ending. Never waits on a stuck show for long: the
        app's way out must not hang behind it."""
        got = _lock.acquire(timeout=LOCK_WAIT)
        try:
            self.closing = True
            window, self.window = self.window, None
            self.shown = False
        finally:
            if got:
                _lock.release()
        self._stop_runner()
        if window is not None:
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                logger.debug("could not destroy the companion window", exc_info=True)


def _default_overlay_factory() -> Callable[..., Any] | None:
    """The see-through figure is the Windows default; elsewhere the card window
    (or the see-through web window) stays."""
    if sys.platform != "win32":
        return None
    from tessellate.core.overlay.runner import OverlayRunner

    return OverlayRunner


def attach(
    webview: Any,
    main_window: Any,
    open_main: Callable[[str], None],
    url: Callable[[], str],
    *,
    transparent: bool | None = None,
    on_change: Callable[[], Any] | None = None,
    overlay_factory: Any = "auto",
) -> DeskCompanion:
    """Make the companion for `main_window` and follow it into and out of the
    tray. `transparent` defaults to every platform but Windows, where a frameless
    web view cannot be made see-through and the page draws a card instead."""
    global _active
    companion = DeskCompanion(
        webview,
        main_window,
        open_main,
        url,
        transparent=(sys.platform != "win32") if transparent is None else transparent,
        overlay_factory=_default_overlay_factory() if overlay_factory == "auto" else overlay_factory,
    )
    companion.on_change = on_change
    followed = _follow(main_window, companion)
    with _lock:
        _active = companion
    #: At start, so a log with no later companion line still says it was wired (INBOX 1633).
    logger.info("desk companion: attached (on=%s, follows %s)", enabled(), ", ".join(followed))
    return companion


def _follow(main_window: Any, companion: DeskCompanion) -> list[str]:
    """Wrap the main window's `show` and `hide` so the companion follows them.
    The window events it also follows, by name."""
    show, hide = main_window.show, main_window.hide

    def shown(*args: Any, **kwargs: Any) -> Any:
        result = show(*args, **kwargs)
        companion.set_main_hidden(False)
        return result

    def hidden(*args: Any, **kwargs: Any) -> Any:
        result = hide(*args, **kwargs)
        companion.set_main_hidden(True)
        return result

    main_window.show, main_window.hide = shown, hidden
    #: Minimised counts as away too (the owner, 2026-11-04: "can the desktop
    #: companion show even when I still have the application open but
    #: minimised?"). pywebview's window events, where this version has them.
    events = getattr(main_window, "events", None)
    followed = ["show", "hide"]
    for name, away in (("minimized", True), ("restored", False), ("maximized", False)):
        event = getattr(events, name, None)
        if event is None:
            continue

        def follow(*_args: Any, _away: bool = away) -> None:
            companion.set_main_hidden(_away)

        try:
            event += follow
            followed.append(name)
        except TypeError:
            logger.debug("desk companion: the window has no %s event to follow", name)
    return followed


def shutdown() -> None:
    """Close the companion for good, on every way out. Never raises."""
    with _lock:
        companion = _active
    if companion is not None:
        companion.close()


def tray_menu_item(pystray: Any) -> Any:
    """The tray's "Show desktop companion": a tick that is the preference."""

    def _toggle(icon: Any, item: Any) -> None:
        on = not enabled()
        _set_pref(PREF, on)
        with _lock:
            companion = _active
        #: On a worker, never the tray's own thread: a slow window must not freeze its menu.
        if companion is not None:
            companion._dispatch("desk-companion", companion.sync)  # noqa: SLF001
        if on:
            try:
                icon.notify("It sits in the corner while the window is minimised or in the tray.", "Tessellate")
            except Exception:  # noqa: BLE001 - balloons are optional
                logger.debug("could not show the companion balloon", exc_info=True)

    return pystray.MenuItem("Show desktop companion", _toggle, checked=lambda item: enabled())
