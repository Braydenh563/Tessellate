"""A fake X connection (`xlib.XConn`'s surface) for the Linux overlay's tests: records what is
drawn, moved, mapped and raised, answers EWMH properties from a dict, and delivers injected
events through a real pipe so `X11Host` runs its `select` loop on a thread as it would."""

from __future__ import annotations

import os
import threading
from typing import Any


class FakeX:
    def __init__(self, cursor: tuple[int, int] = (500, 400)) -> None:
        self.root = 1
        self.compositor = True
        self.calls: list[tuple[Any, ...]] = []
        self.presented: list[dict[str, Any]] = []
        self.cursor = cursor
        self.monitor_list = [(0, 0, 1920, 1080)]
        self.dpi: float | None = None
        self.idle: int | None = None
        #: {window or root: {property name: value}}; `geo` is a window's client rectangle.
        self.props: dict[int, dict[str, Any]] = {self.root: {}}
        self.geo: dict[int, tuple[int, int, int, int]] = {}
        self._rd, self._wr = os.pipe()
        self._events: list[tuple[str, int, int]] = []
        self._lock = threading.Lock()
        self.window = 0
        self.closed = False
        self.fail_create = False

    # --- the surface the host and the readers use --------------------------------------------

    def fileno(self) -> int:
        return self._rd

    def inject(self, kind: str, x: int = 0, y: int = 0) -> None:
        with self._lock:
            self._events.append((kind, x, y))
        os.write(self._wr, b"e")

    def events(self) -> list[tuple[str, int, int]]:
        with self._lock:
            out, self._events = self._events, []
        if out:
            try:
                os.read(self._rd, 4096)
            except OSError:
                pass  # nothing left to drain (the wake pipe is non-blocking): the events are the answer
        return out

    def create_window(self, title: str) -> int:
        self.calls.append(("create", title))
        if self.fail_create:
            raise OSError("no display")
        self.window = 4242
        return self.window

    def present(self, win: int, bgra: bytes, width: int, height: int, x: int, y: int) -> None:
        self.calls.append(("present", win, width, height, x, y))
        self.presented.append({"bgra": bgra, "w": width, "h": height, "x": x, "y": y})

    def redraw(self, win: int) -> None:
        self.calls.append(("redraw", win))

    def move(self, win: int, x: int, y: int) -> None:
        self.calls.append(("move", win, x, y))

    def map(self, win: int) -> None:
        self.calls.append(("map", win))

    def unmap(self, win: int) -> None:
        self.calls.append(("unmap", win))

    def raise_window(self, win: int) -> None:
        self.calls.append(("raise", win))

    def destroy(self, win: int) -> None:
        self.calls.append(("destroy", win))

    def grab_pointer(self, win: int) -> None:
        self.calls.append(("grab", win))

    def ungrab_pointer(self) -> None:
        self.calls.append(("ungrab",))

    def pointer(self) -> tuple[int, int]:
        return self.cursor

    def close(self) -> None:
        self.closed = True

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]

    # --- what the desktop says -----------------------------------------------------------------

    def prop(self, win: int, name: str, max_items: int = 4096) -> Any:
        return self.props.get(win, {}).get(name)

    def geometry(self, win: int) -> tuple[int, int, int, int] | None:
        return self.geo.get(win)

    def rr_monitors(self) -> list[tuple[int, int, int, int]]:
        return list(self.monitor_list)

    def resource_dpi(self) -> float | None:
        return self.dpi

    def idle_ms(self) -> int | None:
        return self.idle

    def screen_size(self) -> tuple[int, int]:
        m = self.monitor_list
        return max(a + c for a, _b, c, _d in m), max(b + d for _a, b, _c, d in m)

    # --- building a desktop ---------------------------------------------------------------------

    def add_window(self, win: int, rect: tuple[int, int, int, int], *, title: str = "App", pid: int = 1, state: list[str] | None = None,
                   kinds: list[str] | None = None, desktop: int = 0, extents: tuple[int, int, int, int] | None = None) -> None:
        """Put a client window on top of the stack. `rect` is its client area (x, y, w, h)."""
        self.geo[win] = rect
        p: dict[str, Any] = {"_NET_WM_NAME": title, "_NET_WM_PID": [pid], "_NET_WM_DESKTOP": [desktop], "_NET_WM_STATE": list(state or [])}
        if kinds:
            p["_NET_WM_WINDOW_TYPE"] = list(kinds)
        if extents:
            p["_NET_FRAME_EXTENTS"] = list(extents)
        self.props[win] = p
        self.props[self.root].setdefault("_NET_CLIENT_LIST_STACKING", []).append(win)
        self.props[self.root].setdefault("_NET_CLIENT_LIST", []).append(win)
        self.props[self.root].setdefault("_NET_CURRENT_DESKTOP", [0])
