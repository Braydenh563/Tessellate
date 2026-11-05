"""What happens on the screen that the desk figure may answer (INBOX 1683 ask M6: "react to events on my computer
and the ui on my screen"): the foreground app changing, a window opening or closing, the hour, the battery running
low, a download finishing. Pure bookkeeping over what the runner reads (counts, ids and a folder's file count,
never a title or a file name), returning event kinds for `Engine.react`. One poll every `EVERY` seconds.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

EVERY = 2.0
#: Battery percent that is low, and the one it must climb back past before it can say so again.
LOW, RECOVERED = 20, 30
#: A download folder entry still being written ends in one of these.
PARTIAL = (".crdownload", ".part", ".tmp", ".download", ".partial")


def downloads_count(folder: Path | None = None) -> int | None:
    """How many finished files the downloads folder holds (None when there is none to read)."""
    folder = folder or Path.home() / "Downloads"
    try:
        with os.scandir(folder) as it:
            return sum(1 for e in it if e.is_file() and not e.name.lower().endswith(PARTIAL))
    except OSError:
        return None


def battery_sysfs() -> tuple[int, bool] | None:
    """`(percent, on_mains)` from /sys/class/power_supply, for the platforms with no call of their own."""
    base = Path("/sys/class/power_supply")
    try:
        for bat in sorted(base.glob("BAT*")):
            pct = int((bat / "capacity").read_text().strip())
            state = (bat / "status").read_text().strip().lower()
            return pct, state in ("charging", "full")
    except (OSError, ValueError):
        return None
    return None


class ScreenWatch:
    """Remembers the last poll and says what changed since."""

    def __init__(
        self, foreground: Callable[[], int | None] | None = None, battery: Callable[[], tuple[int, bool] | None] | None = None,
        downloads: Callable[[], int | None] = downloads_count,
    ) -> None:
        self.foreground, self.battery, self.downloads = foreground, battery, downloads
        self.next_at = 0.0
        self.fg: int | None = None
        self.windows: set[int] | None = None
        self.hour: int | None = None
        self.low = False
        self.files: int | None = None

    def windows_seen(self, keys: Any) -> list[str]:
        """The window list a scan read: what opened and closed since the last one (the first is only remembered)."""
        seen = set(keys)
        out: list[str] = []
        if self.windows is not None:
            if seen - self.windows:
                out.append("window_opened")
            if self.windows - seen:
                out.append("window_closed")
        self.windows = seen
        return out

    def poll(self, now: float, hour: int, minute: int = 0) -> list[str]:
        """The events of this tick (empty before `EVERY` has passed)."""
        if now < self.next_at:
            return []
        self.next_at = now + EVERY
        out: list[str] = []
        out += self._foreground()
        if self.hour is not None and hour != self.hour and minute < 2:
            out.append("hour_chime")
        if self.hour is None or minute < 2:
            self.hour = hour
        out += self._battery()
        out += self._downloads()
        return out

    def _foreground(self) -> list[str]:
        if self.foreground is None:
            return []
        try:
            fg = self.foreground()
        except Exception:  # noqa: BLE001 - an unreadable foreground is no event
            logger.debug("overlay: foreground unreadable", exc_info=True)
            return []
        changed = self.fg is not None and bool(fg) and fg != self.fg
        self.fg = fg or self.fg
        return ["app_switched"] if changed else []

    def _battery(self) -> list[str]:
        if self.battery is None:
            return []
        try:
            got = self.battery()
        except Exception:  # noqa: BLE001
            logger.debug("overlay: battery unreadable", exc_info=True)
            return []
        if got is None:
            return []
        pct, mains = got
        if mains or pct >= RECOVERED:
            self.low = False
            return []
        if pct <= LOW and not self.low:
            self.low = True
            return ["battery_low"]
        return []

    def _downloads(self) -> list[str]:
        n = self.downloads()
        out = ["download_done"] if n is not None and self.files is not None and n > self.files else []
        self.files = n
        return out
