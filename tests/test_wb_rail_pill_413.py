"""L-world-class-413 (wbrail sweep): the board's tool row is a pill while it is
one line and a card once it wraps. The card rule keyed on the panel having more
than one child, and the phone's hidden Tools opener is a second child, so the
row drew the card radius at every width (measured at 1440: 8px on a 46px row).
The row's own size observer now marks a real wrap."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend/css/06-timeline-dialogs.css").read_text(encoding="utf-8")
PAN = (ROOT / "frontend/js/whiteboard-pan.js").read_text(encoding="utf-8")


def test_the_card_shape_waits_for_a_real_wrap():
    assert ":has(> :last-child:not(:first-child))" not in CSS
    rule = re.search(r"\.whiteboard-floating-panel\.bottom-center\.wb-rail-wrapped\s*\{([^}]*)\}", CSS)
    assert rule and "var(--radius)" in rule.group(1)


def test_the_size_observer_marks_the_wrap():
    assert 'classList.toggle("wb-rail-wrapped"' in PAN
