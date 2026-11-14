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
import math
import re
import sys
import threading
import time
from typing import Any, Callable

from tessellate.core import jobs
from tessellate.core.overlay import capture, sizing

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
#: "Roam over windows" (right-click menu): on by default, a pref the person can turn off.
ROAM_PREF = "desktop_companion_roam"
#: "Stay here" (menu): it stands where it is and does not wander until "Roam" is chosen.
STAY_PREF = "desktop_companion_stay"
#: The menu's Activity (research DG5): how lively the figure is.
LIVELY_PREF = "desktop_companion_lively"
LIVELY_LEVELS = ("calm", "usual", "lively")
#: "Hide for 10 minutes" (menu): minutes, and the menu requests the figure takes.
SNOOZE_MINUTES = 10
#: The menu's Small, Medium and Large: the in-app steps (`NMB_SIZES` in avatars.js; a test holds them equal).
SIZE_PRESETS = {"small": 0.8, "medium": 1.0, "large": 1.3}
FIGURE_COMMANDS = ("wave", "come", "wander", "nap", "wake", "perch")
#: The look and motion a readable (unlocked) app window last gave. A locked
#: window has not read its prefs and answers the default look, so these stand
#: until it is unlocked (INBOX 1670: masculine until unlocked).
LOOK_PREF = "desktop_companion_look"
MOTION_PREF = "desktop_companion_motion"
#: What a click on a reminder's card runs in the app window: the Reminders tab, behind
#: the same lock guard as the tray's items and a notification's own click.
REMINDERS_SCRIPT = (
    "if (document.getElementById('lock-overlay')?.classList.contains('hidden')"
    " && typeof switchTab === 'function') { switchTab('reminders'); }"
)
#: The quick panel opened by a click on the overlay figure, and its gap to it.
#: The size the panel window is made and shown at, by the click that opened it: the
#: page then measures its own menu and asks for the exact height (`menuHeight` in
#: desk-companion.js), so this only has to be close, never the other menu's size.
#: INBOX 1683: close was not enough. The guesses were 168 and 124 while the rows measure 516 (11 rows of 38 px and
#: two separators) and 306 (6 rows), so the first open after a start showed a fraction of the menu; they are the
#: measured heights now, and the page's first report refits the window if it still differs by `REFIT_PX`.
PANEL_SIZES = {"menu": (248, 516), "context": (248, 306)}
#: A first height report this far from what the window was placed at refits it, once per menu kind.
REFIT_PX = 12
PANEL_GAP = 8
LOOK_WAIT = 1.5
#: A companion whose frames failed to draw is tried again after this many seconds.
RENDER_RETRY = 300.0
#: How often, and how long apart, the figure is read while the app window has not redrawn it since a choice
#: (INBOX 1692 i: "You, from your name" was ticked and the desk kept Atlas).
FIGURE_READS = 4
#: A see-through figure that could not start is tried again when the app window next comes forward and goes
#: away again, this many times in all (INBOX 1692 k: one slow start put the card up for good).
OVERLAY_TRIES = 3
#: ...and, in a sync that is due, no sooner than this many seconds after the failure.
OVERLAY_RETRY_GAP = 20.0
#: A runner that died is brought back where it stood only this soon after (its retry waits `OVERLAY_RETRY_GAP` at
#: least); later, or a second start, uses the saved place, which an arrival home keeps current.
LAST_PLACE_KEEP = 3 * OVERLAY_RETRY_GAP
FIGURE_GAP = 0.4
NOTE_DRAWING = "Summoning your companion to the desk. Atlas keeps you company until it arrives."
NOTE_FAILED = "Your companion could not be summoned to the desk yet, so Atlas stays. It will try again."
#: A click on the figure this soon after the panel closed itself on losing focus
#: is the press that took the focus: it closes the panel, it does not reopen it.
BLUR_GRACE = 0.6
#: Asks the app window which companion it draws (Atlas and its look, or one of the person's own and a hash of
#: how it looks, `capture.FIGURE_JS`) and how the companion may move
#: (Appearance > Companion movement, resolved by `nameMarkBuddyMotion`), in one
#: round trip; empty when it cannot say. A bare look string is still understood.
LOOK_SCRIPT = (
    "(function(){try{const lk=document.getElementById('lock-overlay');return JSON.stringify({"
    "locked:!!(lk&&!lk.classList.contains('hidden')),"
    "look:typeof atlasLook==='function'?atlasLook():'',"
    "who:typeof appearancePref==='function'?appearancePref('avatar-buddy','off'):'off',"
    "figure:" + capture.FIGURE_JS + ","
    "size:typeof nameMarkBuddyScaleSaved==='function'?nameMarkBuddyScaleSaved():1,"
    "motion:typeof nameMarkBuddyMotion==='function'?nameMarkBuddyMotion():null})}catch(e){return ''}})()"
)
#: Appearance > Companion size, written as the app's own handle writes it (`nameMarkBuddySetSize`: the pref, the select
#: that shows "As you sized it", the in-app figure), from the desk figure's handle. `%s` is a number.
SIZE_SCRIPT = (
    "(function(){try{const v=%s;if(typeof nameMarkBuddySetSize==='function')nameMarkBuddySetSize(v,true);"
    "else prefs.set('avatar-buddy-size',String(v));return true}catch(e){return false}})()"
)
#: "Let it walk": the app's own setting set to Always, as its menu would, then the
#: setting's hint refreshed. True when the app window did it.
WALK_SCRIPT = (
    "(function(){try{prefs.set('avatar-buddy-motion','always');"
    "if(typeof nameMarkBuddyMotionApply==='function')nameMarkBuddyMotionApply();return true}catch(e){return false}})()"
)
#: What the right-click "Companion" panel needs of the app window: whether it is locked
#: and the choices the app's own menu and Appearance keep (`avatar-buddy`: off, me,
#: persona, atlas, custom; `atlas-look`; the saved companions in `avatar-buddy-presets`).
COMPANION_LOCK = (
    "const lk=document.getElementById('lock-overlay');"
    "if(lk&&!lk.classList.contains('hidden'))return 'locked';"
)
COMPANION_SCRIPT = (
    "(function(){try{const lk=document.getElementById('lock-overlay');"
    "const locked=!!(lk&&!lk.classList.contains('hidden'));let presets=[];"
    "try{const l=prefs.json('avatar-buddy-presets',[]);if(Array.isArray(l))presets=l.map(function(p){"
    "const v=(p&&p.values)||{};return {name:String((p&&p.name)||'').slice(0,30),who:String(v['avatar-buddy']||''),look:String(v['atlas-look']||'')}})}catch(e){}"
    "return JSON.stringify({locked:locked,who:prefs.get('avatar-buddy',null)||'off',"
    "look:typeof appearancePref==='function'?appearancePref('atlas-look'):'auto',presets:presets})}catch(e){return ''}})()"
)
#: Writes the app's own prefs for an Atlas choice, as its Companion menu does (the select's
#: change handlers: `avatar-buddy`, then the custom row, the corner companion and the size row
#: follow; `atlas-look` repaints), and says "ok". A locked app is refused.
COMPANION_ATLAS = (
    "(function(){try{" + COMPANION_LOCK + "prefs.set('avatar-buddy','atlas');prefs.set('atlas-look',%s);"
    "if(typeof mountBuddyCustom==='function')mountBuddyCustom();"
    "if(typeof atlasRepaint==='function')atlasRepaint();"
    "if(typeof syncNameMarkBuddy==='function')syncNameMarkBuddy();"
    "if(typeof nameMarkBuddySizeSelect==='function')nameMarkBuddySizeSelect();return 'ok'}catch(e){return 'error'}})()"
)
#: One of the person's own companions (`me`, `persona`, `custom`): the same writes, without an Atlas look.
COMPANION_KIND = (
    "(function(){try{" + COMPANION_LOCK + "prefs.set('avatar-buddy',%s);"
    "if(typeof mountBuddyCustom==='function')mountBuddyCustom();"
    "if(typeof syncNameMarkBuddy==='function')syncNameMarkBuddy();"
    "if(typeof nameMarkBuddySizeSelect==='function')nameMarkBuddySizeSelect();return 'ok'}catch(e){return 'error'}})()"
)
#: A saved companion applied by its own function when the app has loaded it; else its two
#: prefs the overlay shows are written at once and the rest follows when the module loads.
COMPANION_PRESET = (
    "(function(){try{" + COMPANION_LOCK + "const p=(prefs.json('avatar-buddy-presets',[])||[])[%d];"
    "if(!p||p.name!==%s)return 'gone';const v=p.values||{};"
    "if(typeof nameMarkBuddyApplyPreset==='function'){nameMarkBuddyApplyPreset(p);return 'ok'}"
    "prefs.set('avatar-buddy',v['avatar-buddy']||'off');"
    "if(v['atlas-look'])prefs.set('atlas-look',v['atlas-look']);else prefs.remove('atlas-look');"
    "if(typeof syncNameMarkBuddy==='function')syncNameMarkBuddy();"
    "if(typeof ensureModule==='function')ensureModule('companionMenu').then(function(){"
    "if(typeof nameMarkBuddyApplyPreset==='function')nameMarkBuddyApplyPreset(p)});return 'ok'}catch(e){return 'error'}})()"
)
_CHOICE_KEY = re.compile(r"atlas:(masculine|feminine|auto)|me|persona|custom|preset:\d{1,2}")
MOTION_MODES = ("full", "fades", "still")
MOTION_REASONS = ("", "os", "app", "setting", "avatar", "perf-ignored", "app-ignored", "os-ignored")

