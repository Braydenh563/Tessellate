"""INBOX 1683 i, y: peek from behind a bar on any edge and out of any screen edge. The play area's edge is a shown
bar's inner edge, so the clip hides exactly the part under the bar; with no bar the edge is the screen's own. Fake
clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import math
import random
from collections import Counter

import pytest

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay import sprites
from tessellate.core.overlay.engine import Bar, Engine, Monitor

SIZE = (100, 120)
FULL = (0, 0, 1920, 1080)
SQUARE = math.ceil(math.hypot(*SIZE))  # the canvas a turned (upside-down) figure is drawn on
#: edge -> (the bar's rectangle, the play area it leaves)
BARS = {
    "bottom": ((0, 1040, 1920, 1080), (0, 0, 1920, 1040)),
    "top": ((0, 0, 1920, 40), (0, 40, 1920, 1080)),
    "left": ((0, 0, 60, 1080), (60, 0, 1920, 1080)),
    "right": ((1860, 0, 1920, 1080), (0, 0, 1860, 1080)),
}


def monitor(bar_edge: str | None) -> Monitor:
    if bar_edge is None:
        return Monitor(FULL, 96, FULL, ())
    rect, area = BARS[bar_edge]
    return Monitor(area, 96, FULL, (Bar(bar_edge, rect, True),))


def make(bar_edge: str | None, **kw) -> Engine:
    kw.setdefault("hang_top", 0.2)
    e = Engine(SIZE, [monitor(bar_edge)], home=(900, 700), rng=random.Random(5), idle_frames=0, now=0.0, **kw)
    e.update(0.1)
    return e


def peek_to_depth(e: Engine, edge: str, at: float = 2.0) -> eng.Output:
    """Start a peek on `edge`, run until it has been peeking `at` seconds (head showing), return that draw."""
    t = e.now
    e._peek(t, edge)
    out = e.update(t)
    while t < 60.0 and not (e.state == "peek" and t - e.peek_started >= at):
        t += 0.033
        out = e.update(t)
    assert e.state == "peek" and e.peek_edge == edge, (e.state, e.peek_edge)
    return out


def opaque(w: int, h: int) -> sprites.Frame:
    return sprites.Frame(w, h, bytes([200, 100, 50, 255]) * (w * h), 0, 0, (0, 0, w, h))


def alpha_rows_cols(frame: sprites.Frame) -> tuple[set[int], set[int]]:
    rows, cols = set(), set()
    for i in range(frame.width * frame.height):
        if frame.bgra[i * 4 + 3]:
            rows.add(i // frame.width)
            cols.add(i % frame.width)
    return rows, cols


@pytest.mark.parametrize("bar", ["bottom", "left", "right", "top"])
def test_the_clip_hides_exactly_the_part_under_the_bar(bar: str) -> None:
    e = make(bar)
    out = peek_to_depth(e, bar)
    w, h = SIZE
    assert out.clip is not None
    left, top, right, bottom = out.clip
    if bar == "bottom":
        assert out.y + bottom == BARS[bar][0][1]  # the visible rows end where the bar begins
        assert (left, top, right) == (0, 0, w)
    elif bar == "left":
        assert out.x + left == BARS[bar][0][2]  # they begin where the bar ends
        assert (top, right, bottom) == (0, w, h)
    elif bar == "right":
        assert out.x + right == BARS[bar][0][0]
        assert (left, top, bottom) == (0, 0, h)
    else:
        # Intent moved, not weakened (edges2-1108): the top peek is drawn upside-down on the tumble's square canvas, whose
        # clip is in that canvas's pixels, so its origin is the box's less the pad; the edge is still where the strip begins.
        w, h = (SQUARE, SQUARE) if out.frame.startswith("spin") else (w, h)
        assert out.y - (SQUARE - SIZE[1]) // 2 * (w == SQUARE) + top == BARS[bar][0][3]
        assert (left, right, bottom) == (0, w, h)
    rows, cols = alpha_rows_cols(sprites.clipped(opaque(w, h), out.clip))
    visible_rows = set(range(max(0, top), min(h, bottom)))
    visible_cols = set(range(max(0, left), min(w, right)))
    assert rows == visible_rows and cols == visible_cols and 0 < len(rows) * len(cols) < w * h


@pytest.mark.parametrize("bar", ["bottom", "left", "right", "top"])
def test_with_no_bar_the_screen_edge_is_the_edge(bar: str) -> None:
    e = make(None)
    out = peek_to_depth(e, bar)
    assert out.clip is not None
    if bar == "bottom":
        assert out.y + out.clip[3] == FULL[3]
    elif bar == "left":
        assert out.x + out.clip[0] == FULL[0]
    elif bar == "right":
        assert out.x + out.clip[2] == FULL[2]
    else:  # the turned canvas's origin (see the note above)
        assert out.y - (SQUARE - SIZE[1]) // 2 * out.frame.startswith("spin") + out.clip[1] == FULL[1]


@pytest.mark.parametrize("bar", ["bottom", "left", "right", "top"])
def test_a_click_on_the_visible_part_lands_and_brings_it_out(bar: str) -> None:
    e = make(bar)
    out = peek_to_depth(e, bar)
    left, top, right, bottom = out.clip
    px, py = out.x + (max(left, 0) + min(right, SIZE[0])) // 2, out.y + (max(top, 0) + min(bottom, SIZE[1])) // 2
    rows, cols = alpha_rows_cols(sprites.clipped(opaque(*SIZE), out.clip))
    assert (py - out.y) in rows and (px - out.x) in cols  # the point is on a pixel that takes the click
    t = e.now + 0.05
    e.update(t, (px, py), ("down", px, py))
    got = e.update(t + 0.05, (px, py), ("up", px, py))
    assert got.click == "left" or e.click_now == "left" or e.state in ("emerge", "wave", "hang")
    assert e.state in ("emerge", "wave", "hang")


def test_a_pixel_under_the_bar_takes_no_click() -> None:
    e = make("left")
    out = peek_to_depth(e, "left")
    clipped = sprites.clipped(opaque(*SIZE), out.clip)
    hidden_cols = {c for c in range(SIZE[0]) if c < out.clip[0]}
    assert hidden_cols and all(clipped.bgra[(r * SIZE[0] + c) * 4 + 3] == 0 for r in range(SIZE[1]) for c in hidden_cols)


def test_the_figure_ducks_all_the_way_behind_the_bar_and_comes_back() -> None:
    e = make("bottom")
    peek_to_depth(e, "bottom")
    t, sinks = e.now, []
    while e.state == "peek" and t < 30:
        t += 0.033
        e.update(t)
        sinks.append(e.sink)
    assert max(sinks) > 0.99 and e.state == "stand" and e.sink == 0.0


def test_a_top_peek_ends_back_on_its_hands_not_standing_in_the_air() -> None:
    e = make("top")
    peek_to_depth(e, "top")
    t = e.now
    while e.state == "peek" and t < 30:
        t += 0.033
        e.update(t)
    assert e.state == "hang" and e.sink == 0.0 and e.y == BARS["top"][1][1] - e._lift()


def test_a_top_peek_climbs_to_the_ceiling_clipped_behind_the_bar_all_the_way() -> None:
    e = make("top")
    e._peek(0.1, "top")
    t, clips = 0.1, []
    while e.state != "peek" and t < 20:
        t += 0.033
        out = e.update(t)
        if e.state == "rise":
            clips.append((out.y, out.clip))
    assert clips and all(c is not None and out_y + c[1] >= BARS["top"][1][1] - 1 for out_y, c in clips if out_y + c[1] >= 0)


# --- which edge -------------------------------------------------------------------------------------------------------

def table(e: Engine, now: float = 1.0) -> dict[str, float]:
    return dict(e._peek_edges(e.current_monitor(), now))


def test_a_shown_bar_is_a_wanted_place_to_hide_and_a_bare_edge_less_so() -> None:
    with_left = table(make("left"))
    assert with_left["left"] == eng.PEEK_BEHIND and with_left["bottom"] == eng.PEEK_OPEN["bottom"]
    assert set(with_left) == {"bottom", "left", "right", "top"}
    assert table(make(None))["left"] == eng.PEEK_OPEN["left"]


def test_a_bar_that_is_not_shown_is_no_hiding_place() -> None:
    hidden = Monitor(FULL, 96, FULL, (Bar("bottom", BARS["bottom"][0], False),))
    e = Engine(SIZE, [hidden], home=(900, 700), rng=random.Random(5), idle_frames=0, now=0.0, hang_top=0.2)
    e.update(0.1)
    assert table(e)["bottom"] == eng.PEEK_OPEN["bottom"]


def test_the_top_needs_the_window_option_and_a_side_with_no_neighbour() -> None:
    assert "top" not in table(make(None, roam_windows=False))
    right = Monitor((1920, 0, 3840, 1080), 96, (1920, 0, 3840, 1080), ())
    e = Engine(SIZE, [Monitor(FULL, 96, FULL, ()), right], home=(900, 700), rng=random.Random(5), idle_frames=0, now=0.0, hang_top=0.2)
    e.update(0.1)
    assert set(table(e)) == {"bottom", "left", "top"}  # the right side joins the next screen: no edge to look out of


def test_the_mood_bends_the_choice() -> None:
    e = make("left")
    e.mind.feel("startled", 1.0)
    startled = table(e, 1.5)
    assert startled["left"] == eng.PEEK_BEHIND * 2 and startled["bottom"] == eng.PEEK_OPEN["bottom"]
    e.mind.feel("curious", 1.0)
    assert table(e, 1.5)["bottom"] == eng.PEEK_OPEN["bottom"] * 1.5
    e.mind.feel("happy", 1.0)
    assert table(e, 1.5)["top"] == eng.PEEK_OPEN["top"] * 2


def test_the_seeded_choices_cover_every_edge_and_favour_the_bar() -> None:
    e = make("left")
    seen: Counter = Counter()
    e._go = lambda goal, then, now, plain=False: seen.update([then])  # type: ignore[method-assign]
    e._rise = lambda to, then, now, drawn_from=None: seen.update([then])  # type: ignore[method-assign]
    for i in range(600):
        e.rng = random.Random(i)
        e._peek(1.0)
    assert set(seen) == {"peek_bottom", "peek_left", "peek_right", "peek_top"}
    assert seen["peek_left"] > max(seen["peek_right"], seen["peek_top"])
    weights = dict(e._peek_edges(e.current_monitor(), 1.0))
    assert seen["peek_left"] / 600 == pytest.approx(weights["left"] / sum(weights.values()), abs=0.06)


def test_the_taskbar_moving_to_another_edge_moves_the_hiding_place() -> None:
    e = make("bottom")
    assert table(e)["bottom"] == eng.PEEK_BEHIND
    e.set_monitors([monitor("right")])
    after = table(e)
    assert after["right"] == eng.PEEK_BEHIND and after["bottom"] == eng.PEEK_OPEN["bottom"]
    t = e.now
    while e.state != "stand" and t < 10:  # the bottom strip it stood above is free: it falls to the new floor first
        t += 0.033
        e.update(t)
    out = peek_to_depth(e, "right")
    assert out.x + out.clip[2] == BARS["right"][0][0]
