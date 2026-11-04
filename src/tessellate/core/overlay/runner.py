"""Window, behaviour and frames, joined (BACKLOG 16, O4).

`OverlayRunner` owns one `OverlayHost`, one `Engine` and one `SpriteSet`. Every
call into the engine happens on the overlay's own thread (the host's event
callback), so the engine needs no lock; other threads only call `show`, `hide`
and `stop`, which queue work for that thread.

A click on the figure is handed to `on_click(kind, rect, dpi)` on a worker
(`jobs.thread`), never on the overlay thread: the quick panel is a web window
and its creation waits on the UI thread. `on_settle(x, y)` says where a drop
landed (the place worth saving).

Fullscreen and "do not disturb" (`SHQueryUserNotificationState`: busy, a
fullscreen Direct3D game, a presentation) hide the window and stop it moving;
asked every 2 s while it runs, and while it is hidden for that.

Not run on Windows (the sandbox has none): the tests drive a fake `win32`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from tessellate.core import jobs
from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import host as host_mod
from tessellate.core.overlay import sprites
from tessellate.core.overlay import win32 as k

logger = logging.getLogger(__name__)

#: How often to ask whether something fullscreen is in the way (seconds).
BUSY_EVERY = 2.0


class OverlayRunner:
    def __init__(
        self,
        *,
        look: str = "masculine",
        reduced: bool = False,
        home: tuple[int, int] | None = None,
        on_click: Callable[[str, tuple[int, int, int, int], int], Any] | None = None,
        on_settle: Callable[[int, int], Any] | None = None,
        w: Any = None,
        clock: Callable[[], float] = time.monotonic,
        frames: Path | None = None,
        dispatch: Callable[[str, Callable[[], None]], Any] | None = None,
    ) -> None:
        self.look = sprites.look_for(look)
        self.reduced = reduced
        self.home = home
        self.on_click = on_click
        self.on_settle = on_settle
        self.w = w
        self.clock = clock
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
        self._resume = False
        self._last_key: tuple[str, int, bool] | None = None
        self._last_pos: tuple[int, int] | None = None
        self._next_busy_check = 0.0

    # --- life (any thread) ------------------------------------------------------------

    def start(self, timeout: float = 3.0) -> bool:
        """Make the window and the engine. False (and logged) when either fails:
        the coordinator then falls back to the card window."""
        try:
            if self.w is None:
                self.w = k.load()
            self.host = host_mod.OverlayHost(self.w, on_event=self._on_event)
            ok = self.host.start(timeout)
        except Exception:  # noqa: BLE001 - any failure means the card window instead
            logger.warning("overlay: could not start", exc_info=True)
            return False
        if not ok:
            self.stop()
        return ok

    def show(self) -> None:
        self.visible = True
        self._resume = True
        if self.host:
            self.host.show()
            self.host.wake(1)

    def hide(self) -> None:
        self.visible = False
        if self.host:
            self.host.hide()

    def stop(self) -> None:
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
            hold = self._busy_gate(now)
            if hold is not None:
                return hold
        if kind not in ("tick", "display"):
            return None
        return self._apply(engine.update(now, pointer))

    def _busy_gate(self, now: float) -> int | None:
        """Hide while something fullscreen is in the way; None when free to move."""
        if now < self._next_busy_check and not self.busy:
            return None
        self._next_busy_check = now + BUSY_EVERY
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
        self._last_key = None

    def _ready(self) -> None:
        """On the overlay thread, once its window exists: monitors in its own
        awareness, the frames, the engine, and the first frame drawn (hidden)."""
        self.monitors = self._read_monitors()
        spr = sprites.SpriteSet(self.look, self.frames)
        if spr.missing():
            raise OSError(f"overlay frames missing: {spr.missing()[:3]}")
        self.sprites = spr
        reduced = self.reduced or not k.animations_enabled(self.w)
        first = self.monitors[0]
        self.dpi = first.dpi
        self.engine = eng.Engine(spr.size(first.dpi), self.monitors, home=self.home, reduced=reduced, now=self.clock())
        out = self.engine.update(self.clock())
        self._apply(out)
        logger.info(
            "overlay: ready, look=%s, monitors=%s, frames=%d at %s px, reduced=%s",
            self.look, [(m.area, m.dpi) for m in self.monitors], len(sprites.FRAME_NAMES), spr.size(first.dpi), reduced,
        )

    def _apply(self, out: eng.Output) -> int | None:
        engine, spr, host = self.engine, self.sprites, self.host
        assert engine is not None and spr is not None and host is not None
        dpi = engine.current_monitor().dpi
        if dpi != self.dpi:
            self.dpi = dpi
            engine.set_monitors(self.monitors, spr.size(dpi))
            self._last_key = None
        key = (out.frame, self.dpi, out.flip)
        if key != self._last_key:
            frame = spr.frame(out.frame, self.dpi, out.flip)
            host.present(frame.bgra, frame.width, frame.height, out.x, out.y)
            self._last_key, self._last_pos = key, (out.x, out.y)
        elif (out.x, out.y) != self._last_pos:
            host.move(out.x, out.y)
            self._last_pos = (out.x, out.y)
        if out.click:
            width, height = spr.size(self.dpi)
            self._hand_off("overlay-click", lambda: self.on_click and self.on_click(out.click, (out.x, out.y, width, height), self.dpi))
        if out.settled:
            self._hand_off("overlay-settle", lambda: self.on_settle and self.on_settle(out.x, out.y))
        return out.wake_ms

    def _hand_off(self, name: str, call: Callable[[], Any]) -> None:
        try:
            self._dispatch(name, call)
        except Exception:  # noqa: BLE001 - the pet keeps walking if a click cannot be passed on
            logger.warning("overlay: could not hand off %s", name, exc_info=True)