_KIND = re.compile(r"[a-z]{1,16}")


def companion_options(data: Any) -> list[dict[str, Any]]:
    """The right-click "Companion" panel's rows from what the app window said (`COMPANION_SCRIPT`):
    every choice the app offers, the current one marked, all of them choosable. Atlas has frames
    shipped; the others are drawn on this machine from the app's own figure (`capture`, INBOX 1684),
    and Atlas stands in while that happens."""
    if not isinstance(data, dict):
        return []
    who, look = str(data.get("who") or "off"), str(data.get("look") or "auto")
    rows: list[dict[str, Any]] = [
        {"key": f"atlas:{name}", "label": label, "group": "Atlas", "current": who == "atlas" and look == name, "enabled": True}
        for name, label in (("masculine", "Atlas, masculine"), ("feminine", "Atlas, feminine"), ("auto", "Atlas, match your faces"))
    ]
    for kind, label in (("me", "You, from your name"), ("persona", "The chat's persona"), ("custom", "Your own character")):
        rows.append({"key": kind, "label": label, "group": "Yours", "current": who == kind, "enabled": True})
    presets = data.get("presets")
    for index, preset in enumerate(presets[:12] if isinstance(presets, list) else []):
        name = str(preset.get("name") or "")[:30] if isinstance(preset, dict) else ""
        if name:
            rows.append({"key": f"preset:{index}", "label": name, "group": "Saved companions", "current": False, "enabled": True})
    return rows


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

def _look_answer(answer: Any) -> dict[str, Any] | None:
    """The app window's answer to LOOK_SCRIPT as a dict, or None when it gave
    none (a bare look string is the older answer)."""
    if isinstance(answer, str) and answer.startswith("{"):
        try:
            data = json.loads(answer)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None
    if answer in ("masculine", "feminine"):
        return {"look": answer}
    return None


def _motion_of(mode: Any, reason: Any) -> tuple[bool, str] | None:
    """(reduced, reason) for a motion mode, or None for an unknown mode."""
    if mode not in MOTION_MODES:
        return None
    # The reason handed back is the matching constant, never the caller's value: it may have come from
    # a preference read, and code scanning (rightly, by type alone) treats that read as a possible secret
    # once it reaches a log line.
    return (mode != "full", next((r for r in MOTION_REASONS if r == reason), ""))


def figure_key(data: dict[str, Any]) -> str | None:
    """The cache key of the person's own companion the app window draws (`capture`), or None when it
    draws Atlas (also what the chat's default persona is) or nobody, or gave no figure."""
    figure = data.get("figure")
    if data.get("who") not in ("me", "persona", "custom") or not isinstance(figure, dict) or figure.get("atlas") is True:
        return None
    return capture.key_for(figure.get("sig"))


def _figure_unsettled(data: dict[str, Any] | None) -> bool:
    """Your own companion is chosen (and the app is open) but the window has not drawn it: no figure, or Atlas for
    `me` or `custom`. The persona is only unsettled with no figure at all."""
    if not isinstance(data, dict) or data.get("locked") is True or data.get("who") not in ("me", "persona", "custom"):
        return False
    figure = data.get("figure")
    if not isinstance(figure, dict) or not figure.get("sig"):
        return True
    return figure.get("atlas") is True and data.get("who") != "persona"


def _look_label(look: Any) -> str:
    """What a look is called in the log: a drawn companion is named by its capture key (a stored identifier, and
    code scanning reads a value called a key as a secret), so the log says which kind it is, never the key."""
    return "a drawn companion" if capture.is_key(look) else "an Atlas look"


def _motion_label(motion: tuple[bool, str] | None) -> str:
    """The motion in force as words for the log: built only from fixed strings, the reason being the
    matching entry of `MOTION_REASONS` and never the value that was passed in (see `_motion_of`)."""
    if motion is None:
        return "unknown, the system flag decides"
    word = "still" if motion[0] else "moving"
    for known in MOTION_REASONS:
        if known == motion[1]:
            return f"{word} ({known})"
    return f"{word} ()"


def _look_in_force(data: dict[str, Any], look: str) -> tuple[str, tuple[bool, str] | None]:
    """The look and motion an answer stands for. A locked app window has not
    read its prefs and answers the default look (INBOX 1670), so the last
    look and motion an unlocked one gave stand instead, and an unlocked answer
    is remembered. No motion block hands the motion back to the Windows flag."""
    if data.get("look") in ("masculine", "feminine"):
        look = data["look"]
    elif capture.is_key(look):  # another companion's frames never stand in for this one
        look = "masculine"
    key = figure_key(data)
    if key is not None and capture.complete(key):
        look = key
    m = data.get("motion")
    motion = _motion_of(m.get("mode"), m.get("reason")) if isinstance(m, dict) else None
    saved_look = _pref(LOOK_PREF, None)
    if data.get("locked") is True:
        if saved_look in ("masculine", "feminine") or (capture.is_key(saved_look) and capture.complete(saved_look)):
            look = saved_look
            saved = _pref(MOTION_PREF, None)
            if isinstance(saved, (list, tuple)) and len(saved) == 2 and saved[0] in MOTION_MODES:
                motion = _motion_of(saved[0], saved[1])
        return look, motion
    _set_pref(LOOK_PREF, look)
    if motion is not None and isinstance(m, dict):
        _set_pref(MOTION_PREF, [m["mode"], motion[1]])
    return look, motion



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


def _linux_areas() -> list[tuple[int, int, int, int]]:
    """Each monitor's work area on an X11 desktop (EWMH struts and `_NET_WORKAREA`), in the
    logical pixels pywebview takes; empty on Wayland or without a display. A short-lived
    connection: the panel is placed once per click."""
    ok, _note = overlay_support()
    if not ok:
        return []
    try:
        from tessellate.core.overlay import x11

        conn = x11.load()
        try:
            mons = x11.monitors(conn)
            dpi = mons[0][1] if mons else 96
            return [to_logical(a, dpi) for a in x11.work_areas(conn)]
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - the pywebview screen list is the fallback
        logger.debug("could not read the X11 work area", exc_info=True)
        return []


