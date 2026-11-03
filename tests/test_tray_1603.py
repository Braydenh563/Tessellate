"""INBOX 1603, the tray: the row body drags, the page holds still over the tray,
the button's icon and count clear its edges, and `t` then `y` opens it.
Measured in the app by scratchpad/ui-sweeps/traymore.js and traystuck.js."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def test_a_tray_row_is_a_grip_for_a_mouse():
    drag = frontend_text("js/obj-drag.js")
    seed = drag[drag.index("function objDragSeed"):drag.index("function objDragArm")]
    assert 'event.target.closest?.(".obj-tray-use")' in seed[seed.index("const quick"):]


def test_the_edge_scroll_holds_over_the_tray():
    drag = frontend_text("js/obj-drag.js")
    tick = drag[drag.index("function objDragTick"):drag.index("function objDragUp")]
    hold = tick.index("objTrayDoor.hit(g.x, g.y)")
    assert hold < tick.index("scrollTop +=")


def test_the_tray_button_pads_its_count():
    css = (ROOT / "frontend" / "css" / "objmove-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index("#status-tray.has-count {"):]
    assert "padding-inline: var(--space-2);" in rule[: rule.index("}")]


def test_t_then_y_opens_the_tray():
    wiring = frontend_text("js/settings-wiring.js")
    actions = wiring[wiring.index("const CHORD_ACTIONS"):wiring.index("let tabJumpArmedAt")]
    assert 'y: { label: "Tray"' in actions and '$("status-tray")?.click()' in actions
    keys = wiring[wiring.index("const TAB_JUMP_KEYS"):wiring.index("const CHORD_ACTIONS")]
    assert "  y:" not in keys
    assert "(t then y)" in frontend_text("index.html")
