"""Source text: the status bar's working ring turns under "Auto" unless the OS
asks for reduced motion, when it breathes; "Still" makes it breathe whatever
the OS says (L415).

Measured on the status bar's `ph:spin` ring with the OS set to reduce and to
no preference: Auto pulsed (1.8s) under reduce and turned (0.9s) otherwise,
Always turned in both. Still turned at 0.9s with the OS at no preference, the
one setting meant to stop it; it now pulses (1.8s) in both.
"""

from __future__ import annotations

from tests._css_paths import CSS_DIR

CSS = (CSS_DIR / "02-chat-graph.css").read_text(encoding="utf-8")


def test_still_breathes_the_ring_like_reduced_motion():
    rule = ':root[data-motion="reduced"]:not([data-progress-motion="always"]) .spinner,\n:root[data-progress-motion="still"] .spinner {\n  animation: spinner-pulse'
    assert rule in CSS
