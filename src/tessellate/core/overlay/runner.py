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

import collections
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Callable

from tessellate.core import jobs
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import host as host_mod
from tessellate.core.overlay import perches
from tessellate.core.overlay import sprites
from tessellate.core.overlay import win32 as k

logger = logging.getLogger(__name__)

#: How often to ask whether something fullscreen is in the way (seconds).
BUSY_EVERY = 2.0
#: Input this recent means the person is typing or working: no acts, only standing.
TYPING_AGE = 2.5
#: The window scan is at most this often (seconds); it starts this long before a
#: climb is due, so the first read is in hand when it is.
SCAN_EVERY = 1.0
SCAN_SLACK = 1.0
#: Room past the figure's width a top edge needs to be stood on (logical px, at 96 dpi).
PERCH_ROOM = 20


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
        roam_windows: bool = True,
        w: Any = None,
        clock: Callable[[], float] = time.monotonic,
        frames: Path | None = None,
        dispatch: Callable[[str, Callable[[], None]], Any] | None = None,
    ) -> None:
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
        self.roam_windows = roam_windows
        self.w = w
        self.clock = clock
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
        self._stopped = False
        self._resume = False
        self._last_key: tuple[str, int, bool, tuple[int, int, int, int] | None] | None = None
        self._last_pos: tuple[int, int] | None = None
        self._next_busy_check = 0.0
        self._next_scan = 0.0
        self._cards: collections.deque[Any] = collections.deque()
        self._scan_failed = False

    # --- life (any thread) ------------------------------------------------------------

    def start(self, timeout: float = 3.0) -> bool:
        """Make the window and the engine. False (and logged) when either fails:
        the coordinator then falls back to the card window."""
        try:
            if self.w is None:
                self.w = k.load()
            self.host = host_mod.OverlayHost(self.w, on_event=self._on_event, on_exit=self._exited)
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

    def set_roam(self, on: bool) -> None:
        """The "Roam over windows" switch: takes effect on the next tick."""
        self.roam_windows = bool(on)
        if self.host:
            self.host.wake(1)

    def dpi_at(self, x: int, y: int) -> int:
        """The dpi of the monitor under a physical point (MonitorFromPoint, then
        GetDpiForMonitor); the monitor list's, then 96, when Windows cannot say."""
        found = k.dpi_at_point(self.w, x, y) if self.w is not None else None
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
        if kind == "ready":
            self._ready()
            return None
        if self.engine is None or self.paused and kind != "resume":
            return None
        now = self.clock()
        if kind in ("down", "move", "up", "right"):
            return self._apply(self.engine.update(now, (x, y), (kind, x, y)))
        return self._system(kind, now, (x, y))

    def _system(self, kind: str, now: float, pointer: tuple[int, int]) -> int | None:
        engine = self.engine
        assert engine is not None
        if kind == "suspend":
            self.paused = True
            return None
        if kind == "resume":
            self.paused = False
            engine.resume(now)
            return 1
        if kind == "display":
            self._refresh_monitors()
        if kind == "tick":
            if not self.visible:
                return None
            if self._resume:
                self._resume = False
                engine.resume(now)
            hold = self._busy_gate(now, pointer)
            if hold is not None:
                return hold
            while self._cards:
                engine.bring_card(self._cards.popleft(), now)
            self._scan(now)
        if kind not in ("tick", "display"):
            return None
        return self._apply(engine.update(now, pointer))

    # --- other windows' tops ------------------------------------------------------------

    def _wants_scan(self, now: float) -> bool:
        """Only when a climb could come soon or the figure stands on a window."""
        e = self.engine
        if e is None or not self.roam_windows or e.reduced or not e.roam or e.quiet:
            return False
        if e.perch is not None or e.target is not None or e.state in ("pressed", "held"):
            return True  # carried: a title bar under it may be taken hold of
        return e.state in ("stand", "walk", "drift", "act", "crouch") and now >= e.trip_ready - SCAN_SLACK

    def _scan(self, now: float) -> None:
        engine = self.engine
        assert engine is not None
        engine.roam_windows = self.roam_windows
        if not self.roam_windows:
            if engine.windows or engine.perch is not None:
                engine.set_windows([], now)
            return
        if now < self._next_scan or not self._wants_scan(now):
            return
        self._next_scan = now + SCAN_EVERY
        try:
            wins = k.windows(
                self.w, os.getpid(), self.host.hwnd if self.host else None, [m.area for m in self.monitors],
            )
        except Exception:  # noqa: BLE001 - no window list means no roaming, never a crash
            if not self._scan_failed:
                logger.warning("overlay: the windows could not be listed", exc_info=True)
            self._scan_failed = True
            wins = []
        scale = max(m.dpi for m in self.monitors) / 96.0 if self.monitors else 1.0
        edges = perches.top_edges(wins, int(engine.size[0] + PERCH_ROOM * scale))
        engine.set_windows(edges, now)

    def _scan_wake(self, wake: int | None) -> int | None:
        """The engine's wake, but no later than the next scan while one is wanted."""
        if not self._wants_scan(self.clock()):
            return wake
        due = max(30, int((self._next_scan - self.clock()) * 1000))
        return due if wake is None else min(wake, due)

    def _busy_gate(self, now: float, pointer: tuple[int, int] | None = None) -> int | None:
        """Hide while something fullscreen is in the way; None when free to move."""
        if now < self._next_busy_check and not self.busy:
            return None
        self._next_busy_check = now + BUSY_EVERY
        if pointer is not None:
            if self._busy_ptr is not None and pointer != self._busy_ptr:
                self._ptr_moved_at = now
            self._busy_ptr = pointer
        age = k.last_input_age(self.w)
        engine = self.engine
        if engine is not None:  # typing: it stays put (nothing big); the mouse alone is not typing
            engine.quiet = age is not None and age < TYPING_AGE and now - self._ptr_moved_at > age
        state = k.notification_state(self.w)
        away = state in k.QUNS_HIDE
        if away and not self.busy:
            logger.info("overlay: hidden while something fullscreen or busy is up (state %s)", state)
            self.busy = True
            self.host.hide()  # type: ignore[union-attr]
        elif not away and self.busy:
            logger.info("overlay: shown again")
            self.busy = False
            self.host.show()  # type: ignore[union-attr]
            self.engine.resume(now)  # type: ignore[union-attr]
            return None
        return int(BUSY_EVERY * 1000) if self.busy else None

    def _read_monitors(self) -> list[eng.Monitor]:
        found = [eng.Monitor(area, dpi) for area, dpi in k.monitors(self.w)]
        if not found:
            raise OSError("no monitor was reported")
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
        self.engine.set_monitors(self.monitors, self.sprites.size(dpi))
        self.engine.set_metrics(self.sprites.metrics(dpi))
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
            reduced = not k.animations_enabled(self.w)
            self.reduced_reason = "os" if reduced else ""
        self.reduced = reduced
        first = self.monitors[0]
        self.dpi = first.dpi
        self.engine = eng.Engine(
            spr.size(first.dpi), self.monitors, home=self.home, reduced=reduced, roam_windows=self.roam_windows, gait=spr.gait, hang_top=spr.top_share("hang"), idle_frames=sprites.IDLE_COUNT, now=self.clock(),
        )
        self.engine.set_metrics(spr.metrics(first.dpi))
        out = self.engine.update(self.clock())
        self._apply(out)
        logger.info(
            "overlay: ready, look=%s, monitors=%s, frames=%d at %s px, reduced=%s%s",
            self.look, [(m.area, m.dpi) for m in self.monitors], len(sprites.FRAME_NAMES), spr.size(first.dpi), reduced,
            f" ({self.reduced_reason})" if reduced and self.reduced_reason else "",
        )

    def _apply(self, out: eng.Output) -> int | None:
        engine, spr, host = self.engine, self.sprites, self.host
        assert engine is not None and spr is not None and host is not None
        dpi = engine.current_monitor().dpi
        if dpi != self.dpi:
            self.dpi = dpi
            engine.set_monitors(self.monitors, spr.size(dpi))
            engine.set_metrics(spr.metrics(dpi))
            self._last_key = None
        engine.hour = time.localtime().tm_hour if self.clock_hour is None else self.clock_hour
        key = (out.frame, self.dpi, out.flip, out.clip, out.pose)
        if key != self._last_key:
            posed = spr.posed(out.frame, self.dpi, out.flip, out.pose) if out.pose else spr.frame(out.frame, self.dpi, out.flip)
            frame = sprites.clipped(posed, out.clip)
            host.present(frame.bgra, frame.width, frame.height, out.x - frame.pad_x, out.y - frame.pad_y)
            self._last_key, self._last_pos = key, (out.x, out.y)
        elif (out.x, out.y) != self._last_pos:
            pad = spr.frame(out.frame, self.dpi, out.flip)
            host.move(out.x - pad.pad_x, out.y - pad.pad_y)
            self._last_pos = (out.x, out.y)
        if out.click:
            rect = self.drawn_rect(out.x, out.y, out.frame, out.flip)
            self._hand_off("overlay-click", lambda: self.on_click and self.on_click(out.click, rect, self.dpi))
        if out.settled:
            home = engine.home()  # where it stands, not where its window is drawn (feet are planted)
            self._hand_off("overlay-settle", lambda: self.on_settle and self.on_settle(*home))
        if out.card is not None:
            token = out.card
            self._hand_off("overlay-card", lambda: self.on_card and self.on_card(token))
        return self._scan_wake(out.wake_ms)

    def drawn_rect(self, x: int, y: int, frame: str | None = None, flip: bool | None = None, dpi: int | None = None) -> tuple[int, int, int, int]:
        """The figure's drawn box (x, y, width, height, physical pixels) for a window at
        (x, y), not the window's own: the quick panel sits beside the figure (INBOX 1663).
        Defaults to the frame last drawn."""
        spr = self.sprites
        assert spr is not None
        dpi = int(dpi or self.dpi)
        name, mirror = (frame, flip) if frame is not None else (self._last_key[0], self._last_key[2]) if self._last_key else ("stand", False)
        f = spr.frame(name, dpi, bool(mirror))
        left, top, right, bottom = f.box
        return x - f.pad_x + left, y - f.pad_y + top, right - left, bottom - top

    def _hand_off(self, name: str, call: Callable[[], Any]) -> None:
        try:
            self._dispatch(name, call)
        except Exception:  # noqa: BLE001 - the pet keeps walking if a click cannot be passed on
            logger.warning("overlay: could not hand off %s", name, exc_info=True)
