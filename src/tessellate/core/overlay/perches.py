"""Window tops worth standing on, from a scan of the visible windows (roam).

Pure: `top_edges` takes what `win32.windows` read (topmost first) and returns,
for each window that may be stood on, the widest stretch of its top edge that
no window above it covers. A window above another one hides the part of the
lower one's top edge it overlaps, so the figure would be standing on nothing
the person can see. Nothing here touches Windows or any window.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from tessellate.core.overlay.engine import Cover, Perch
from tessellate.core.overlay.win32 import WinInfo


def _cut(spans: list[tuple[int, int]], lo: int, hi: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in spans:
        if hi <= a or lo >= b:
            out.append((a, b))
            continue
        if lo > a:
            out.append((a, lo))
        if hi < b:
            out.append((hi, b))
    return out


def top_edges(wins: Iterable[WinInfo], min_width: int, drops: Counter | None = None) -> list[Perch]:
    """`drops`, when given, counts why a standable window's top gave no perch (never a title)."""
    ordered = list(wins)
    found: list[Perch] = []
    for i, win in enumerate(ordered):
        if not win.perch:
            continue
        left, top, right, _bottom = win.rect
        spans = [(left, right)]
        by_tool = False
        for above in ordered[:i]:
            if not above.solid:  # a full-monitor layered window hides no top
                continue
            al, at, ar, ab = above.rect
            if at <= top < ab:  # the line the figure would stand on passes through it
                cut = _cut(spans, al, ar)
                by_tool = by_tool or (cut != spans and not above.perch)
                spans = cut
        wide = [s for s in spans if s[1] - s[0] >= min_width]
        if wide:
            a, b = max(wide, key=lambda s: s[1] - s[0])
            found.append(Perch(win.key, a, top, b))
        elif drops is not None:
            drops["covered by a tool window" if by_tool and not spans else "covered by a window" if not spans else "too narrow"] += 1
    return found


def hang_spots(wins: Iterable[WinInfo], min_width: int) -> list[Perch]:
    """Edges worth hanging from that are not a window's top: a maximised window's title bar (its top edge, kind
    "bar") and the bottom edge of a window that can be stood on (kind "bottom", the key negated so it never meets
    the window's own). Each is the widest stretch no window above it covers (INBOX 1683 w)."""
    ordered = list(wins)
    found: list[Perch] = []
    for i, win in enumerate(ordered):
        if not (win.hang or win.perch):
            continue
        left, top, right, bottom = win.rect
        kind, line, key = ("bar", top, win.key) if win.hang else ("bottom", bottom, -win.key)
        spans = [(left, right)]
        for above in ordered[:i]:
            al, at, ar, ab = above.rect
            if above.solid and at <= line < ab:
                spans = _cut(spans, al, ar)
        spans = [s for s in spans if s[1] - s[0] >= min_width]
        if spans:
            a, b = max(spans, key=lambda s: s[1] - s[0])
            found.append(Perch(key, a, line, b, kind))
    return found


def tuck_spots(wins: Iterable[WinInfo], min_size: int) -> list[Cover]:
    """The windows a figure may tuck behind the side of (INBOX 1683 k): each window it could stand on, at least
    `min_size` each way, with the rectangles of the solid windows above it that overlap it (a window drawn over its
    edge hides the figure's cover). The engine judges the side, the reach and the room."""
    ordered = list(wins)
    found: list[Cover] = []
    for i, win in enumerate(ordered):
        left, top, right, bottom = win.rect
        if not win.perch or right - left < min_size or bottom - top < min_size:
            continue
        above = tuple(
            a.rect for a in ordered[:i]
            if a.solid and a.rect[0] < right and left < a.rect[2] and a.rect[1] < bottom and top < a.rect[3]
        )
        found.append(Cover(win.key, win.rect, above))
    return found
