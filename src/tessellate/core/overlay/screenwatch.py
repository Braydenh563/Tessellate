"""What happens on the screen that the desk figure may answer (INBOX 1683 ask M6: "react to events on my computer
and the ui on my screen"): the foreground app changing, a window opening or closing, the hour, the battery running
low, a download finishing. Pure bookkeeping over what the runner reads (counts, ids and a folder's file count,
never a title or a file name), returning event kinds for `Engine.react`. One poll every `EVERY` seconds.
"""

from __future__ import annotations

import logging
import os
from itertools import islice
from pathlib import Path
from typing import Any, Callable

#: No count has come back since the last poll (a count can come back as None: no folder).
_UNSET: Any = object()

logger = logging.getLogger(__name__)

EVERY = 2.0
#: A window that moved this many px between two scans, twice running, is being dragged.
DRAG_MIN = 24
#: Battery percent that is low, and the one it must climb back past before it can say so again.
LOW, RECOVERED = 20, 30
#: A download folder entry still being written ends in one of these.
#: The folder is looked at this many entries deep and this often (a huge folder costs a bounded read, rarely).
SCAN_CAP, DOWNLOADS_EVERY = 3000, 10.0
#: Input older than this (s, ten minutes: the figure's sit, `engine.IDLE_SIT`) is an absence, and the next input is the person coming back.
AWAY_AFTER = 600.0
#: ...and input this fresh (s, a few reads of the 0.5 Hz typing check) is the return.
BACK_WITHIN = 5.0
PARTIAL = (".crdownload", ".part", ".tmp", ".download", ".partial")
#: The part of the day (INBOX 1719 b; the catalogue's `phases`): the hour dusk falls (its chime is `night_falls`, a stretch)
#: and the morning's hours, in which the day's first input (or the first back from an absence) is `morning_hello`.
DUSK, MORNING = 17, (6, 11)
#: Typing this long (s, gaps under `BURST_GAP` s) that then rests `BURST_GAP` s is a burst finished (`typing_burst`, a nod).
BURST_MIN, BURST_GAP = 30.0, 4.0
#: ...and a run this long is a writing run ended (`writing_stretch`, a stretch: Brief 88 N9, L-chat-7).
WRITING_RUN = 60.0


