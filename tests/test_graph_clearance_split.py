"""L-graph-5, the owner 2026-11-12: "a coarser push if measured dot and label
overlaps stay 0". `clearanceForce` was 28 ms a call at 2,000 notes (66 ms on
this box under load), most of it the hits along long lines. A line longer than
`CLEAR_SPLIT_CELLS` cells now pushes on every second tick at twice the gain.

Measured with the shipped worker under node (`scratchpad/hub/cf.js`): 2,000
notes 66 to 40 ms a call; the twenty 36-note hub seeds 0 overlaps either way
and notes sitting on a line 8 to 7; a 300-note map 0 overlaps, 134 to 117 on a
line. Overlaps are also held by tests/test_graph_hub_crossings.py."""

from __future__ import annotations

from pathlib import Path

WORKER = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-worker.js").read_text(encoding="utf-8")


def test_a_long_line_pushes_every_second_tick_at_twice_the_gain() -> None:
    body = WORKER[WORKER.index("function clearanceForce()") :]
    body = body[: body.index("\n}\n")]
    assert "const CLEAR_SPLIT_CELLS = 3;" in WORKER
    assert "if (!clearSplitTurn(a, b)) continue;" in body
    turn = WORKER[WORKER.index("function clearSplitTurn(a, b)") :]
    turn = turn[: turn.index("\n}\n")]
    # Twice the tick's gain, so the lean stretch's own doubling still applies on top.
    assert "clear.push = split ? clear.gain * 2 : clear.gain;" in turn
    assert "(clear.tick + a.index + b.index) % 2 === 0" in turn
