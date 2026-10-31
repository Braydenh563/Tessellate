"""Audit 1029 row 38: the Dashboard's constellation rests while scrolled away.

The scene was the largest idle cost on a long Dashboard (185 ms of every 3 s
at 1x) whether or not its card was on screen. An IntersectionObserver on the
holder stops the loop while the card is out of view and starts it again, with
the drift clock moved on by the time away, when it returns. Measured with a
Playwright sweep at 1440x500: 60 frames in 2 s in view, 0 scrolled away, 60
back in view.
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
SKETCH = SOURCE[SOURCE.index("const sketch = (p) =>") : SOURCE.index("artInstance = new p5(sketch, holder);")]


def test_the_sketch_watches_whether_its_card_is_in_view():
    assert "new IntersectionObserver(" in SKETCH
    assert "sight.observe(holder)" in SKETCH
    # Torn down with the sketch, as the ResizeObserver is.
    assert "sight.disconnect()" in SKETCH


def test_a_draw_while_out_of_view_stops_the_loop():
    draw = SKETCH[SKETCH.index("p.draw = () => {") :]
    assert re.search(r"if \(hiddenSince\) \{\s*p\.noLoop\(\);\s*return;", draw[:200])


def test_coming_back_moves_the_clock_on_and_restarts_unless_idle():
    sight = SKETCH[SKETCH.index("const sight = new IntersectionObserver(") :]
    sight = sight[: sight.index("sight.observe(holder)")]
    assert "artClock.epoch += performance.now() - hiddenSince" in sight
    # The idle rest has its own wake (any input); this one must not undo it.
    assert "if (!p.rested) p.loop();" in sight
