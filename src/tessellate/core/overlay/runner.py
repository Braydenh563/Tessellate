"""Window, behaviour and frames, joined (BACKLOG 16, O4).

`OverlayRunner` owns one `OverlayHost`, one `Engine` and one `SpriteSet`. Every
call into the engine happens on the overlay's own thread (the host's event
callback), so the engine needs no lock; other threads only call `show`, `hide`
and `stop`, which queue work for that thread.

A click on the figure is handed to `on_click(kind, rect, dpi)` on a worker
(`jobs.thread`), never on the overlay thread: the quick panel is a web window
and its creation waits on the UI thread. `on_settle(x, y)` says where a drop
landed (the place worth saving).

**Roam and carry** (owner, 2026-11-04). While it is shown and free to move the
runner reads the top edges of the other windows (`win32.windows`, then
`perches.top_edges`) at most once a second, on the overlay thread in its own step
before the engine's (the thread whose DPI awareness makes the coordinates
physical; never in the draw path), and hands them to the engine. It reads only
when a climb could happen soon or the figure is on a window (`_wants_scan`):
a figure that is sitting, asleep, typing-quiet, still, or switched off reads
nothing. `bring_card(token)` (any thread) queues a reminder for the engine; a
click on the card comes back as `on_card(token)` on a worker.

Fullscreen and "do not disturb" (`SHQueryUserNotificationState`: a
fullscreen Direct3D game, a presentation) hide the window and stop it moving;
asked every 2 s while it runs, and while it is hidden for that.

Not run on Windows (the sandbox has none): the tests drive a fake `win32`.
"""

from __future__ import annotations

import inspect
import logging
import math
import os
import random
import sys
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any, Callable

from tessellate.core import companion_events, jobs
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import host as host_mod
from tessellate.core.overlay import pacing
from tessellate.core.overlay import faces
from tessellate.core.overlay import perches
from tessellate.core.overlay import props
from tessellate.core.overlay import screenwatch
from tessellate.core.overlay import sizing
from tessellate.core.overlay import sprites
from tessellate.core.overlay import win32

logger = logging.getLogger(__name__)

#: How often to ask whether something fullscreen is in the way (seconds).
#: A pose change dissolves over this long, in this many steps (one a display frame at 60 Hz), among these
#: picture families (INBOX 1670, 14:14Z: "framey and not seamless").
BLEND_S = 0.12
#: A look is a head turn (INBOX 1670, 16:40Z: it snapped): its dissolve, in and out, is slower than a pose change's.
BLEND_LOOK_S = 0.24
BLEND_STEPS = 7
BLEND_TICK_MS = 16
BLENDED = ("stand", "walk", "idle", "look", "sit", "sleep", "wave", "land", "hang", "hang_one", "hang_sloth", "hang_feet", "dangle", "kick", "meditate", "lean", "back_float")
BUSY_EVERY = 2.0
#: A flight or a fall holds the periodic reads back this long at most (s): longer than any throw is in the air, so it is a
#: bound, not a pace (`OverlayRunner._aloft`).
AIR_DEFER = 8.0
#: A tick of the overlay thread longer than this (ms) is logged with the reads that ran in it and the state, at most once per
#: `SLOW_TICK_EVERY` s: the next log from Windows says which read, if any, stops a fall (INBOX 1696 a; the frame cost of the
#: layered-window draw itself is `draw` in the same line).
SLOW_TICK_MS = 30.0
SLOW_TICK_EVERY = 5.0
#: Input this recent means the person is typing or working: no acts, only standing.
TYPING_AGE = 2.5
#: A welcome back not yet answered (the figure busy or mid-reaction) is tried again for this long (s).
RETURN_FOR = 10.0
#: A screen event nobody could answer yet (the figure walking, hanging, typed over, mid-reaction) is held this long (s) and played at the
#: next free moment, then dropped with a log line (INBOX 1700: it was thrown away the tick it came).
SCREEN_WAIT = 10.0
#: How long a foreground window's text band is trusted before it is read again.
ZONE_EVERY = 30.0
#: The window scan is at most this often (seconds); it starts this long before a
#: climb is due, so the first read is in hand when it is.
SCAN_EVERY = 1.0
#: Pictures with a face or a prop kept built (a prop act cycles a few phases for a minute).
DECOR_KEEP = 48
SCAN_RIDING = 0.25
#: A tool that hides the taskbar window sends no message, so the work area is read again this often (seconds).
TASKBAR_EVERY = 5.0
SCAN_SLACK = 1.0
#: Room past the figure's width a top edge needs to be stood on (logical px, at 96 dpi).
PERCH_ROOM = 20


