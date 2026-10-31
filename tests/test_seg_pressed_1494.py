"""INBOX 1494, the owner: "no visual active state on this pill selector" (the
note capture's Note / To-do switch). The well's chosen look was keyed to
`.active` only, and that switch marks its choice with `aria-pressed`, so it
showed none. The class: a `.seg` segment chosen either way is painted, in the
base look and in the flat palettes, and hover never repaints a chosen one."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"
CHOSEN = re.compile(r'\.seg button:is\(\.active, \[aria-pressed="true"\]\)\s*[,{]')


def _rules(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def test_a_pressed_segment_gets_the_chosen_ground():
    css = _rules("03-dashboard-widgets.css")
    match = CHOSEN.search(css)
    assert match, "the .seg chosen rule must match aria-pressed as well as .active"
    body = css[match.end(): css.index("}", match.end())]
    assert "background: var(--accent-surface)" in body


def test_the_flat_palettes_paint_a_pressed_segment_too():
    assert CHOSEN.search(_rules("08-consistency.css"))


def test_hover_never_repaints_a_chosen_segment():
    css = _rules("03-dashboard-widgets.css")
    hovers = re.findall(r"\.seg button:not\(([^)]*)\):hover", css)
    assert hovers and all('[aria-pressed="true"]' in h and ".active" in h for h in hovers), hovers


def test_no_stylesheet_keys_a_seg_choice_to_active_alone():
    for path in CSS.glob("*.css"):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        assert not re.search(r"\.seg button\.active\b", css), path.name