def work_area() -> tuple[int, int, int, int] | None:
    """The screen minus the taskbar, as (left, top, right, bottom) in logical
    pixels, or None where it cannot be asked (Windows and X11 desktops can)."""
    if sys.platform.startswith("linux"):
        areas = _linux_areas()
        return areas[0] if areas else None
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
    asked (Windows and X11 desktops can)."""
    if sys.platform.startswith("linux"):
        return _linux_areas()
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
    (x, y, width, height, logical pixels: the drawn pixels' box, not the window): to its left when that fits inside
    `area`, else to its right, bottoms level; held inside `area` either way."""
    x, y, w, h = pet
    right = x - PANEL_GAP
    if right - size[0] < area[0]:
        right = x + w + PANEL_GAP + size[0]
    return clamp_corner((right, y + h), size, area)


def monitor_for(
    point: tuple[int, int], monitors: list[tuple[tuple[int, int, int, int], int]]
) -> tuple[tuple[int, int, int, int], int]:
    """The (physical work area, dpi) holding a physical point, else the nearest."""
    def gap(m: tuple[tuple[int, int, int, int], int]) -> int:
        left, top, right, bottom = m[0]
        dx, dy = max(left - point[0], 0, point[0] - right + 1), max(top - point[1], 0, point[1] - bottom + 1)
        return dx * dx + dy * dy

    return min(monitors, key=gap)


