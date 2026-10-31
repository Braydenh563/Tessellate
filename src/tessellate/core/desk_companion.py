"""The desktop companion: a small window of its own at the screen's corner.

The owner, 2026-10-27 (BACKLOG 16; INBOX 1464): "is it possible to have the
companion be like a corner thing that can actually show on the user's main
screen outside of the app if they dont have the window open?? like the
chatgpt pets and then if the user clicks it ... a window to quick add a note,
quick search, or to open the app window."

A second pywebview window, frameless and on top, that draws the chosen
companion (`frontend/desktop-companion.html`, which loads the app's own
drawing files) and is visible only while the preference `desktop_companion`
is on and the main window is hidden in the tray. The page's own requests are
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
from typing import Any, Callable

from tessellate.core import background

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


def work_area() -> tuple[int, int, int, int] | None:
    """The screen minus the taskbar, as (left, top, right, bottom), or None
    where it cannot be asked (every platform but Windows)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT()
        # SPI_GETWORKAREA: what a window may use without covering the taskbar.
        if not ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            return None
        return rect.left, rect.top, rect.right, rect.bottom
    except Exception:  # noqa: BLE001
        logger.debug("could not read the work area", exc_info=True)
        return None


def _screen_area(webview: Any) -> tuple[int, int, int, int]:
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
    ) -> None:
        self.webview = webview
        self.main = main_window
        self._open_main = open_main
        self._url = url
        self.transparent = transparent
        #: Where `sync` runs when a window event asks for it: pywebview waits
        #: for a new window to be shown, which on the thread that is handling
        #: an event of the main window would wait for itself.
        self._dispatch = dispatch or background.start
        self.window: Any = None
        self.main_hidden = False
        self.closing = False
        self.size = REST_SIZE
        self.corner: tuple[int, int] | None = None
        self.shown = False

    # --- where it is -----------------------------------------------------------

    def _home(self) -> tuple[int, int]:
        """The saved corner, held inside the screen, else bottom-right above the taskbar."""
        area = _screen_area(self.webview)
        saved = _pref(POS_PREF, None)
        if isinstance(saved, (list, tuple)) and len(saved) == 2 and all(isinstance(v, int) for v in saved):
            return clamp_corner((saved[0], saved[1]), REST_SIZE, area)
        return area[2] - MARGIN, area[3] - MARGIN

    def top_left(self) -> tuple[int, int]:
        corner = self.corner or self._home()
        return corner[0] - self.size[0], corner[1] - self.size[1]

    def resize(self, width: int, height: int) -> tuple[int, int]:
        """Resize about the bottom-right corner, so a panel opens up and to the
        left of the companion rather than off the screen's edge."""
        with _lock:
            self.size = (width, height)
            self.corner = clamp_corner(self.corner or self._home(), self.size, _screen_area(self.webview))
            if self.window is not None:
                self.window.resize(width, height)
                self.window.move(*self.top_left())
            return self.size

    def move_to(self, x: int, y: int) -> bool:
        with _lock:
            if self.window is None:
                return False
            area = _screen_area(self.webview)
            self.corner = clamp_corner((x + self.size[0], y + self.size[1]), self.size, area)
            self.window.move(*self.top_left())
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
        url = self._url() + ("" if self.transparent else "?card=1")
        self.size = REST_SIZE
        self.corner = self._home()
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
        }
        try:
            return self.webview.create_window("Tessellate companion", **options)
        except TypeError:
            # An older pywebview without one of the newer options: a plainer
            # window beats none.
            for name in ("hidden", "easy_drag", "transparent"):
                options.pop(name, None)
            return self.webview.create_window("Tessellate companion", **options)

    def sync(self) -> None:
        """Show it when it is due (on, and the main window in the tray), else hide it."""
        with _lock:
            due = enabled() and self.main_hidden and not self.closing
            try:
                if due and self.window is None:
                    self.window = self._make()
                if self.window is None or due == self.shown:
                    return
                (self.window.show if due else self.window.hide)()
                self.shown = due
            except Exception:  # noqa: BLE001 - a companion that fails never takes the app with it
                logger.warning("the desktop companion window failed", exc_info=True)

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

    def turn_off(self) -> bool:
        """Its own Hide: off until the tray item or Settings turns it on again."""
        _set_pref(PREF, False)
        self.sync()
        return True

    def close(self) -> None:
        """Gone for good (the app is quitting): a hidden window would keep the
        web view's loop from ending."""
        with _lock:
            self.closing = True
            window, self.window = self.window, None
            self.shown = False
        if window is not None:
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                logger.debug("could not destroy the companion window", exc_info=True)


def attach(
    webview: Any,
    main_window: Any,
    open_main: Callable[[str], None],
    url: Callable[[], str],
    *,
    transparent: bool | None = None,
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
    )
    _follow(main_window, companion)
    with _lock:
        _active = companion
    return companion


def _follow(main_window: Any, companion: DeskCompanion) -> None:
    """Wrap the main window's `show` and `hide` so the companion follows them."""
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
        if companion is not None:
            companion.sync()
        if on:
            try:
                icon.notify("It sits in the corner while the window is in the tray.", "Tessellate")
            except Exception:  # noqa: BLE001 - balloons are optional
                logger.debug("could not show the companion balloon", exc_info=True)

    return pystray.MenuItem("Show desktop companion", _toggle, checked=lambda item: enabled())
