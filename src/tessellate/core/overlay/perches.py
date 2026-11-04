"""Window tops worth standing on, from a scan of the visible windows (roam).

Pure: `top_edges` takes what `win32.windows` read (topmost first) and returns,
for each window that may be stood on, the widest stretch of its top edge that
no window above it covers. A window above another one hides the part of the
lower one's top edge it overlaps, so the figure would be standing on nothing
the person can see. Nothing here touches Windows or any window.
"""

from __future__ import annotations

from typing import Iterable

from tessellate.core.overlay.engine import Perch
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


def top_edges(wins: Iterable[WinInfo], min_width: int) -> list[Perch]:
    ordered = list(wins)
    found: list[Perch] = []
    for i, win in enumerate(ordered):
        if not win.perch:
            continue
        left, top, right, _bottom = win.rect
        spans = [(left, right)]
        for above in ordered[:i]:
            al, at, ar, ab = above.rect
            if at <= top < ab:  # the line the figure would stand on passes through it
                spans = _cut(spans, al, ar)
        spans = [s for s in spans if s[1] - s[0] >= min_width]
        if spans:
            a, b = max(spans, key=lambda s: s[1] - s[0])
            found.append(Perch(win.key, a, top, b))
    return found
