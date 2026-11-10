"""Edges-1107 "Left" (INBOX 1683 x, y): the top peek is an upside-down figure peering down from behind the top edge, not a
hang climbing up. The pose is flipped (the half-turned picture and its angle), the turn is made out of sight, and the
clip strip keeps everything above the work area's top clear. Fake clock, no Win32; real Windows is unverified."""

from __future__ import annotations

import math

from tessellate.core.overlay import engine as eng
from tests.test_overlay_peek_edges_1107 import BARS, SIZE, make

W, H = SIZE
TOP = BARS["top"][1][1]  # the work area's top, below the bar
SIDE = math.ceil(math.hypot(W, H))
PAD_Y = (SIDE - H) // 2


def run_peek(step: float = 0.033):
    """Every draw of a whole top peek: (seconds into it, output)."""
    e = make("top")
    t = e.now
    e._peek(t, "top")
    seen = []
    started = None
    while t < 60.0:
        t += step
        out = e.update(t)
        if e.state == "peek" and started is None:
            started = e.peek_started
        if started is not None and e.state != "peek":
            break  # the draw that ends it is a plain hang on its hands
        if started is not None:
            seen.append((t - started, out))
    return e, seen


def visible_rows(out: eng.Output) -> int:
    """The rows of the figure's own box that show below the work area's top (the clip is in canvas pixels)."""
    if out.frame.startswith("spin"):
        return max(0, out.y + H - TOP)
    return max(0, H - out.clip[1]) if out.clip else H


def test_the_top_peek_turns_the_figure_upside_down() -> None:
    _e, seen = run_peek()
    flips = [(t, o) for t, o in seen if o.frame == "spin24"]
    assert flips and all(o.angle == math.pi for _t, o in flips)
    assert all(o.angle is None for _t, o in seen if o.frame != "spin24")
    # hanging first, upside-down in the middle, hanging again at the end: the pose is not only hung
    assert seen[0][1].frame == "hang" and seen[-1][1].frame == "hang"  # pulled up hanging, and lowered hanging
    assert min(t for t, _o in flips) > 0.5 and max(t for t, _o in flips) < 7.8


def test_the_turn_is_made_out_of_sight_both_ways() -> None:
    _e, seen = run_peek(0.01)
    swaps = [(a, b) for (_ta, a), (_tb, b) in zip(seen, seen[1:]) if a.frame != b.frame]
    assert len(swaps) == 2
    for before, after in swaps:
        assert visible_rows(before) <= 2 and visible_rows(after) <= 2, (before, after)


def test_it_peers_down_with_its_head_below_the_edge_and_the_body_behind_it() -> None:
    _e, seen = run_peek()
    held = [o for t, o in seen if 2.3 <= t <= 6.0]
    assert held and all(o.frame == "spin24" for o in held)
    for o in held:
        shown = round(eng.PEEK_TOP_PEER * H)
        assert o.y == TOP - H + shown  # the lower part of the turned box is below the edge: the head
        assert o.clip == (0, TOP - o.y + PAD_Y, SIDE, SIDE)  # nothing of the canvas above the edge shows
        assert visible_rows(o) == shown


def test_nothing_is_drawn_above_the_top_edge_at_any_draw() -> None:
    _e, seen = run_peek(0.02)
    for t, o in seen:
        if t < 0.05:  # the draw that entered the peek is the climb's last
            continue
        pad = PAD_Y if o.frame.startswith("spin") else 0
        first = o.y - pad + (o.clip[1] if o.clip else 0)
        assert first >= TOP - 1 or (o.clip and o.clip[1] >= (SIDE if pad else H)), (o.frame, o.y, o.clip)


def test_it_ends_back_on_its_hands() -> None:
    e, seen = run_peek()
    assert e.state == "hang" and e.sink == 0.0 and not e.peek_flip and e.peek_show == 0.0
    assert e.y == TOP - e._lift()


def test_a_peek_cut_short_leaves_nothing_turned() -> None:
    e = make("top")
    e._peek(e.now, "top")
    t = e.now
    while not e.peek_flip and t < 20:
        t += 0.033
        e.update(t)
    assert e.state == "peek" and e.peek_flip
    e._enter("stand", t)
    assert not e.peek_flip and e.peek_show == 0.0
    assert e.update(t + 0.1).angle is None