def timed(owner: Any, name: str, call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """`call(...)`, its milliseconds kept on the runner for the tick's slow-tick line (`OverlayRunner._note_tick`); an owner
    with no tick under way (a test's stand-in, a read made between ticks) keeps nothing."""
    perf, reads = getattr(owner, "_perf", None), getattr(owner, "_tick_reads", None)
    if perf is None or reads is None:
        return call(*args, **kwargs)
    began = perf()
    try:
        return call(*args, **kwargs)
    finally:
        reads.append((name, (perf() - began) * 1000.0))


def default_backend(w: Any = None) -> Any:
    """Windows' calls on Windows, X11's everywhere else; a handed-in connection says which it is
    (the Windows fakes carry `user32`)."""
    if (w is not None and hasattr(w, "user32")) or (w is None and sys.platform == "win32"):
        return win32
    from tessellate.core.overlay import x11

    return x11


def read_layout(k: Any, w: Any) -> list[eng.Monitor]:
    """Every monitor as the engine plays on it. A backend that knows the screen's bars (`monitors_full`: win32) gives
    the whole monitor and what lies along its edges; one that does not (x11) gives the play area and dpi."""
    full = getattr(k, "monitors_full", None)
    if full is None:
        return [eng.Monitor(area, dpi) for area, dpi in k.monitors(w)]
    return [eng.Monitor(m.area, m.dpi, m.screen, tuple(eng.Bar(b.edge, b.rect, b.shown) for b in m.bars)) for m in full(w)]


class OverlayRunner:
    def __init__(
        self,
        *,
        look: str = "masculine",
        reduced: bool | None = None,
        reduced_reason: str = "",
        home: tuple[int, int] | None = None,
        on_click: Callable[[str, tuple[int, int, int, int], int], Any] | None = None,
        on_settle: Callable[[int, int], Any] | None = None,
        on_died: Callable[[], Any] | None = None,
        on_card: Callable[[Any], Any] | None = None,
        on_size: Callable[[float], Any] | None = None,
        scale: float = 1.0,
        roam_windows: bool = True,
        stay: bool = False,
        backend: Any = None,
        w: Any = None,
        clock: Callable[[], float] = time.monotonic,
        frames: Path | None = None,
        dispatch: Callable[[str, Callable[[], None]], Any] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        #: The engine's chance; a test passes a seeded one (an unseeded one made react_1700 fail a different test a CI job).
        self.rng = rng
        #: The platform's half (`win32` or `x11`): its connection, window, monitors and window list.
        self.k = backend or default_backend(w)
        self.look = sprites.look_for(look)
        #: True or False is the app's answer (Appearance > Companion movement);
        #: None means it gave none, and the Windows animation flag decides in `_ready`.
        self.reduced = reduced
        self.reduced_reason = reduced_reason
        self.home = home
        self.on_click = on_click
        self.on_settle = on_settle
        self.on_died = on_died
        self.on_card = on_card
        #: The size handle: the figure's size as a multiplier on the monitor's dpi (Appearance > Companion size, 0.7 to 1.6),
        #: where it is eased to, the presses on the handle, how long it shows, and how many times the window was resized.
        self.on_size = on_size
        #: A trip arrived where it lives now (`Engine.home_arrivals`): passed on so the place is saved, as a drop is.
        self.on_place: Callable[[int, int], Any] | None = None
        self._arrivals_seen = 0
        #: Drops handed on so far: an arrival's save is skipped once a drop came after it.
        self._drops = 0
        #: The last runner's `Engine.carry`, set by the coordinator before `start` on a restart: taken up in `_ready`.
        self.carried: dict[str, Any] | None = None
        self.enter = False  # set by the coordinator for the first show of a session
        self.entrance = ""  # the first show's arrival, for the log and the tests
        self.scale = sizing.clamp(scale)
        self._goal: float | None = None
        self._sizing: dict[str, Any] | None = None
        #: The resize cursor for the handle as last drawn, and the one the host was last told (0: the arrow).
        self._hit_cursor, self._cursor_now = win32.IDC_SIZENESW, 0
        #: The size just pulled and until when: a sync from the page, which has not got it yet, must not undo it.
        self._pending: tuple[float, float] | None = None
        #: A press the engine took (a drag of the figure): the handle is for a hover, not for what follows one.
        self._engine_press = False
        #: The frame name and mirror last drawn; unlike `_last_key` it is never cleared, so a press right after a
        #: resize still knows whether the figure stands or hangs.
        self._shown: tuple[str, bool] = ("stand", False)
        self._last_press: tuple[float, int, int, bool] | None = None
        self._hover_until = -math.inf
        self._hit: tuple[int, int, int, int] | None = None
        self.resizes = 0
        self.roam_windows = roam_windows
        self.stay = stay
        self.w = w
        self.clock = clock
        #: The gap between the moving figure's wakes, as one line a minute (`pacing.IntervalLog`).
        self._intervals = pacing.IntervalLog()
        self.clock_hour: int | None = None
        self.frames = frames
        self._dispatch = dispatch or jobs.thread
        self.host: host_mod.OverlayHost | None = None
        self.engine: eng.Engine | None = None
        self.sprites: sprites.SpriteSet | None = None
        self.monitors: list[eng.Monitor] = []
        self.dpi = 96
        self.visible = False
        self.busy = False
        self.paused = False
        #: Where the pointer was at the last busy check and when it last moved:
        #: GetLastInputInfo counts mouse moves too, and a person using the mouse
        #: is not typing (INBOX 1670: "it doesnt move" while the mouse was in use).
        self._busy_ptr: tuple[int, int] | None = None
        self._ptr_moved_at = -math.inf
        self._return_until = -math.inf
        self._return_kind = "idle_return"
        self._stopped = False
        self._resume = False
        self._last_key: tuple | None = None
        self._last_pos: tuple[int, int] | None = None
        #: The frame last asked for, the dissolve from the one before (frame, started at), and which step it drew.
        self._target: sprites.Frame | None = None
        self._blend: tuple[sprites.Frame | None, float] | None = None
        self._blend_step = -1
        self._blend_s = BLEND_S
        self._next_busy_check = 0.0
        self._air_since: float | None = None  # when the flight or fall in progress began (`_aloft`)
        self._perf: Callable[[], float] = time.perf_counter
        self._tick_reads: list[tuple[str, float]] = []  # (what, ms) of each timed read in the tick under way
        self._slow_logged = -1e9
        #: The foreground window's text band, kept per window: (hwnd, read at, band).
        self._zone: tuple[int, float, tuple[int, int, int, int] | None] | None = None
        self._next_scan = 0.0
        self._next_taskbar = 0.0
        self._bars_key: list | None = None
        self.lively = "usual"
        self._cards: deque[Any] = deque()
        self._commands: deque[str] = deque()
        #: The result of the last menu request the engine took, for the tests and the log.
        self.last_command: tuple[str, bool] | None = None
        self._scan_failed = False
        self._last_scan_line = ""
        self._last_skip_line = ""
        #: Screen events the figure answers (a window opening, the app changing, the hour, the battery, a download).
        self._watch = screenwatch.ScreenWatch(
            foreground=(lambda: self.k.foreground(self.w)) if hasattr(self.k, "foreground") else None,
            battery=(lambda: self.k.battery(self.w)) if hasattr(self.k, "battery") else None,
            run=lambda fn: jobs.thread("overlay-downloads", fn),
            feed=companion_events.since,  # the notebook's own events, on this same poll (W31)
        )
        #: kind -> when it is given up: the screen events waiting for a free moment; the last window rects read, by key; when
        #: the window list was last read for events (the climb scan or `_window_events`).
        self._events: dict[str, float] = {}
        self._rects: dict[int, tuple[int, int, int, int]] = {}
        self._events_read = -1e9
        self._decor: dict[tuple, sprites.Frame] = {}
        self._warmed = 0  # the size the quarter turn was last built for (INBOX 1696 a)
        try:  # a backend that can count why windows were left out (win32); a fake may not
            self._tallies = "tally" in inspect.signature(self.k.windows).parameters
            self._nears = "near" in inspect.signature(self.k.windows).parameters
        except (TypeError, ValueError):
            self._tallies = self._nears = False

    # --- life (any thread) ------------------------------------------------------------

    def start(self, timeout: float = 10.0) -> bool:
        """Make the window and the engine. False (and logged) when either fails:
        the coordinator then falls back to the card window."""
        try:
            if self.w is None:
                self.w = self.k.load()
            self.host = getattr(self.k, "Host", host_mod.OverlayHost)(self.w, on_event=self._on_event, on_exit=self._exited)
            ok = self.host.start(timeout)
        except Exception:  # noqa: BLE001 - any failure means the card window instead
            logger.warning("overlay: could not start", exc_info=True)
            return False
        if not ok:
            self.stop()
        return ok

    def _exited(self) -> None:
        """The overlay thread ended without a `stop` (no polling: the thread says so)."""
        if self._stopped:
            return
        self.visible = False
        logger.warning("overlay: the window thread ended on its own")
        self._hand_off("overlay-died", lambda: self.on_died and self.on_died())

    def show(self) -> None:
        self.visible = True
        self._resume = True
        if self.host:
            self.host.show()
            self.host.wake(1)

    def bring_card(self, token: Any) -> None:
        """A reminder fell due (any thread): the figure fetches it on its next tick."""
        self._cards.append(token)
        if self.host:
            self.host.wake(1)

    def command(self, name: str) -> bool:
        """A choice from the companion's menu (any thread): the engine acts on it on its next
        tick, on its own thread. False for a name the engine does not know."""
        if name not in eng.Engine.COMMANDS:
            return False
        self._commands.append(name)
        if self.host:
            self.host.wake(1)
        return True

    def set_stay(self, on: bool) -> None:
        """"Stay here" (any thread): the engine stops wandering until told to roam."""
        self.stay = bool(on)
        self.command("stay" if on else "roam")

    def set_scale(self, scale: float) -> None:
        """Appearance changed the size (any thread): eased to it on the next ticks. Not while the handle is pulled,
        and not back to the old value while a pull's write-back is still on its way to the page."""
        if self._sizing is not None:
            return
        goal = sizing.clamp(scale)
        pending = self._pending
        if pending is not None:
            if self.clock() < pending[1] and goal != pending[0]:
                return
            self._pending = None
        if goal != self.scale:
            self._goal = goal
            if self.host:
                self.host.wake(1)

    def _fdpi(self) -> int:
        """The dpi the pictures are drawn at: the monitor's, times the size the person chose."""
        return max(24, round(self.dpi * self.scale))

    def set_lively(self, name: str) -> None:
        """The menu's Activity (any thread): read by the engine on the next tick."""
        self.lively = name if name in eng.LIVELY else "usual"
        if self.host:
            self.host.wake(1)

    def set_roam(self, on: bool) -> None:
        """The "Roam over windows" switch: takes effect on the next tick."""
        self.roam_windows = bool(on)
        if self.host:
            self.host.wake(1)

    def dpi_at(self, x: int, y: int) -> int:
        """The dpi of the monitor under a physical point (MonitorFromPoint, then
        GetDpiForMonitor); the monitor list's, then 96, when Windows cannot say."""
        found = self.k.dpi_at_point(self.w, x, y) if self.w is not None else None
        if found:
            return found
        for area, dpi in ((m.area, m.dpi) for m in list(self.monitors)):
            if area[0] <= x < area[2] and area[1] <= y < area[3]:
                return dpi
        return 96

    def hide(self) -> None:
        self.visible = False
        if self.host:
            self.host.hide()

    def stop(self) -> None:
        self._stopped = True
        if self.host:
            self.host.stop()
        self.host = None
        self.visible = False

    # --- the overlay's thread --------------------------------------------------------------

    def _on_event(self, kind: str, x: int, y: int) -> int | None:
        if kind == "tick":
            self._note_interval(self.clock())
        ask = self._on_event_inner(kind, x, y)
        self._intervals.asked(ask)
        return ask

    def _on_event_inner(self, kind: str, x: int, y: int) -> int | None:
        if kind == "ready":
            self._ready()
            return None
        if self.engine is None or self.paused and kind != "resume":
            return None
        now = self.clock()
        if kind in ("down", "move", "up", "right"):
            if self._handle_event(kind, x, y, now):
                if self._sizing is not None:  # a pull holds the figure still, whatever it was doing
                    return self._apply(self.engine.hold())
                return self._apply(self.engine.update(now, (x, y)))
            if kind == "up" and self.engine.carrying:
                self._scan_at_release(x, y, now)
            out = self.engine.update(now, (x, y), (kind, x, y))
            self._log_notes()
            return self._apply(out)
        if kind != "tick":
            return self._system(kind, now, (x, y))
        began, self._tick_reads = self._perf(), []
        wake = self._system(kind, now, (x, y))
        self._note_tick((self._perf() - began) * 1000.0, now)
        return wake

    def _note_tick(self, ms: float, now: float) -> None:
        engine = self.engine
        if ms < SLOW_TICK_MS or engine is None or now - self._slow_logged < SLOW_TICK_EVERY:
            return
        self._slow_logged = now
        reads = ", ".join(f"{name} {took:.0f} ms" for name, took in self._tick_reads if took >= 1.0) or "none"
        logger.info("overlay: a slow tick, %.0f ms in state %s (timed reads: %s; the rest is the engine and the draw)", ms, engine.state, reads)

    def _system(self, kind: str, now: float, pointer: tuple[int, int]) -> int | None:
        engine = self.engine
        assert engine is not None
        if kind == "suspend":
            if self._sizing is not None:
                self._end_pull(now)
            self.paused = True
            return None
        if kind == "resume":
            self.paused = False
            self._resume_engine(engine, now)
            return 1
        if kind in ("display", "taskbar"):  # the shell rebuilt the taskbar: its edge or size may have changed
            self._refresh_monitors()
        if kind == "tick":
            if not self.visible:
                return None
            if self._sizing is not None:
                if now - self._sizing["last"] < sizing.PULL_IDLE_S:
                    return self._apply(engine.hold())
                self._end_pull(now)  # the release never came: a lost grab, a lock screen
            if self._resume:
                self._resume = False
                self._resume_engine(engine, now)
            aloft = self._aloft(engine, now)
            hold = None if aloft else self._busy_gate(now, pointer)
            if hold is not None:
                return hold
            while self._cards:
                engine.bring_card(self._cards.popleft(), now)
            self._run_commands(engine, now)
            if not aloft:  # the periodic reads wait for the landing (INBOX 1696 a)
                self._scan(now)
                self._screen_events(now)
        if kind not in ("tick", "display", "taskbar"):
            return None
        return self._apply(engine.update(now, pointer))

    def _aloft(self, engine: eng.Engine, now: float) -> bool:
        """In a fall or a throw's flight, for at most `AIR_DEFER` s: the window list (EnumWindows and a query on each of the
        ~590 windows of the owner's desktop), the foreground, the downloads folder, the layout and the typing reads all land
        on this thread between two frames, so a flight caught one of each every 2 s (measured 3 reads in a 3.2 s flight, in
        40 of 40 phases of the timers): a tick of its own, which is a stop in the downward arc (INBOX 1696 a). They are
        read on the first tick on the ground instead; none is urgent to a quarter of a second."""
        if engine.state not in ("fly", "fall"):
            if self._air_since is not None:  # landed: the held-back reads come one tick each, not all on the landing's
                self._air_since = None
                self._watch.next_at = max(self._watch.next_at, now + 0.25)
                self._events_read = max(self._events_read, now - screenwatch.EVERY + 0.5)
            return False
        if self._air_since is None:
            self._air_since = now
        return now - self._air_since < AIR_DEFER

    def _note_interval(self, now: float) -> None:
        line = self._intervals.note(now)
        if line:
            logger.info(line)

    def _run_commands(self, engine: eng.Engine, now: float) -> None:
        """The menu's requests, in order. "Sit on a window" reads the window list first, since
        the usual scan is only wanted when a climb is near."""
        while self._commands:
            name = self._commands.popleft()
            if name == "perch":
                self._scan(now, force=True)
            self.last_command = (name, engine.command(name, now))
            logger.info("overlay: menu request %s, done=%s", *self.last_command)

    # --- other windows' tops ------------------------------------------------------------

    def _wants_scan(self, now: float) -> bool:
        """Only when a climb could come soon or the figure stands on a window."""
        e = self.engine
        if e is None or not self.roam_windows or e.reduced or not e.roam:
            return False
        if e.tuck is not None or e.hang_on is not None:
            return True  # hidden behind a window or hanging from one: it moving or closing is read within a quarter of a second (INBOX 1699)
        if e.quiet:
            return False
        if e.perch is not None or e.target is not None or e.state in ("pressed", "held"):
            return True  # carried: a title bar under it may be taken hold of
        # A window is climbed to by a trip or by the climb act, so the list is wanted before either is due.
        return e.state in ("stand", "walk", "drift", "act", "crouch") and now >= min(e.trip_ready, e.climb_ready, e.big_ready) - SCAN_SLACK

    def _list_windows(self, tally: Counter, near: tuple[int, int, int] | None = None, seen: list | None = None) -> list:
        """The window list, or [] when it cannot be read (no list means no roaming, never a crash)."""
        extra: dict[str, Any] = {"tally": tally} if self._tallies else {}
        if near is not None and self._nears:
            extra.update(near=near, seen=seen)
        try:
            return timed(self, "windows", self.k.windows, self.w, os.getpid(), self.host.hwnd if self.host else None, [m.area for m in self.monitors], **extra)
        except Exception:  # noqa: BLE001
            if not self._scan_failed:
                logger.warning("overlay: the windows could not be listed", exc_info=True)
            self._scan_failed = True
            return []

    def _watch_taskbar(self, now: float) -> None:
        """Read the work areas again now and then: a hider tool changes the floor without a message (research T1)."""
        if now < self._next_taskbar:
            return
        self._next_taskbar = now + TASKBAR_EVERY
        try:
            read = timed(self, "layout", read_layout, self.k, self.w)
        except OSError:
            return
        # The play areas move the figure's floor; the bars (shown or not, which edge) move where it can tuck (INBOX 1683 y).
        key = [(m.screen, m.bars) for m in read]
        before = getattr(self, "_bars_key", None)
        self._bars_key = key
        if read and ([m.area for m in read] != [m.area for m in self.monitors] or (before is not None and key != before)):
            self._refresh_monitors()

    def _scan_at_release(self, x: int, y: int, now: float) -> None:
        """A carried figure let go: the windows read now, not up to a second ago (INBOX 1696 b: "I tried to drag the
        desktop companion onto the top of my file explorer window but it just fell"), and one INFO line for each
        window whose top is near the feet saying what it counted as (its class, never its title)."""
        engine = self.engine
        assert engine is not None
        if not self.roam_windows or engine.reduced or not engine.roam:
            return
        w, h = engine.size
        feet, reach = int(engine.y + h), int(2 * h)
        seen: list = []
        self._scan(now, force=True, near=(int(engine.x + w / 2), feet, reach), seen=seen)
        for cls, rect, why in seen[:8]:
            used = any(p.left <= engine.x + w / 2 < p.right and p.top == rect[1] for p in engine.windows)
            logger.info(
                "overlay: let go at %s with the feet at y %d: a %s window, top %d, x %d to %d, counted as %s%s",
                (x, y), feet, cls or "nameless", rect[1], rect[0], rect[2], why,
                "" if why != "perch" else (", its top is a place to stand" if used else ", its top is covered or too narrow here"),
            )

    def _scan(self, now: float, force: bool = False, near: tuple[int, int, int] | None = None, seen: list | None = None) -> None:
        engine = self.engine
        assert engine is not None
        self._watch_taskbar(now)
        engine.roam_windows = self.roam_windows
        engine.lively = self.lively
        if not self.roam_windows:
            if engine.windows or engine.perch is not None:
                engine.set_windows([], now)
            return
        if engine.tuck is not None or engine.hang_on is not None:  # hidden behind or hanging from a window: the next look is a quarter second away, not up to a second
            self._next_scan = min(self._next_scan, now + SCAN_RIDING)
        if not force and (now < self._next_scan or not self._wants_scan(now)):
            return
        # On a window it rides it: a dragged window is followed four times a second, not once.
        self._next_scan = now + (SCAN_RIDING if engine.is_riding() else SCAN_EVERY)
        tally: Counter = Counter()
        wins = self._list_windows(tally, near, seen)
        self._answer(self._window_events(wins, now), now)
        scale = max(m.dpi for m in self.monitors) / 96.0 if self.monitors else 1.0
        room = int(engine.size[0] + PERCH_ROOM * scale)
        drops: Counter = Counter()
        edges = perches.top_edges(wins, eng.perch_room(engine.size[0], scale), drops)
        hangs = perches.hang_spots(wins, room)
        engine.set_windows(edges, now, hangs, perches.tuck_spots(wins, room))
        self._log_scan(len(wins), len(edges), len(engine._candidates(drops)), tally, len(edges) + len(hangs), drops)
        self._log_skips(tally)
        self._log_notes()

    def _screen_events(self, now: float) -> None:
        """What happened on the screen since the last tick, handed to the engine to answer (INBOX 1683, M6; 1700): the app
        changing, a window opening, closing or dragged (the list is read every `EVERY` s here, whether or not a climb is near),
        the hour, the battery, a finished download. Read only while the figure is up and awake (a hidden, sitting or
        sleeping one reads nothing); typing holds the answer back, a text caret alone does not."""
        engine = self.engine
        if engine is None or engine.reduced or not engine.roam:  # (a text caret in the foreground window is not typing: INBOX 1700)
            return
        if engine.state in ("sit", "sleep", "pressed", "held", "warp"):
            return
        local = time.localtime()
        hour = local.tm_hour if self.clock_hour is None else self.clock_hour
        kinds = timed(self, "poll", self._watch.poll, now, hour, local.tm_min, screen=self.roam_windows, day=local.tm_yday)
        if self.roam_windows and not engine.quiet and now - self._events_read >= screenwatch.EVERY:
            kinds += self._window_events(self._list_windows(Counter()), now)  # a window opening, closing or dragged is news with no climb near
        self._answer(kinds, now)

    def _window_events(self, wins: list, now: float) -> list[str]:
        """What a window list says happened (an empty list is a failed read, not every window closing); its rects are kept
        for the figure to look toward."""
        self._events_read = now
        if not wins:
            return []
        self._rects = {w.key: tuple(w.rect) for w in wins}  # type: ignore[misc]
        return self._watch.windows_seen(w.key for w in wins) + self._watch.states_seen(wins)

    def _resume_engine(self, engine: Any, now: float) -> None:
        """Back after a stall (a resume, a full-screen app gone, shown again): the engine re-times its acts
        and the screen watch forgets, so nothing that happened while away is answered as news (1678 review)."""
        self._watch.forget()
        engine.resume(now)

    def _answer(self, kinds: list[str], now: float) -> None:
        """Hold each event for `SCREEN_WAIT` s and play what the figure is free for (INBOX 1700): one line at INFO when an
        event is seen, one when it is answered (and which way it looked), one when it was given up."""
        engine = self.engine
        for kind in kinds:
            if kind not in self._events:
                logger.info("overlay: screen event %s", kind)
            self._events[kind] = now + SCREEN_WAIT
        for kind, until in list(self._events.items()):
            if engine is not None and not engine.quiet and engine.react(kind, now):
                del self._events[kind]
                logger.info("overlay: it answered %s%s", kind, self._look_toward(kind, now))
            elif now >= until:
                del self._events[kind]
                logger.info("overlay: screen event %s went unanswered (state %s, typing %s)", kind, engine.state if engine else "none", bool(engine and engine.quiet))

    def _look_toward(self, kind: str, now: float) -> str:
        """Turn to the window the event was about (the one now in front, the one that opened, moved or changed size): ", looking
        left or right", or "" when it is unknown or the event is not about a window."""
        engine = self.engine
        key = self._watch.fg if kind == "app_switched" else self._watch.subject.get(kind)
        rect = self._rects.get(key) if key is not None else None
        if engine is None or rect is None:
            return ""
        side = 1 if (rect[0] + rect[2]) / 2 >= engine.x + engine.size[0] / 2 else -1
        engine._face(side, now)
        return ", looking right" if side > 0 else ", looking left"

    def _log_notes(self) -> None:
        """What the engine decided about a trip to a window or an edge (chosen, skipped and why), one INFO line each."""
        engine = self.engine
        while engine is not None and engine.notes:
            logger.info("overlay: %s", engine.notes.pop(0))

    def _log_scan(self, listed: int, edges: int, candidates: int, tally: Counter, hangs: int = 0, drops: Counter | None = None) -> None:
        """One INFO line when what the window list returns changes (counts and reasons, never a title), so a
        companion that never perches can be read off the log (INBOX 1683 g)."""
        parts = ", ".join(f"{n} {why}" for why, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])))
        line = f"overlay: windows listed {listed}, standable top edges {edges}, worth the trip {candidates}, hang spots {hangs}" + (f" ({parts})" if parts else "")
        if drops:  # why a standable window's top gave no perch or no trip: counts only (INBOX 1692 n)
            line += "; edges dropped: " + ", ".join(f"{n} {why}" for why, n in sorted(drops.items(), key=lambda kv: (-kv[1], kv[0])))
        if line != self._last_scan_line:
            self._last_scan_line = line
            logger.info(line)

    def _log_skips(self, tally: Counter) -> None:
        """One INFO line with the count of windows skipped for each reason, every reason always present (zeros too), so a
        scan that finds no place to stand reads off the log. Counts only, from the window walk, never a title or a
        preference (INBOX 1778 e: 535 windows listed by EnumWindows are mostly hidden helpers)."""
        invisible = sum(n for why, n in tally.items() if why.startswith("invisible"))
        line = (
            "overlay: window scan skipped: invisible %d (of those with a title bar %d), cloaked %d, minimised %d, tool window %d, too small %d, own window %d, off-screen %d"
            % (invisible, tally["invisible, with a title bar"] + tally["invisible, yet foreground"], tally["cloaked"], tally["minimised"],
               tally["tool window"], tally["too small"], tally["own overlay"] + tally["own process"], tally["off-screen"])
        )
        if line != self._last_skip_line:
            self._last_skip_line = line
            logger.info(line)

    def _scan_wake(self, wake: int | None) -> int | None:
        """The engine's wake, but no later than the next scan while one is wanted."""
        if not self._wants_scan(self.clock()):
            return wake
        due = max(30, int((self._next_scan - self.clock()) * 1000))
        return due if wake is None else min(wake, due)

    def _cap_wake(self, wake: int | None) -> int | None:
        """No sleep longer than the busy check, so the caret and the typing are read at 0.5 Hz."""
        cap = int(BUSY_EVERY * 1000)
        return cap if wake is None else min(wake, cap)

    def _read_typing(self, now: float) -> None:
        """Whether keys are going in, and where: the caret, else (an app with none) the window's bottom band."""
        age = self.k.last_input_age(self.w)
        engine = self.engine
        if engine is None:  # typing: it stays put (nothing big); the mouse alone is not typing
            return
        engine.quiet = age is not None and age < TYPING_AGE and now - self._ptr_moved_at > age
        # the person back after a long absence (checked here: a sitting or sleeping figure reads no screen events)
        for kind in self._watch.input_seen(now, age):  # idle_return, or the morning's first hello
            self._return_until, self._return_kind = now + RETURN_FOR, kind
        if now < self._return_until and engine.react(self._return_kind, now):
            self._return_until = 0.0
            logger.info("overlay: it answered %s", self._return_kind)
        burst = self._watch.typing_seen(now, engine.quiet)  # a long run of typing come to rest: a nod
        if burst:
            self._answer(burst, now)
        # at BUSY_EVERY (0.5 Hz); Chromium and Electron give no caret (INBOX 1670 13:22Z)
        read_caret = getattr(self.k, "caret_rect", None)  # the X11 backend reads no caret yet
        caret = read_caret(self.w) if read_caret else None
        engine.set_caret(caret if caret is not None or not engine.quiet else self._text_zone(now))

    def _text_zone(self, now: float) -> tuple[int, int, int, int] | None:
        """The text band, read again only when the foreground window changes or every ZONE_EVERY s
        (a window rarely moves while someone types in it), so typing costs one frame read, not one per check."""
        read_zone = getattr(self.k, "text_zone", None)
        if read_zone is None:
            return None
        try:
            hwnd = int(self.w.user32.GetForegroundWindow() or 0)
        except Exception:  # noqa: BLE001 - no foreground window to read is no band
            logger.debug("overlay: foreground window unreadable", exc_info=True)
            return None
        kept = self._zone
        if kept is not None and kept[0] == hwnd and now - kept[1] < ZONE_EVERY:
            return kept[2]
        band = read_zone(self.w, hwnd) if hwnd else None
        self._zone = (hwnd, now, band)
        return band

    def _busy_gate(self, now: float, pointer: tuple[int, int] | None = None) -> int | None:
        """Hide while something fullscreen is in the way; None when free to move."""
        if now < self._next_busy_check and not self.busy:
            return None
        self._next_busy_check = now + BUSY_EVERY
        if pointer is not None:
            if self._busy_ptr is not None and pointer != self._busy_ptr:
                self._ptr_moved_at = now
            self._busy_ptr = pointer
        timed(self, "typing", self._read_typing, now)
        state = timed(self, "notify", self.k.notification_state, self.w)
        away = state in self.k.QUNS_HIDE
        if away and not self.busy:
            logger.info("overlay: hidden while something fullscreen or busy is up (state %s)", state)
            self.busy = True
            self.host.hide()  # type: ignore[union-attr]
        elif not away and self.busy:
            logger.info("overlay: shown again")
            self.busy = False
            self.host.show()  # type: ignore[union-attr]
            self._resume_engine(self.engine, now)
            self._answer(["fullscreen_app"], now)  # back from behind a full-screen app: it peeks out (INBOX 1719 b)
            return None
        return int(BUSY_EVERY * 1000) if self.busy else None

    def _read_monitors(self) -> list[eng.Monitor]:
        found = read_layout(self.k, self.w)
        if not found:
            raise OSError("no monitor was reported")
        self._bars_key = [(m.screen, m.bars) for m in found]
        return found

    def _refresh_monitors(self) -> None:
        try:
            self.monitors = self._read_monitors()
        except OSError:
            logger.warning("overlay: monitors could not be read after a display change", exc_info=True)
            return
        assert self.engine is not None and self.sprites is not None
        dpi = self.engine.monitor_at(self.engine.x, self.engine.y).dpi
        self.dpi = dpi
        self.sprites.keep_only(self._fdpi())
        self.engine.set_monitors(self.monitors, self.sprites.size(self._fdpi()))
        self.engine.set_metrics(self.sprites.metrics(self._fdpi()))
        self._last_key = None

    def _ready(self) -> None:
        """On the overlay thread, once its window exists: monitors in its own
        awareness, the frames, the engine, and the first frame drawn (hidden)."""
        self.monitors = self._read_monitors()
        spr = sprites.SpriteSet(self.look, self.frames)
        if spr.missing():
            raise OSError(f"overlay frames missing: {spr.missing()[:3]}")
        self.sprites = spr
        reduced = self.reduced
        if reduced is None:
            reduced = not self.k.animations_enabled(self.w)
            self.reduced_reason = "os" if reduced else ""
        self.reduced = reduced
        first = self.monitors[0]
        self.dpi = first.dpi
        self.engine = eng.Engine(
            spr.size(self._fdpi()), self.monitors, home=self.home, reduced=reduced, roam=not self.stay, roam_windows=self.roam_windows, gait=spr.gait, hang_top=spr.top_share("hang"), idle_frames=spr.idle_count(), walk_frames=spr.walk_count(), wave_frames=spr.wave_count(), extra_frames=spr.extras(), now=self.clock(), rng=self.rng,
        )
        self.engine.set_metrics(spr.metrics(self._fdpi()))
        self.engine.take(self.carried, self.clock())
        if self.enter:
            self.entrance = self.engine.enter_scene(self.clock())  # a first show arrives (INBOX 1718 a); a restart carries its place
        out = self.engine.update(self.clock())
        self._apply(out)
        logger.info(
            "overlay: ready, look=%s, monitors=%s, frames=%d at %s px, reduced=%s%s, effects=%s",
            self.look, [(m.area, m.dpi) for m in self.monitors], len(sprites.FRAME_NAMES), spr.size(self._fdpi()), reduced,
            f" ({self.reduced_reason})" if reduced and self.reduced_reason else "",
            # INBOX 1692: with the OS's animations off every portal is a plain fade; the log says so, so it is not a mystery
            "off, every move is a fade (animations are off in " + (self.reduced_reason or "the app") + ")" if reduced else "on",
        )

    def _apply(self, out: eng.Output) -> int | None:
        engine, spr, host = self.engine, self.sprites, self.host
        assert engine is not None and spr is not None and host is not None
        dpi = engine.current_monitor().dpi
        if dpi != self.dpi:
            if self._sizing is not None:
                self._end_pull(self.clock())  # the pull's distances were in the old pixels: it ends where it is
            self.dpi = dpi
            spr.keep_only(self._fdpi())
            engine.set_monitors(self.monitors, spr.size(self._fdpi()))
            engine.set_metrics(spr.metrics(self._fdpi()))
            self._last_key, self._blend, self._target = None, None, None
        now = self.clock()
        eased = self._ease(now)
        engine.hour = time.localtime().tm_hour if self.clock_hour is None else self.clock_hour
        # a thrown figure's true angle is part of the picture (INBOX 1683): every tick of a spin is a new one
        turn = None if out.angle is None else round(math.degrees(out.angle) / sprites.SPIN_QUANT) % round(360.0 / sprites.SPIN_QUANT)
        handle = self._handle_shown(out, now)
        key = (out.frame, self._fdpi(), out.flip, out.clip, out.pose, out.fx, out.alpha, turn, out.flow, out.prop, out.face, out.tail, out.squash, handle)
        blending = False
        if key != self._last_key:
            blending = self._new_picture(out, key)
        elif self._blend is not None:
            blending = self._show(self._target, out, False)
        elif (out.x, out.y) != self._last_pos:
            pad = self._target or spr.frame(out.frame, self._fdpi(), out.flip)
            host.move(out.x - pad.pad_x, out.y - pad.pad_y)
            self._last_pos = (out.x, out.y)
        self._hand_offs(out, engine)
        self._warm_spins(spr)  # after the picture is shown: a new size draws first, its turns are built behind it
        wake = self._cap_wake(self._scan_wake(out.wake_ms))
        wake = self._handle_wake(wake, handle, now)
        if blending or eased:  # the dissolve is a move: one step a display frame
            wake = BLEND_TICK_MS if wake is None else min(wake, BLEND_TICK_MS)
        return wake

    def _warm_spins(self, spr: sprites.SpriteSet) -> None:
        """Once a size is settled, its quarter turn is built on a worker (INBOX 1696 a: a fall rotated a fresh picture
        every tick, 6 ms at dpi 192, about 8 fps on the owner's machine), so a throw only transposes. Not mid-pull or
        mid-ease (each step is a size of its own), and not in reduced motion, where nothing spins."""
        fd = self._fdpi()
        if fd == self._warmed or self._sizing is not None or self._goal is not None or self.reduced:
            return
        self._warmed = fd
        self._hand_off("overlay-spins", lambda: spr.warm_spins(fd))

    def _hand_offs(self, out: eng.Output, engine: eng.Engine) -> None:
        """What the tick finished, passed on off the overlay thread: a click, a settled place, a card."""
        if out.click:
            rect = self.drawn_rect(out.x, out.y, out.frame, out.flip)
            self._hand_off("overlay-click", lambda: self.on_click and self.on_click(out.click, rect, self.dpi))
        if out.settled:
            self._drops += 1
            home = engine.home()  # where it stands, not where its window is drawn (feet are planted)
            self._hand_off("overlay-settle", lambda: self.on_settle and self.on_settle(*home))
        if engine.home_arrivals != self._arrivals_seen:
            self._arrivals_seen = engine.home_arrivals
            place, drops = engine.home(), self._drops
            # the hand-offs run on workers in any order: an arrival saved after a later drop would undo the drop's place
            self._hand_off("overlay-place", lambda: self.on_place and self._drops == drops and not out.settled and self.on_place(*place))
        if out.card is not None:
            token = out.card
            self._hand_off("overlay-card", lambda: self.on_card and self.on_card(token))

    def _new_picture(self, out: eng.Output, key: tuple) -> bool:
        """A new picture: build it, start a dissolve from the last one when the change earns one (a look's is
        the slow head turn), and present it. True while the dissolve has more to come."""
        spr = self.sprites
        assert spr is not None
        if out.angle is not None:
            posed = spr.spun_at(out.angle, self._fdpi(), out.flip)
        else:
            posed = spr.posed(out.frame, self._fdpi(), out.flip, out.pose or eng.bh.NEUTRAL, out.flow) if out.pose or out.flow else spr.frame(out.frame, self._fdpi(), out.flip)
        if out.tail and out.angle is None:
            posed = spr.tailed(posed, out.frame, self._fdpi(), out.flip, out.tail)  # the tail's layer, over the body frame (C1)
        posed = self._decorated(posed, out, key)
        frame = sprites.effect(sprites.clipped(sprites.squashed(posed, out.squash), out.clip), out.fx, out.alpha)
        self._hit = None
        if key[-1]:
            hanging = out.frame.startswith("hang")
            box = sizing.corner_box(frame, hanging)
            hit = sizing.hit_box(box, hanging, self.dpi)
            area = self.engine.current_monitor().area if self.engine else None
            if area is not None and out.x - frame.pad_x + max(frame.width, hit[2]) > area[2]:
                hit = sizing.hit_box(box, hanging, self.dpi, left=True)  # the right corner is off the screen: the left one
            frame, self._hit = sizing.with_handle(frame, hit, self._sizing is not None)
            self._hit_cursor = win32.IDC_SIZENWSE if sizing.pulls_nwse(box, hit, hanging) else win32.IDC_SIZENESW
        self._blend = (self._target, self.clock()) if self._blends(self._last_key, key, self._target, frame) else None
        self._blend_s = BLEND_LOOK_S if self._last_key and "look" in (self._last_key[0], key[0]) else BLEND_S
        self._target, self._blend_step = frame, -1
        self._last_key, self._shown = key, (out.frame, out.flip)
        return self._show(frame, out, True)

    def _decorated(self, posed: sprites.Frame, out: eng.Output, key: tuple) -> sprites.Frame:
        """The face and the prop drawn over the posed frame (`faces.draw`, `props.draw`), kept by picture: a prop
        act repeats a few phases for a minute, so each is built once."""
        spr = self.sprites
        if (out.face is None and out.prop is None) or spr is None or out.angle is not None:
            return posed
        built = self._decor.pop(key, None)
        if built is None:
            built = posed
            if out.face is not None:
                built = faces.draw(spr, out.frame, built, out.flip, out.pose, out.face, spr.frame(out.frame, self._fdpi(), out.flip))
            if out.prop is not None:
                built = props.draw(built, out.prop, out.flip)
        self._decor[key] = built
        while len(self._decor) > DECOR_KEEP:
            del self._decor[next(iter(self._decor))]
        return built

    def _blends(self, before: tuple | None, after: tuple, prev: sprites.Frame | None, frame: sprites.Frame) -> bool:
        """A pose change dissolves (INBOX 1670: "framey"): standing to walking, sitting up, a wave, a landing.
        Not the cycle's own in-betweens, not a blink (quick on purpose; a look dissolves slowly, as a head turn), not a reaction to the person
        (held, thrown, falling), not a vanish or a peek, and never in reduced motion."""
        if prev is None or before is None or self.reduced or self.engine is None:
            return False
        if after[3] is not None or after[5] is not None or before[3] is not None or before[5] is not None:
            return False
        a, b = before[0].rstrip("0123456789"), after[0].rstrip("0123456789")
        return a != b and a in BLENDED and b in BLENDED and (prev.width, prev.height) == (frame.width, frame.height)

    def _show(self, frame: sprites.Frame, out: eng.Output, changed: bool) -> bool:
        """Present `frame`, or while a dissolve runs the mix of the old picture and it, one step a display
        frame (`BLEND_STEPS` of them over `BLEND_S`). True while there is more to come."""
        host = self.host
        assert host is not None
        shown, more = frame, False
        if self._blend is not None:
            prev, t0 = self._blend
            u = (self.clock() - t0) / self._blend_s
            if u >= 1.0:
                self._blend = None
            else:
                step = int(u * BLEND_STEPS)
                if not changed and step == self._blend_step:
                    return True
                self._blend_step = step
                mixed = sprites.mix(prev, frame, (step + 1) / (BLEND_STEPS + 1)) if prev is not None else None
                if mixed is None:
                    self._blend = None
                else:
                    shown, more = mixed, True
        host.present(shown.bgra, shown.width, shown.height, out.x - shown.pad_x, out.y - shown.pad_y)
        self._last_pos = (out.x, out.y)
        return more

    def drawn_rect(self, x: int, y: int, frame: str | None = None, flip: bool | None = None, dpi: int | None = None) -> tuple[int, int, int, int]:
        """The figure's drawn box (x, y, width, height, physical pixels) for a window at
        (x, y), not the window's own: the quick panel sits beside the figure (INBOX 1663).
        Defaults to the frame last drawn."""
        spr = self.sprites
        assert spr is not None
        dpi = int(dpi or self._fdpi())
        name, mirror = (frame, flip) if frame is not None else self._shown
        f = spr.frame(name, dpi, bool(mirror))
        left, top, right, bottom = f.box
        return x - f.pad_x + left, y - f.pad_y + top, right - left, bottom - top

    # --- the size handle ---------------------------------------------------------------------------

    def _handle_shown(self, out: eng.Output, now: float) -> bool:
        """The handle shows while the pointer is over the figure (and a moment after), or is held on it, when the
        figure is whole and in no effect: not while it is thrown, carried, faded or clipped behind an edge."""
        if out.angle is not None or out.fx is not None or out.alpha < 1.0 or out.clip is not None or out.frame in ("held", "fall"):
            return False
        return self._sizing is not None or now < self._hover_until

    def _handle_wake(self, wake: int | None, shown: bool, now: float) -> int | None:
        """The handle goes when the pointer has been gone for SHOW_S: wake then to draw it away."""
        if self._sizing is not None:  # the idle check of a pull that may never be released
            return 1000 if wake is None else min(wake, 1000)
        if not shown:
            return wake
        left = max(1, int((self._hover_until - now) * 1000) + 1)
        return left if wake is None else min(wake, left)

    def _hit_screen(self) -> tuple[int, int, int, int] | None:
        target, at = self._target, self._last_pos
        if self._hit is None or target is None or at is None:
            return None
        ox, oy = at[0] - target.pad_x, at[1] - target.pad_y
        h = self._hit
        return ox + h[0], oy + h[1], ox + h[2], oy + h[3]

    def _handle_event(self, kind: str, x: int, y: int, now: float) -> bool:
        """A press, move or release meant for the size handle (True: the engine does not see it). Over the figure a
        move shows the handle; a press on it starts a pull from the stand or hang point, a second press close to the
        first goes back to Medium (the app's grip, `avatars.js`), and a release keeps the size. A press the engine
        took (a drag of the figure) shows no handle until the next hover."""
        if self._sizing is not None:
            return self._pull_handle(kind, x, y, now)
        rect = self._hit_screen()
        over = rect is not None and rect[0] <= x < rect[2] and rect[1] <= y < rect[3]
        self._set_cursor(self._hit_cursor if over else 0)
        if kind == "down":
            if over and self._press_handle(x, y, now):
                self._engine_press = False
                return True
            self._engine_press, self._hover_until = True, -math.inf
            return False
        if kind == "up":
            self._engine_press, self._hover_until = False, -math.inf
            return False
        if kind == "move" and not self._engine_press:
            self._hover_until = now + sizing.SHOW_S
            return over
        return False

    def _set_cursor(self, idc: int) -> None:
        """The pointer's shape over the overlay, told to the host only when it changes."""
        if idc != self._cursor_now and self.host is not None:
            self._cursor_now = idc
            self.host.cursor(idc)

    def _press_handle(self, x: int, y: int, now: float) -> bool:
        """A press on the handle: the second of a double goes back to Medium, else a pull starts from the point the
        figure stands or hangs on. Either way what Appearance or an earlier ease was walking to is dropped."""
        self._goal = None
        last, self._last_press = self._last_press, (now, x, y, False)
        if last and now - last[0] < sizing.DOUBLE_S and math.hypot(x - last[1], y - last[2]) < sizing.DOUBLE_PX and not last[3]:
            self._last_press = None
            self._goal = sizing.MEDIUM
            return True
        if self._last_pos is None:
            return True
        box = self.drawn_rect(*self._last_pos)
        hanging = self._shown[0].startswith("hang")
        origin = (box[0] + box[2] / 2, box[1] if hanging else box[1] + box[3])
        self._sizing = {"origin": origin, "from": max(8.0, math.hypot(x - origin[0], y - origin[1])), "was": self.scale, "press": (x, y), "moved": False, "last": now}
        self._hover_until = now + sizing.SHOW_S
        self._last_key = None
        return True

    def _pull_handle(self, kind: str, x: int, y: int, now: float) -> bool:
        st = self._sizing
        assert st is not None
        st["last"] = now
        if kind == "move":
            if not st["moved"] and math.hypot(x - st["press"][0], y - st["press"][1]) < sizing.SLOP_PX:
                return True
            st["moved"] = True
            if self._last_press:
                self._last_press = (*self._last_press[:3], True)
            new = sizing.clamp(sizing.pulled(st["was"], st["from"], math.hypot(x - st["origin"][0], y - st["origin"][1]), self.dpi))
            if new != self.scale:
                self._set_scale(new)
        elif kind == "up":
            self._end_pull(now)
        return True

    def _end_pull(self, now: float) -> None:
        """The pull is over (a release, or none came): the figure goes on from where it was held, the size is kept
        and passed on if the pointer moved it."""
        st, self._sizing = self._sizing, None
        self._goal, self._last_key = None, None
        self._hover_until = now + sizing.SHOW_S
        if self.engine is not None:
            self._resume_engine(self.engine, now)
        if st is not None and st["moved"]:
            self._saved()

    def _saved(self) -> None:
        scale = self.scale
        self._pending = (scale, self.clock() + sizing.PENDING_S)
        self._hand_off("overlay-size", lambda: self.on_size and self.on_size(scale))

    def _set_scale(self, scale: float) -> None:
        """One step of size: the pictures at the new dpi (the old ones dropped), the engine told once, the window
        resized by the next picture. The stand or hang point stays where it was (`Engine.resize`)."""
        engine, spr = self.engine, self.sprites
        assert engine is not None and spr is not None
        self.scale = scale
        fd = self._fdpi()
        spr.keep_only(fd)
        engine.resize(spr.size(fd), spr.metrics(fd))
        self.resizes += 1
        self._last_key, self._blend, self._target = None, None, None

    def _ease(self, now: float) -> bool:
        """Toward the size Appearance or a double press asked for, one step a tick (at once in reduced motion).
        True while there is more to go."""
        goal = self._goal
        if goal is None or self._sizing is not None:
            return False
        if goal == self.scale:
            self._goal = None
            return False
        nxt = goal if self.reduced else round(self.scale + max(-sizing.STEP, min(sizing.STEP, goal - self.scale)), 2)
        self._set_scale(nxt)
        if nxt == goal:
            self._goal = None
            if self.on_size is not None:
                self._saved()
            return False
        return True

    def _hand_off(self, name: str, call: Callable[[], Any]) -> None:
        try:
            self._dispatch(name, call)
        except Exception:  # noqa: BLE001 - the pet keeps walking if a click cannot be passed on
            logger.warning("overlay: could not hand off %s", name, exc_info=True)
