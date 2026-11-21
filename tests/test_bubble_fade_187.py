"""L-chat-187 (the owner: "Composer responses just appear, I think there should be an animation or smooth
transition"): every bubble fades in from nothing, and the fade is gone with reduced motion or Interface
animations off. The bubble's opacity over time is measured in the live app (`scratchpad/ui-sweeps`), not here."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path("frontend/css")


def _text(name: str) -> str:
    return (CSS / name).read_text(encoding="utf-8")


def test_a_bubble_arrives_from_transparent_to_opaque():
    css = _text("03-dashboard-widgets.css")
    keyframes = re.search(r"@keyframes msg-in \{(.*?)\n\}", css, re.S).group(1)
    assert re.search(r"from \{[^}]*opacity: 0", keyframes) and re.search(r"to \{[^}]*opacity: 1", keyframes)
    assert re.search(r"\.msg \{[^}]*animation: msg-in var\(--ui-slow\)", css, re.S)


def test_reduced_motion_stills_the_fade_and_the_slow_step_is_zero_when_animations_are_off():
    still = _text("motion-still.css")
    rule = re.search(r':root\[data-motion="reduced"\] \*:where\(.*?\{(.*?)\}', still, re.S).group(1)
    assert "animation-duration: 0.001ms !important" in rule
    #: The exemptions in that selector are menus, popovers and toasts; a message bubble is not among them.
    selector = re.search(r':root\[data-motion="reduced"\] \*:where\((.*?)\) \{|:root\[data-motion="reduced"\] \*:where\((.*?)\),\n', still, re.S).group(0)
    assert ".msg" not in selector
    tokens = _text("00-tokens-shell.css")
    assert re.search(r'data-ui-motion="off"[^{]*\{[^}]*--ui-slow: 0s', tokens, re.S)
