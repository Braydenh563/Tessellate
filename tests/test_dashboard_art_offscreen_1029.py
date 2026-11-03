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

# The constellation moved to the lazy dash-art.js (INBOX 1530 d), inside an IIFE.
SOURCE = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dash-art.js").read_text(encoding="utf-8")
SKETCH = SOURCE[SOURCE.index("const sketch = (p) =>") : SOURCE.index("artInstance = live ? new p5(sketch, holder)")]


def test_the_sketch_watches_whether_its_card_is_in_view():
    assert "new IntersectionObserver(" in SKETCH
    assert "sight.observe(holder)" in SKETCH
    # Torn down with the sketch, as the ResizeObserver is.
    assert "sight.disconnect()" in SKETCH


def test_a_draw_while_out_of_view_stops_the_loop():
    draw = SKETCH[SKETCH.index("p.draw = () => {") :]
    assert re.search(r"if \(hiddenSince\) \{\s*p\.noLoop\(\);\s*return;", draw[:200])


def test_coming_back_moves_the_clock_on_and_restarts_only_while_attended():
    """INBOX 1501: coming back to a card nobody is looking at draws no frame (a
    Dashboard click cost the art a 7 to 18 ms frame thirty times a second at 4x);
    the loop starts again only inside the attention window, and a rest keeps its
    own count of the time away, so the clock is not moved on twice."""
    sight = SKETCH[SKETCH.index("const sight = new IntersectionObserver(") :]
    sight = sight[: sight.index("sight.observe(holder)")]
    assert "if (!p.rested) artClock.epoch += performance.now() - hiddenSince" in sight
    assert "if (!p.rested) performance.now() > attendUntil ? rest() : p.loop();" in sight