def panel_placement(
    pet: tuple[int, int, int, int],
    size: tuple[int, int],
    monitors: list[tuple[tuple[int, int, int, int], int]],
    dpi: int | None = None,
) -> tuple[tuple[int, int, int, int], int]:
    """Where the quick panel goes, in physical pixels: ((x, y, width, height), dpi).

    `pet` is the figure's physical rectangle, `size` the panel's logical size,
    `monitors` each work area (physical) with its dpi, and `dpi` the scale of the
    monitor the panel lands on when Windows said (MonitorFromPoint, then
    GetDpiForMonitor); without it the monitor list's own dpi for that monitor is
    used. **Why all in physical pixels** (the owner asked for mixed-dpi screens): a
    logical corner means one scale for the whole desktop, but a 100 percent monitor
    left of a 150 percent primary has no single one, and the panel's own window
    reports the scale of the monitor it last sat on, not the one it lands on. The
    panel is beside the figure, left when that fits on the monitor, else right,
    bottoms level, and held inside that monitor's work area."""
    x, y, w, h = pet
    area, own = monitor_for((x + w // 2, y + h), monitors)
    scale = (dpi or own or 96) / 96.0
    pw, ph = max(1, round(size[0] * scale)), max(1, round(size[1] * scale))
    gap = round(PANEL_GAP * scale)
    right = x - gap
    if right - pw < area[0]:
        right = x + w + gap + pw
    bottom = y + h
    right = min(max(right, area[0] + pw), area[2])
    bottom = min(max(bottom, area[1] + ph), area[3])
    return (right - pw, bottom - ph, pw, ph), int(round(scale * 96))


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
#: How long quitting waits for a window still starting up before destroying it. Destroying a
#: web view mid-start made pywebview log "WebView2 initialization failed ... E_ABORT" (INBOX 1666).
LOADED_WAIT = 1.5


def window_handle(window: Any) -> int | None:
    """The native handle of a pywebview window on Windows (its WinForms form), or None.
    Read only once the window is shown, so the handle already exists: reading it
    earlier would make the form on this (worker) thread."""
    try:
        return int(window.native.Handle.ToInt64())
    except Exception as exc:  # noqa: BLE001 - not WinForms, or its window does not exist yet
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


#: Click-away without focus (INBOX 1689): the panel closes on losing focus, but a click on the figure
#: (a no-activate overlay) need not hand it the focus, so it never lost any and stayed open. While it is
#: shown, a mouse press that starts outside its rectangle closes it too; read this often, Windows only.
CLICK_AWAY_POLL = 0.05
VK_LBUTTON, VK_RBUTTON, VK_MBUTTON = 0x01, 0x02, 0x04


def mouse_down(user32: Any) -> bool:
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (VK_LBUTTON, VK_RBUTTON, VK_MBUTTON))


def press_outside(user32: Any, handle: int, was_down: bool) -> tuple[bool, bool]:
    """(a press began outside the window, the button state now): only a press that starts after the last
    read counts, so the click that opened the panel, still held, does not close it."""
    import ctypes
    import ctypes.wintypes

    down = mouse_down(user32)
    if not down or was_down:
        return False, down
    point, rect = ctypes.wintypes.POINT(), ctypes.wintypes.RECT()
    if not user32.GetCursorPos(ctypes.byref(point)) or not user32.GetWindowRect(handle, ctypes.byref(rect)):
        return False, down
    inside = rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom
    return not inside, down


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


def place_physical(window: Any, box: tuple[int, int, int, int]) -> bool:
    """Windows only: move and size the window to a physical (x, y, width, height)
    exactly, without a show or a z-order change. Done twice: the first move puts the
    window on the monitor it is going to, which can change its dpi and rescale it;
    the second sets the size and place at that dpi, and a read-back later sets them
    once more if they did not hold (a window crossing monitors of different scale)."""
    if sys.platform != "win32":
        return False
    handle = window_handle(window)
    if not handle:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        flags = (SWP_PLACE & ~0x0040) | 0x0004
        user32.SetWindowPos(handle, 0, *box, flags)
        user32.SetWindowPos(handle, 0, *box, flags)
        _read_back(handle, box, 0, again=True)
        return True
    except Exception:  # noqa: BLE001
        logger.debug("could not place the quick panel", exc_info=True)
        return False


#: The newest place asked of each window handle. A read-back that finds the window elsewhere re-sets it only while
#: its own ask is still this one: two asks in flight (the menu's first size, then its measured one) each re-set the
#: window to their own place when they saw the other's, four flips in 0.6 s (INBOX 1716).
_WANTED: dict[int, tuple[int, int, int, int]] = {}


def _read_back(handle: int, want: tuple[int, int, int, int], dpi: int, again: bool = False) -> None:
    """Read the window's place back half a second on, on a listed thread (the
    move is posted, so it lands a moment later)."""
    _WANTED[handle] = want

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
        if again and got != want and _WANTED.get(handle, want) == want:
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


#: New reminder and Open today: the Reminders tab with its quick field focused, and the dashboard,
#: both only past the lock screen like Settings.
NEW_REMINDER_SCRIPT = (
    "if (document.getElementById('lock-overlay')?.classList.contains('hidden')"
    " && typeof switchTab === 'function') { switchTab('reminders');"
    " setTimeout(() => document.getElementById('reminder-magic')?.focus(), 400); }"
)
TODAY_SCRIPT = (
    "if (document.getElementById('lock-overlay')?.classList.contains('hidden')"
    " && typeof switchTab === 'function') { switchTab('dashboard'); }"
)


class _SnoozeTimer:
    """The snooze countdown as a listed thread Job (`jobs.thread`) with the `threading.Timer` surface
    (`start`, `cancel`, `join`, `is_alive`): cancel wakes the wait at once, so closing never lingers."""

    def __init__(self, delay: float, fire: Callable[[], None]) -> None:
        self._delay, self._fire = delay, fire
        self._cancelled = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = jobs.thread("desk-snooze", self._run, stop=self._cancelled.set)

    def _run(self) -> None:
        if not self._cancelled.wait(self._delay):
            self._fire()

    def cancel(self) -> None:
        self._cancelled.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


def _lively_pref() -> str:
    """The saved Activity, Usual when none or an unknown one is saved."""
    saved = _pref(LIVELY_PREF, "usual")
    return saved if saved in LIVELY_LEVELS else "usual"


class DeskApi:
    """What the companion's page may ask of its window. Only public methods
    are exposed to the page (pywebview), and each validates what it is given:
    the page is the notebook's own, but a note's text is drawn in it."""

    def __init__(self, owner: DeskCompanion) -> None:
        self._owner = owner

    def open_app(self, where: str = "") -> bool:
        scripts = {"settings": SETTINGS_SCRIPT, "reminder": NEW_REMINDER_SCRIPT, "today": TODAY_SCRIPT}
        return self._owner.open_main(scripts.get(where, "") if isinstance(where, str) else "")

    def open_hit(self, kind: Any, ident: Any) -> bool:
        return self._owner.open_main(hit_script(kind, ident))

    def set_size(self, width: Any, height: Any, state: Any = "") -> list[int]:
        return list(self._owner.resize(*clean_size(width, height), state=state if isinstance(state, str) else ""))

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

    def panel_motion(self) -> dict[str, Any]:
        return self._owner.panel_motion()

    def let_it_walk(self) -> bool:
        return self._owner.let_it_walk()

    def set_roam(self, on: Any) -> bool:
        return self._owner.set_roam(on is True)

    def figure_do(self, name: Any) -> bool:
        return self._owner.figure_do(name if isinstance(name, str) else "")

    def set_stay(self, on: Any) -> bool:
        return self._owner.set_stay(on is True)

    def set_lively(self, name: Any) -> bool:
        return self._owner.set_lively(name if isinstance(name, str) else "")

    def set_figure_size(self, name: Any) -> bool:
        return self._owner.set_figure_size(name if isinstance(name, str) else "")

    def snooze(self) -> bool:
        return self._owner.snooze()

    def companion_choices(self) -> dict[str, Any]:
        return self._owner.companion_choices()

    def choose_companion(self, key: Any) -> str:
        return self._owner.choose_companion(key if isinstance(key, str) else "")


class DeskCompanion:
    """The second window and when it is shown (see the module's docstring)."""
    _entered = False  # the first show has arrived (INBOX 1718 a)

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
        self._away_at: float | None = None  # when `main_hidden` last changed (`set_main_hidden`'s log line)
        self.closing = False
        self.size = REST_SIZE
        self.corner: tuple[int, int] | None = None
        self.shown = False
        #: Hidden by "Hide for 10 minutes" until this time on `_now`'s clock.
        self.snooze_until = -1e9
        self._snooze_timer: Any = None
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
        self.overlay_tries = 0
        self._overlay_retry_at = 0.0
        self.overlay_why = ""
        #: Why the see-through figure is not used on this machine (Wayland), shown in the card's menu.
        self.overlay_note = ""
        self.look = "masculine"
        #: Appearance > Companion size as the app window last said it (0.7 to 1.6; Medium is 1).
        self.size_pref = sizing.MEDIUM
        #: The page may still say the old size for a moment after the handle wrote a new one: not believed until then.
        self._size_held = 0.0
        #: A size the figure was given that the app window has not taken yet (a write that failed): kept here, written
        #: again on the next sync, and the page's older value does not replace it meanwhile.
        self._size_unsent: float | None = None
        #: How the companion may move, as the app window last said: None until it
        #: answers (then the runner falls back to the Windows animation flag).
        self.motion: tuple[bool, str] | None = None
        #: "Let it walk" when the app window could not be written to: the choice
        #: stands for the session.
        self._walk_forced = False
        #: The saved companions' names the "Companion" panel last listed, by key: a choice
        #: names its saved companion by place, and is refused if the name there changed.
        self._choice_names: dict[str, str] = {}
        #: Companions whose frames are being drawn now, and when a draw last failed, by cache key.
        self._rendering: set[str] = set()
        self._wanted: str | None = None
        self._render_failed: dict[str, float] = {}
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
        #: The one source of the menu panel's height (INBOX 1658: the click and the page
        #: each asked a height, 336 and 308 physical, and the window flipped between
        #: them ten times in two seconds). Python places the panel before it is shown, at
        #: `panel_size(kind)`; the page only reports what it measured, which is kept here
        #: for the next open. `_panel_state` is the page's panel now showing.
        self._panel_heights: dict[str, int] = {}
        self._panel_state = ""
        #: The figure's size in physical pixels and dpi at the last click.
        self._pet_phys: tuple[int, int, int] | None = None
        #: The figure's physical rectangle at the last click or drop, and where the
        #: panel went from it: ((x, y, width, height), dpi) in physical pixels.
        self._pet_box: tuple[int, int, int, int] | None = None
        self._away_watch: threading.Thread | None = None
        self.panel_box: tuple[tuple[int, int, int, int], int] | None = None
        #: Where a runner that died stood, what it was doing (`Engine.carry`) and when: one that died mid-trip came back
        #: at the place saved at the last drop, the old spot (INBOX 1696 i). Used once, by the next start only.
        self._last_place: tuple[int, int] | None = None
        self._last_carry: dict[str, Any] | None = None
        self._last_at = -math.inf

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

    def panel_size(self, kind: str) -> tuple[int, int]:
        """The quick panel's size for a menu kind: the page's last measured height
        when there is one, else the starting guess."""
        width, height = PANEL_SIZES[kind]
        return width, self._panel_heights.get(kind, height)

    def resize(self, width: int, height: int, state: str = "") -> tuple[int, int]:
        """Resize about the bottom-right corner, so a panel opens up and to the
        left of the companion rather than off the screen's edge. The overlay panel's
        menu and context heights are only learned while that menu is the open panel
        (see `_panel_heights`): the window was placed at that size before it was
        shown. It moves again only for a panel the person opens from it (note,
        search) or back from one."""
        with _lock:
            if self.panel and state in PANEL_SIZES:
                first = state not in self._panel_heights
                self._panel_heights[state] = height
                refit = first and self.panel_shown and self._panel_state == state and abs(height - self.size[1]) > REFIT_PX
                if not refit and (self._panel_state in PANEL_SIZES or not self._panel_state):
                    return self.size
            if self.panel and state:
                self._panel_state = state
            self.size = (width, height)
            corner = self.corner or self._home()
            if self.panel and self.pet_rect is not None:
                self.corner = panel_corner(self.pet_rect, self.size, _screen_area(self.webview, corner))
                self._update_panel_box()
            else:
                self.corner = clamp_corner(corner, self.size, _screen_area(self.webview, corner))
            if self.window is not None:
                self._place()
            return self.size

    def _update_panel_box(self) -> None:
        """Where the panel goes in physical pixels, at the dpi of the monitor it lands
        on (`panel_placement`); None when the runner cannot say (the logical corner is used)."""
        runner = self.runner
        monitors = [(tuple(m.area), int(m.dpi)) for m in (getattr(runner, "monitors", None) or [])]
        if self._pet_box is None or not monitors:
            self.panel_box = None
            return
        x, y, w, h = self._pet_box
        dpi = None
        ask = getattr(runner, "dpi_at", None)
        if callable(ask):
            try:
                dpi = ask(x + w // 2, y + h)
            except Exception:  # noqa: BLE001 - the monitor list's dpi then
                logger.debug("desk companion: dpi under the figure unknown", exc_info=True)
        self.panel_box = panel_placement(self._pet_box, self.size, monitors, dpi)  # type: ignore[arg-type]

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
        self.size = self.size if self.panel else REST_SIZE
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

    def _ask_main(self, script: str, what: str, wait: float = LOOK_WAIT) -> Any:
        """One script run in the app window on a worker, waited for at most
        LOOK_WAIT: a hidden window may not answer, and no click may wait on it."""
        found: list[Any] = []

        def ask() -> None:
            try:
                found.append(self.main.evaluate_js(script))
            except Exception:  # noqa: BLE001 - the last answer stands
                logger.debug("desk companion: could not ask the app window for %s", what, exc_info=True)

        worker = jobs.thread("desk-look", ask)
        worker.join(wait)
        return found[0] if found else None

    def _read_look(self) -> tuple[str, tuple[bool, str] | None]:
        """Which Atlas look the app window draws and whether the companion may
        move, asked of it in one round trip (the choices live in that window's
        storage). Bounded; no answer keeps the last look and leaves the motion
        to the last motion answer (the Windows flag before any)."""
        data = self._settled(_look_answer(self._ask_main(LOOK_SCRIPT, "its look and motion")))
        look, motion = self.look, self.motion
        if data is not None and isinstance(data.get("size"), (int, float)) and not isinstance(data.get("size"), bool) and self._size_unsent is None and self._now() >= self._size_held:
            self.size_pref = sizing.clamp(data["size"])
        if data is None:
            logger.info("desk companion: the app window gave no look, keeping %s", _look_label(self.look))
        else:
            look, motion = _look_in_force(data, look)
            self._explain_figure(data)
            self._want_frames(data)
        if self._walk_forced and (motion is None or motion[0]):
            motion = (False, "")
        return look, motion

    def _settled(self, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """The answer, read again (`FIGURE_READS` at most) while the app window has not drawn the figure that was
        chosen: none at all, or Atlas where your own companion was asked for. The first read after a choice can
        come before the window redrew it. The chat's persona may be Atlas on purpose, so it is only waited for
        when there is no figure."""
        for _ in range(FIGURE_READS - 1):
            if not _figure_unsettled(data):
                break
            time.sleep(FIGURE_GAP)
            fresh = _look_answer(self._ask_main(LOOK_SCRIPT, "its look and motion, again"))
            if fresh is None:
                break
            data = fresh
        return data

    def _explain_figure(self, data: dict[str, Any]) -> None:
        """A line in the log whenever your own companion is chosen and there is nothing to draw it from."""
        who = data.get("who")
        if who not in ("me", "persona", "custom") or figure_key(data) is not None:
            return
        figure = data.get("figure")
        if data.get("locked") is True:
            why = "the app window is locked"
        elif not isinstance(figure, dict) or not figure.get("sig"):
            why = "the app window drew no figure"
        elif figure.get("atlas") is True:
            why = "the figure it drew is Atlas" + (" (the chat's default persona)" if who == "persona" else "")
        else:
            why = "the figure has no usable signature"
        logger.info("desk companion: %r is chosen but %s, Atlas stays", who, why)

    def frames_note(self) -> str:
        """One line for the Companion panel while your companion's frames are drawn, or when drawing them failed."""
        key = self._wanted
        if key is None or capture.complete(key):
            return ""
        if key in self._rendering:
            return NOTE_DRAWING
        return NOTE_FAILED if key in self._render_failed else ""

    def _want_frames(self, data: dict[str, Any]) -> None:
        """The person's own companion has no frames yet: draw them from the app window on a worker
        (Atlas stands in until they are there), and restart the figure when they land. A failed
        draw is logged and tried again no sooner than `RENDER_RETRY` seconds on."""
        key = figure_key(data)
        if data.get("locked") is not True:
            self._wanted = key
        if key is None or data.get("locked") is True or capture.complete(key):
            return
        now = self._now()
        if key in self._rendering or now - self._render_failed.get(key, -1e9) < RENDER_RETRY:
            return
        self._rendering.add(key)
        jobs.thread("desk-frames", lambda: self._render_frames(key))

    def _render_frames(self, key: str) -> None:
        try:
            started = time.monotonic()
            frames = capture.fetch_frames(lambda script: self._ask_main(script, "the companion's frames", capture.ASK_WAIT))
            capture.write_set(key, frames)
        except (capture.CaptureError, ValueError, OSError, ImportError) as exc:
            self._render_failed[key] = self._now()
            logger.warning("desk companion: could not draw the companion's frames (%s), Atlas stays", exc)
            return
        finally:
            self._rendering.discard(key)
        logger.info("desk companion: drew %d frames for %s in %.1f s", len(capture.CAPTURED), key, time.monotonic() - started)
        self._restart_shown("companion frames drawn")

    def _overlay_size(self, scale: float) -> None:
        """The figure's handle set a size (on a worker): the app window keeps it as its own handle would, so Appearance
        shows it and the in-app figure follows; remembered per device with the rest of its prefs."""
        value = sizing.clamp(scale)
        self.size_pref = self._size_unsent = value
        self._flush_size()

    def _flush_size(self) -> None:
        """Write the size the app window has not taken yet. Only a `true` from its script clears it; a hidden or locked
        window gives none, and the write is tried again at the next sync (the figure keeps the size meanwhile)."""
        value = self._size_unsent
        if value is None:
            return
        self._size_held = self._now() + 2 * LOOK_WAIT
        if self._ask_main(SIZE_SCRIPT % repr(value), "the size the figure was given") is True and self._size_unsent == value:
            self._size_unsent = None

    def set_figure_size(self, name: str) -> bool:
        """The menu's Small, Medium or Large: the in-app steps, to the running figure and to the app window."""
        value = SIZE_PRESETS.get(name)
        if value is None:
            return False
        self.size_pref = self._size_unsent = value
        runner = self.runner
        if runner is not None and hasattr(runner, "set_scale"):
            runner.set_scale(value)
        self._dispatch("desk-size", self._flush_size)
        return True

    def _overlay_home(self) -> tuple[int, int] | None:
        saved = _pref(OVERLAY_POS_PREF, None)
        if isinstance(saved, (list, tuple)) and len(saved) == 2 and all(isinstance(v, int) for v in saved):
            return int(saved[0]), int(saved[1])
        return None

    def _start_overlay(self) -> bool:
        """The runner for the look and motion in force, made when first due and
        again if either changed; False (a warning logged) when it cannot start."""
        self._flush_size()
        look, motion = self._read_look()
        if self.runner is not None and self.look == look and self.motion == motion:
            if hasattr(self.runner, "set_scale") and getattr(self.runner, "scale", self.size_pref) != self.size_pref:
                self.runner.set_scale(self.size_pref)  # Appearance changed it: the figure eases to it
            return True
        place, carried = self._runner_place(), self._runner_carry()
        self.look, self.motion = look, motion
        self._stop_runner()
        kw: dict[str, Any] = {}
        if motion is not None:
            kw = {"reduced": motion[0], "reduced_reason": motion[1]}
        runner, started = self._build_runner(look, place, kw, carried)
        if not started and capture.is_key(look):
            # A drawn companion whose frames will not load must not cost the whole see-through figure.
            logger.warning("desk companion: the overlay did not start in the drawn companion's frames, trying Atlas")
            look = self.look = "masculine"
            runner, started = self._build_runner(look, place, kw, carried)
        if not started:
            self.overlay_failed = True
            self.overlay_tries += 1
            self._overlay_retry_at = self._now() + OVERLAY_RETRY_GAP
            self.overlay_why = self.overlay_why or "the see-through window did not start"
            logger.warning(
                "desk companion: the overlay could not start (%s), using the card window instead (try %d of %d)",
                self.overlay_why, self.overlay_tries, OVERLAY_TRIES,
            )
            self._drop_panel()
            return False
        self.overlay_why = ""
        self.runner = runner
        logger.info(
            "desk companion: overlay started, look=%s, motion=%s",
            _look_label(look), _motion_label(motion),
        )
        return True

    def _build_runner(
        self, look: str, place: tuple[int, int] | None, kw: dict[str, Any], carried: dict[str, Any] | None = None,
    ) -> tuple[Any, bool]:
        """One try at the runner; (runner, started). The reason a try failed is kept for the card's menu."""
        runner = None
        try:
            runner = self._overlay_factory(  # type: ignore[misc]
                look=look,
                home=place or self._overlay_home(),
                on_click=self._overlay_click,
                on_settle=self._overlay_settle,
                on_died=self._overlay_died,
                on_card=self._overlay_card,
                roam_windows=bool(_pref(ROAM_PREF, True)),
                stay=bool(_pref(STAY_PREF, False)),
                **kw,
            )
            if hasattr(runner, "set_lively"):
                runner.set_lively(_lively_pref())
            if hasattr(runner, "on_size"):  # the size handle: the size Appearance has, and the way back for a pull
                runner.on_size = self._overlay_size
                runner.scale = self.size_pref
            if hasattr(runner, "on_place"):  # a trip arrived where it lives now: saved, as a drop is
                runner.on_place = self._overlay_place
            if hasattr(runner, "carried"):  # a restart: the new figure takes up the home and the menu's trip
                runner.carried = carried
            if hasattr(runner, "enter"):  # the first show arrives (INBOX 1718 a); a restart does not replay it
                runner.enter = not self._entered
            started = bool(runner.start())
            self._entered = self._entered or started
            if not started:
                self.overlay_why = "the see-through window did not start in time"
        except Exception as exc:  # noqa: BLE001 - any failure means the card window instead
            logger.warning("desk companion: the overlay failed to build", exc_info=True)
            self.overlay_why = f"it failed to build ({type(exc).__name__})"
            started = False
        return runner, started

    def _runner_place(self) -> tuple[int, int] | None:
        """Where the running figure is, so a restart does not send it home; with no runner, where the last one stood
        when it stopped (a death mid-trip), before the saved place."""
        if self.runner is None:
            place, self._last_place = self._last_place, None
            return place if self._now() - self._last_at <= LAST_PLACE_KEEP else None
        engine = getattr(self.runner, "engine", None)
        x, y = getattr(engine, "x", None), getattr(engine, "y", None)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and math.isfinite(x) and math.isfinite(y):
            return int(x), int(y)
        return None

    def _runner_carry(self) -> dict[str, Any] | None:
        """What the running figure was doing (`Engine.carry`), for the next runner; the last one's with no runner."""
        if self.runner is None:
            carried, self._last_carry = self._last_carry, None
            return carried if self._now() - self._last_at <= LAST_PLACE_KEEP else None
        carry = getattr(getattr(self.runner, "engine", None), "carry", None)
        try:
            found = carry() if callable(carry) else None
        except Exception:  # noqa: BLE001 - a restart without it ends the trip where it stands
            logger.debug("desk companion: the figure's trip could not be read", exc_info=True)
            return None
        return found if isinstance(found, dict) else None

    def panel_motion(self) -> dict[str, Any]:
        """Whether the figure is standing still and why, for the right-click menu."""
        with _lock:
            runner = self.runner
            still = bool(getattr(runner, "reduced", False)) if runner is not None else False
            reason = getattr(runner, "reduced_reason", "") if still else ""
        note = self.overlay_note or (self._failed_note() if self.overlay_failed else "")
        engine = getattr(runner, "engine", None)
        out: dict[str, Any] = {
            "still": still, "reason": str(reason or ""), "roam": bool(_pref(ROAM_PREF, True)), "stay": bool(_pref(STAY_PREF, False)),
            "lively": _lively_pref(), "size": self.size_pref, "asleep": getattr(engine, "state", "") == "sleep", "figure": runner is not None and hasattr(runner, "command"),
        }
        doing = getattr(engine, "doing", None)
        if callable(doing) and (said := doing()):
            out["doing"] = said  # the menu's first line while a prop or spell is in hand (INBOX 1718 b)
        if note:
            out["note"] = note
        return out

    def _failed_note(self) -> str:
        """The card's one line on why the see-through figure is not there, and whether it will try again."""
        why = self.overlay_why or "it stopped"
        again = " It tries again when you next minimise Tessellate." if self.overlay_tries < OVERLAY_TRIES else ""
        return f"The see-through figure could not start ({why}), so the companion stays in this card.{again}"

    def set_roam(self, on: bool) -> bool:
        """The menu's "Roam over windows": saved, and the running figure follows."""
        _set_pref(ROAM_PREF, bool(on))
        runner = self.runner
        if runner is not None and hasattr(runner, "set_roam"):
            runner.set_roam(bool(on))
        return True

    def figure_do(self, name: str) -> bool:
        """A request from the menu to the walking figure (wave, come here, go somewhere else, nap,
        wake, sit on a window). False when there is no figure to ask or the name is not one of them."""
        runner = self.runner
        if name not in FIGURE_COMMANDS or runner is None or not self.shown or not hasattr(runner, "command"):
            return False
        return bool(runner.command(name))

    def set_lively(self, name: str) -> bool:
        """The menu's Activity: Calm, Usual or Lively, saved, and the running figure follows. False for another name."""
        if name not in LIVELY_LEVELS:
            return False
        _set_pref(LIVELY_PREF, name)
        runner = self.runner
        if runner is not None and hasattr(runner, "set_lively"):
            runner.set_lively(name)
        return True

    def set_stay(self, on: bool) -> bool:
        """"Stay here" or "Roam": saved, and the running figure follows."""
        _set_pref(STAY_PREF, bool(on))
        runner = self.runner
        if runner is not None and hasattr(runner, "set_stay"):
            runner.set_stay(bool(on))
        return True

    def snooze(self) -> bool:
        """"Hide for 10 minutes": the figure goes now and comes back by itself, as long as it is
        still turned on and the app window is still away. The clock is the injected one."""
        self.snooze_until = self._now() + SNOOZE_MINUTES * 60
        timer = _SnoozeTimer(SNOOZE_MINUTES * 60 + 1, lambda: self._dispatch("desk-companion", self.sync))
        with _lock:
            old, self._snooze_timer = self._snooze_timer, timer
        if old is not None:
            old.cancel()
        timer.start()
        self._dispatch("desk-companion", self.sync)
        return True

    def carry_reminder(self, token: Any) -> bool:
        """A reminder fell due: the figure fetches it as a card, when the overlay is
        showing (the card window has no such thing, and a hidden figure has no one
        to show it to; the system notification still comes). False when not."""
        runner = self.runner
        if runner is None or not self.shown or not hasattr(runner, "bring_card"):
            return False
        runner.bring_card(token)
        return True

    def _overlay_card(self, token: Any) -> None:
        """The card was clicked (on a worker): the reminder opens in the app, as a
        click on its notification does."""
        logger.info("desk companion: a reminder's card was clicked")
        self.open_main(REMINDERS_SCRIPT)

    def let_it_walk(self) -> bool:
        """The menu's "Let it walk": the app's Companion movement set to Always
        (through its own window), and the figure restarted moving."""
        walked = self._ask_main(WALK_SCRIPT, "the walk setting") is True
        return self._restart_shown("let it walk", walk_forced=not walked)

    def _restart_shown(self, what: str, walk_forced: bool | None = None) -> bool:
        """The runner restarted for whatever the app window now says (look, motion), where
        it stood, and shown again when it was; a failed start falls back to the card."""
        if not _lock.acquire(timeout=LOCK_WAIT):
            logger.warning("desk companion: busy, %s was skipped", what)
            return False
        try:
            if walk_forced is not None:
                self._walk_forced = walk_forced
            if self.closing or self.runner is None:
                return False
            before = self.runner
            if not self._start_overlay():
                self.shown = False
                self._sync_card(enabled() and self.main_hidden)
                return False
            if self.runner is not before and self.shown:
                self.runner.show()
            logger.info("desk companion: %s, restarted", what)
            return True
        except Exception:  # noqa: BLE001 - the figure stays as it was
            logger.warning("desk companion: %s failed", what, exc_info=True)
            return False
        finally:
            _lock.release()

    def companion_choices(self) -> dict[str, Any]:
        """The right-click "Companion" panel: `{"locked": bool, "options": [...]}`. Nothing
        is listed while the app is locked or does not answer."""
        answer = self._ask_main(COMPANION_SCRIPT, "the companion choices")
        try:
            data = json.loads(answer) if isinstance(answer, str) and answer.startswith("{") else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            self._choice_names = {}
            return {"locked": False, "options": []}
        if data.get("locked") is True:
            self._choice_names = {}
            return {"locked": True, "options": []}
        options = companion_options(data)
        self._choice_names = {o["key"]: o["label"] for o in options if o["key"].startswith("preset:")}
        reply: dict[str, Any] = {"locked": False, "options": options}
        if note := self.frames_note():
            reply["note"] = note
        return reply

    def choose_companion(self, key: str) -> str:
        """A choice from that panel, written to the app's own prefs through its window (as
        `let_it_walk` writes its setting), then the figure restarts with the new look.
        "ok", "locked" (refused while the app is locked), "gone" (a saved companion that is
        no longer there), "unknown" or "error"."""
        if not _CHOICE_KEY.fullmatch(key):
            return "unknown"
        if key.startswith("atlas:"):
            script = COMPANION_ATLAS % json.dumps(key.split(":", 1)[1])
        elif key in ("me", "persona", "custom"):
            script = COMPANION_KIND % json.dumps(key)
        else:
            name = self._choice_names.get(key)
            if name is None:
                return "gone"
            script = COMPANION_PRESET % (int(key.split(":", 1)[1]), json.dumps(name))
        answer = self._ask_main(script, "the companion choice")
        if answer != "ok":
            logger.info("desk companion: the companion choice was not applied (%s)", answer)
            return answer if answer in ("locked", "gone") else "error"
        return "ok" if self._restart_shown("companion choice") else "error"

    def _stop_runner(self, died: bool = False) -> None:
        """The runner stopped. Only a death is remembered for the next start: a clean stop (off, a restart, closing)
        leaves nothing to replay. A death before the engine was ready keeps the last good place."""
        if died and self.runner is not None:
            place, carried = self._runner_place(), self._runner_carry()
            if place is not None:
                self._last_place, self._last_carry, self._last_at = place, carried, self._now()
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
            self._make_panel()
            return True
        if self.runner is not None and self.shown:
            self.runner.hide()
            self._hide_panel_window()
            self.shown = False
            logger.info("desk companion: overlay hidden")
        return self.runner is not None

    def _make_panel(self) -> None:
        """The quick panel's window, made once and kept hidden, so a click only
        places and shows it (INBOX 1658: it was made at click time and the figure
        lagged). A failure leaves it to the first click."""
        if self.window is not None or self.closing:
            return
        try:
            self.panel = True
            self.size = self.panel_size("menu")
            self.window = self._unless_closing(self._make())
            if self.window is None:
                return
            logger.info("desk companion: quick panel made hidden")
        except Exception:  # noqa: BLE001 - the first click tries again
            logger.warning("desk companion: the quick panel could not be made ahead", exc_info=True)
            self.panel = False
            self.window = None

    def _unless_closing(self, window: Any) -> Any:
        """A window just made, or None (and it destroyed) when a quit began while it was being made:
        `close` gave up waiting for the lock and took no window, so nothing else would end it (1666 review)."""
        if not self.closing:
            return window
        logger.info("desk companion: a window made as the app quit is closed again")
        try:
            window.destroy()
        except Exception:  # noqa: BLE001 - quitting goes on
            logger.debug("could not destroy the companion window", exc_info=True)
        return None

    def _hide_panel_window(self) -> None:
        if self.window is not None and self.panel_shown:
            window = self.window

            def clear() -> None:
                try:
                    # The page clears its menu, so the next open does not show the last one.
                    window.evaluate_js("window.dispatchEvent(new CustomEvent('desk-close'))")
                except Exception:  # noqa: BLE001 - hiding matters more than tidying
                    logger.debug("desk companion: the quick panel page did not clear", exc_info=True)

            # On a worker: callers hold _lock, and a stuck page must not hold it.
            jobs.thread("desk-panel-clear", clear)
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

    def _overlay_place(self, x: int, y: int) -> None:
        """A trip arrived where the figure lives now (on a worker): saved, so the next start is there, not at the last drop."""
        _set_pref(OVERLAY_POS_PREF, [int(x), int(y)])

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
            ask, spr = getattr(self.runner, "dpi_at", None), getattr(self.runner, "sprites", None)
            drawn = getattr(self.runner, "drawn_rect", None)
            if callable(ask) and spr is not None:  # dropped on a monitor of another scale
                landed = ask(int(x) + width // 2, int(y) + height // 2)
                if landed and landed != dpi:
                    (width, height), dpi = spr.size(landed), int(landed)
            if callable(drawn) and spr is not None:  # the figure's drawn box, not the window around it (INBOX 1663)
                _bx, _by, width, height = box = drawn(int(x), int(y), dpi=dpi)
            else:
                box = (int(x), int(y), width, height)
            self._pet_phys = (width, height, dpi)
            self._pet_box = box
            self.pet_rect = to_logical(box, dpi)
            area = _screen_area(self.webview, (self.pet_rect[0], self.pet_rect[1] + self.pet_rect[3]))
            self.corner = panel_corner(self.pet_rect, self.size, area)
            self._update_panel_box()
            self._place()
        except Exception:  # noqa: BLE001 - the panel stays where it was
            logger.warning("desk companion: the quick panel did not follow the figure", exc_info=True)
        finally:
            _lock.release()

    def _drop_panel(self) -> None:
        """The card window takes over (lock held): the overlay's quick panel, if one was made, is destroyed,
        so `_sync_card` makes a real card. Kept, the hidden panel (the overlay's page, menu sized, taking
        focus) was shown as the card and hid again every few seconds (INBOX 1690 d)."""
        window = self.window if self.panel else None
        if self.panel:
            self.window = None
        self.panel = self.panel_shown = self.shown = False
        self.corner = None
        self.size = REST_SIZE
        if window is not None:
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                logger.debug("could not destroy the quick panel", exc_info=True)

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
            self._stop_runner(died=True)
            self.overlay_failed = True
            self.overlay_tries += 1
            self._overlay_retry_at = self._now() + OVERLAY_RETRY_GAP
            self.overlay_why = "its window ended on its own"
            self._drop_panel()
            self._sync_card(enabled() and self.main_hidden)
        except Exception:  # noqa: BLE001 - never takes the app with it
            logger.warning("desk companion: the card window did not come back", exc_info=True)
        finally:
            _lock.release()

    def _watch_click_away(self) -> None:
        """Windows: close the shown panel on a press outside it, focus or not (`press_outside`)."""
        if sys.platform != "win32" or getattr(self, "_away_watch", None) is not None:
            return
        handle = window_handle(self.window)
        if handle is None:
            return
        import ctypes

        user32 = ctypes.windll.user32
        self._away_watch = jobs.thread("desk-click-away", lambda: self._click_away_loop(user32, handle))

    def _click_away_loop(self, user32: Any, handle: int) -> None:
        down = mouse_down(user32)
        try:
            while self.panel_shown and not self.closing:
                time.sleep(CLICK_AWAY_POLL)
                away, down = press_outside(user32, handle, down)
                if away:
                    self.panel_blur()
                    break
        except Exception:  # noqa: BLE001 - the focus path still closes it
            logger.debug("desk companion: the click-away watch stopped", exc_info=True)
        finally:
            self._away_watch = None

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
            self._pet_box = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
            self._pending_kind = "context" if kind == "right" else "menu"
            area = _screen_area(self.webview, (self.pet_rect[0], self.pet_rect[1] + self.pet_rect[3]))
            self.panel = True
            self._panel_state = self._pending_kind
            self.size = self.panel_size(self._pending_kind)
            self.corner = panel_corner(self.pet_rect, self.size, area)
            self._update_panel_box()
            if self.window is None:
                self.window = self._unless_closing(self._make())
                if self.window is None:
                    return
                logger.info("desk companion: quick panel made beside the figure at %s", self.top_left())
            # The one placement of the click, before the window is shown; nothing
            # resizes or moves it after (the page's own height report is only kept).
            self._place()
            self.window.show()
            self.panel_shown = True
            self.window.evaluate_js(
                "window.dispatchEvent(new CustomEvent('desk-open',{detail:%s}))" % json.dumps("context" if kind == "right" else "menu")
            )
            self._watch_click_away()
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
            due = on and self.main_hidden and not self.closing and self._now() >= self.snooze_until
            #: One line a step (INBOX 1633: the owner could not see it; the log says where it stopped).
            logger.info("desk companion: due=%s (on=%s, window away=%s, shown=%s)", due, enabled(), self.main_hidden, self.shown)
            try:
                self._retry_overlay(due)
                if not self._sync_overlay(due):
                    self._sync_card(due)
            except Exception:  # noqa: BLE001 - a companion that fails never takes the app with it
                logger.warning("the desktop companion window failed", exc_info=True)
        finally:
            _lock.release()

    def _retry_overlay(self, due: bool) -> None:
        """After the see-through figure failed (lock held): the card is put away and the figure tried once more,
        `OVERLAY_TRIES` times in all, when the app window is in front again or, in a due sync, `OVERLAY_RETRY_GAP`
        seconds on (a start that was only slow must not leave the card up for good)."""
        if not self.overlay_failed or self.overlay_tries >= OVERLAY_TRIES or self._overlay_factory is None or self.closing:
            return
        if due and self._now() < self._overlay_retry_at:
            return
        window, self.window = self.window, None
        self.shown = self.panel_shown = self.panel = False
        if window is not None:
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                logger.debug("could not destroy the card window", exc_info=True)
        self.overlay_failed = False
        logger.info("desk companion: the overlay will be tried again at the next minimise (%s)", self.overlay_why)

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

    def set_main_hidden(self, hidden: bool, source: str = "") -> None:
        now = self._now()
        if hidden != self.main_hidden:
            #: Which event flipped it and how long it held (the owner's 2026-11-10 log: the figure shown and hidden four times in
            #: 16 s, "due=True" then "due=False (window away=False)" every 3 to 4 s; a flip back within a second or two is a
            #: window event that fires twice, a steady 3 to 4 s is something else that raises and lowers the window).
            held = now - self._away_at if self._away_at is not None else None
            logger.info(
                "desk companion: the app window is %s (%s)%s", "away" if hidden else "back", source or "unnamed",
                f", {held:.1f} s after the last change" if held is not None else "",
            )
            self._away_at = now
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
        if self.panel and self.panel_box is not None and place_physical(self.window, self.panel_box[0]):
            return
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
            timer, self._snooze_timer = self._snooze_timer, None
            window, self.window = self.window, None
            self.shown = False
        finally:
            if got:
                _lock.release()
        if timer is not None:
            timer.cancel()
        self._stop_runner()
        if window is not None:
            _await_loaded(window)
            try:
                window.destroy()
            except Exception:  # noqa: BLE001
                logger.debug("could not destroy the companion window", exc_info=True)


def overlay_support() -> tuple[bool, str]:
    """(usable, one-line note) for the see-through figure here: Windows always; Linux on an X11
    session (Wayland cannot place a window above others, so the companion stays in the app and
    the note says so); every other platform keeps the card window."""
    if sys.platform == "win32":
        return True, ""
    if sys.platform.startswith("linux"):
        from tessellate.core.overlay import x11

        return x11.support()
    return False, ""


#: Why the see-through figure is not used on this machine (empty when it is, or when nothing needs saying).
OVERLAY_NOTE = ""


def _default_overlay_factory() -> Callable[..., Any] | None:
    """The see-through figure is the default on Windows and on an X11 desktop; elsewhere the
    card window (or the see-through web window) stays, with a note on Linux saying why."""
    global OVERLAY_NOTE
    ok, note = overlay_support()
    OVERLAY_NOTE = note
    if not ok:
        if note:
            logger.info("desk companion: %s", note)
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
    factory = _default_overlay_factory() if overlay_factory == "auto" else overlay_factory
    companion = DeskCompanion(
        webview,
        main_window,
        open_main,
        url,
        #: The see-through figure draws itself, so its quick panel is an ordinary window;
        #: without it (Wayland, other platforms) the card window is the see-through one.
        transparent=(sys.platform != "win32" and factory is None) if transparent is None else transparent,
        overlay_factory=factory,
    )
    companion.on_change = on_change
    companion.overlay_note = OVERLAY_NOTE if overlay_factory == "auto" else ""
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
        companion.set_main_hidden(False, "show")
        return result

    def hidden(*args: Any, **kwargs: Any) -> Any:
        result = hide(*args, **kwargs)
        companion.set_main_hidden(True, "hide")
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

        def follow(*_args: Any, _away: bool = away, _name: str = name) -> None:
            companion.set_main_hidden(_away, "event " + _name)

        try:
            event += follow
            followed.append(name)
        except TypeError:
            logger.debug("desk companion: the window has no %s event to follow", name)
    return followed


def carry_due(due: list[Any]) -> int:
    """Reminders that just fell due (`reminder_notifier.Due`): the active companion's
    overlay fetches a card for each, by reminder id. How many it took; 0 with no
    companion, or none showing. Never raises: the notifier calls it."""
    with _lock:
        companion = _active
    if companion is None:
        return 0
    taken = 0
    for item in due:
        token = getattr(item, "reminder_id", None)
        if token is None:
            continue
        try:
            if companion.carry_reminder(token):
                taken += 1
        except Exception:  # noqa: BLE001 - a card is not worth the notifier's thread
            logger.warning("desk companion: a reminder's card could not be queued", exc_info=True)
    return taken


def _await_loaded(window: Any) -> None:
    """Give a window that is still starting its web view a short deadline to finish, so quitting
    never aborts the start (INBOX 1666). Quiet when the backend has no `loaded` event."""
    loaded = getattr(getattr(window, "events", None), "loaded", None)
    wait = getattr(loaded, "wait", None)
    #: On the GUI thread (the close X quitting) the start waits on this very thread's loop, so a wait
    #: there only froze the closing window and the start aborted anyway (1666 review).
    if not callable(wait) or threading.current_thread() is threading.main_thread():
        return
    try:
        if not wait(LOADED_WAIT):
            logger.info("desk companion: a window was still starting at quit; closing it anyway")
    except Exception:  # noqa: BLE001 - quitting goes on
        logger.debug("desk companion: could not wait for the window to load", exc_info=True)


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