def downloads_count(folder: Path | None = None) -> int | None:
    """How many finished files the downloads folder holds (None when there is none to read)."""
    folder = folder or Path.home() / "Downloads"
    try:
        with os.scandir(folder) as it:
            return sum(1 for e in islice(it, SCAN_CAP) if e.is_file() and not e.name.lower().endswith(PARTIAL))
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
        downloads: Callable[[], int | None] = downloads_count, run: Callable[[Callable[[], None]], Any] | None = None,
        feed: Callable[[int], list[dict]] | None = None,
    ) -> None:
        self.foreground, self.battery, self.downloads = foreground, battery, downloads
        #: What the app's server noted since an id (`core.companion_events.since`): kinds and times, read on this poll
        #: only (W31). `_fed` is the newest id read; None until the first read, which is only remembered (history).
        self.feed = feed
        self._fed: int | None = None
        #: Where the folder is counted: the runner hands it to a worker (a sleeping or synced folder must not stall a
        #: frame, the 1678 review); none runs it in the poll.
        self.run = run or (lambda fn: fn())
        self._counting = False
        self._counted: Any = _UNSET
        self.next_at = 0.0
        self.fg: int | None = None
        self.windows: set[int] | None = None
        #: key -> (frame, maximised, steps moved in a row) of the last scan, for a drag and a maximise.
        self.frames: dict[int, tuple[tuple[int, int, int, int], bool, int]] | None = None
        self.hour: int | None = None
        self.low = False
        self.files: int | None = None
        self.files_at = 0.0
        self.away = False
        #: The day (of the year) of the last morning hello, the day the last poll read, and the typing run under way.
        self.hello_day: int | None = None
        self.day: int | None = None
        self.burst: tuple[float, float] | None = None  # (first key, last key) of the run
        #: The window (its key) the last event of each kind was about, so the figure can look toward it (INBOX 1700).
        self.subject: dict[str, int] = {}

    def input_seen(self, now: float, age: float | None) -> list[str]:
        """The seconds since the last key or mouse input anywhere (None: unreadable). Said once when input comes back
        after `AWAY_AFTER` s without any: the figure's welcome back. Only the age is used, never what was typed."""
        if age is None:
            return []
        first = self.day is not None and self.hello_day != self.day and self.hour is not None and MORNING[0] <= self.hour < MORNING[1]
        if age >= AWAY_AFTER:
            self.away = True
        elif (self.away or first) and age < BACK_WITHIN:
            self.away = False
            if first:  # the first of the morning: a wave and a yawn, which is also the welcome back
                self.hello_day = self.day
                return ["morning_hello"]
            return ["idle_return"]
        return []

    def typing_seen(self, now: float, typing: bool) -> list[str]:
        """Whether keys are going in now (the runner's 0.5 Hz read): a run of `BURST_MIN` s that has rested `BURST_GAP` s is
        said once (`typing_burst`). Only that keys went in, never which."""
        if typing:
            first = self.burst[0] if self.burst and now - self.burst[1] < BURST_GAP else now
            self.burst = (first, now)
            return []
        if self.burst and now - self.burst[1] >= BURST_GAP:
            first, last = self.burst
            self.burst = None
            ran = last - first
            return ["writing_stretch"] if ran >= WRITING_RUN else ["typing_burst"] if ran >= BURST_MIN else []
        return []

    def windows_seen(self, keys: Any) -> list[str]:
        """The window list a scan read: what opened and closed since the last one (the first is only remembered)."""
        seen = set(keys)
        out: list[str] = []
        if self.windows is not None:
            if seen - self.windows:
                out.append("window_opened")
                self.subject["window_opened"] = max(seen - self.windows)
            if self.windows - seen:
                out.append("window_closed")
        self.windows = seen
        return out

    def states_seen(self, wins: Any) -> list[str]:
        """What the windows did since the last scan (B7): one dragged (it moved on two scans running with its size
        unchanged, said once per drag), one maximised, one put back. Keys, frames and flags only, never a title."""
        now: dict[int, tuple[tuple[int, int, int, int], bool, int]] = {}
        out: list[str] = []
        before = self.frames
        for w in wins:
            rect, zoomed = tuple(w.rect), bool(w.hang)
            steps = 0
            old = before.get(w.key) if before is not None else None
            if old is not None:
                (ol, ot, orr, ob), was_zoomed, was_steps = old
                same_size = (orr - ol, ob - ot) == (rect[2] - rect[0], rect[3] - rect[1])
                moved = same_size and (abs(rect[0] - ol) + abs(rect[1] - ot)) >= DRAG_MIN
                steps = was_steps + 1 if moved else 0
                said = ["window_dragged"] if steps == 2 else []
                if zoomed and not was_zoomed:
                    said.append("window_maximised")
                elif was_zoomed and not zoomed:
                    said.append("window_restored")
                out += said
                self.subject.update({kind: w.key for kind in said})
            now[w.key] = (rect, zoomed, steps)  # type: ignore[assignment]
        self.frames = now
        return out

    def forget(self) -> None:
        """After a stall (a suspend, a full-screen app): what changed while away is not news, so the next
        reads are only remembered."""
        self.fg, self.windows, self.frames, self.files, self._counted = None, None, None, None, _UNSET
        self._fed = None

    def poll(self, now: float, hour: int, minute: int = 0, screen: bool = True, day: int | None = None) -> list[str]:
        """The events of this tick (empty before `EVERY` has passed). `screen` False (the person turned
        "Roam over windows" off) reads neither the foreground window nor the downloads folder."""
        if now < self.next_at:
            return []
        self.next_at = now + EVERY
        out: list[str] = []
        if screen:
            out += self._foreground()
        else:
            self.fg, self.files, self._counted = None, None, _UNSET
        if day is not None:
            self.day = day
        if self.hour is not None and hour != self.hour and minute < 2:
            out.append("night_falls" if hour == DUSK else "hour_chime")
        if self.hour is None or minute < 2:
            self.hour = hour
        out += self._battery()
        if screen:
            out += self._downloads(now)
        return out + self._fed_events()

    def _fed_events(self) -> list[str]:
        """The notebook's own events since the last poll (a note binned, a search that found nothing...); the first read after
        a start or a `forget` is only remembered, and an unreadable feed is no event."""
        if self.feed is None:
            return []
        try:
            rows = self.feed(self._fed or 0)
        except Exception:  # noqa: BLE001 - the feed is a courtesy
            logger.debug("overlay: the app's event feed is unreadable", exc_info=True)
            return []
        first = self._fed is None
        if rows:
            self._fed = max(r["id"] for r in rows)
        elif first:
            self._fed = 0
        return [] if first else [r["kind"] for r in rows]

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

    def _downloads(self, now: float) -> list[str]:
        if now >= self.files_at and not self._counting:
            self.files_at = now + DOWNLOADS_EVERY
            self._counting = True
            try:
                self.run(self._count)
            except Exception:  # noqa: BLE001 - no worker to count on (thread start refused) is no event
                #: `_count` never ran, so nothing else would clear the flag and
                #: the folder would never be counted again.
                self._counting = False
                logger.debug("overlay: downloads count not started", exc_info=True)
        if self._counted is _UNSET:
            return []
        n, self._counted = self._counted, _UNSET
        out = ["download_done"] if n is not None and self.files is not None and n > self.files else []
        self.files = n
        return out

    def _count(self) -> None:
        try:
            n = self.downloads()
        except Exception:  # noqa: BLE001 - an unreadable folder is no event
            logger.debug("overlay: downloads unreadable", exc_info=True)
            n = None
        self._counted = n
        self._counting = False
