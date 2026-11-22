"""A laser pointer while presenting (INBOX 797, canvasdepth; Excalidraw's and
tldraw's; WHITEBOARD_PLAN "canvasdepth, ranked" row 9). L or the bar's
button; the trail fades by CSS, so no frame loop is added (the wake-source
ratchet holds whiteboard.js's count), and nothing is drawn on the board. The
browser half is `scratchpad/ui-sweeps/wblaser.js`."""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start)]


def test_the_laser_is_wired_and_ends_with_the_presentation():
    assert "wbPresentLaser(false)" in _body("wbStopPresenting")
    assert "wbPresentLaserButton()" in _body("wbStartPresenting")
    trail = _body("wbLaserTrail")
    assert "requestAnimationFrame" not in trail and "animationend" in trail
    assert 'event.key === "l"' in WB


def test_the_trail_fades_by_itself_and_respects_reduced_motion():
    assert "@keyframes wb-laser-fade" in CSS
    reduced = CSS[CSS.index("@keyframes wb-laser-fade") :]
    assert '[data-motion="reduced"]' in reduced


def test_the_laser_has_a_steady_head_and_the_count_cell_is_fixed():
    assert "wb-laser-head" in _body("wbLaserTrail") and "pointerleave" in WB
    assert ".wb-laser-head" in CSS
    misc = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    cell = misc[misc.index(".wb-present-count {") :].split("}")[0]
    assert "width: min(" in cell


def test_the_laser_has_a_menu_for_its_look_and_it_is_remembered():
    """INBOX 1577: a kebabMenu beside the button; trail on or off, four looks, a colour from
    the board's palette, kept in this browser (`prefs`, key `wb-laser`)."""
    laser = WB[WB.index("const wbLaser = {") : WB.index("function wbPresentLaserButton(")]
    assert 'kebabMenu(items, "Laser pointer options")' in laser and "WB_RUN_SWATCHES" in laser
    assert 'looks: { dot: "Dot", trail: "Trail", ring: "Ring", spotlight: "Spotlight" }' in laser
    assert 'prefs.setJSON("wb-laser"' in laser and 'prefs.json("wb-laser"' in laser
    assert "wbLaser.menu()" in _body("wbPresentLaserButton")
    assert "wbLaser.apply();" in _body("wbPresentLaser")


def test_reduce_motion_turns_the_trail_off_and_looks_animate_only_transform_and_opacity():
    trail = _body("wbLaserTrail")
    assert "reducedMotionWanted()" in trail and "wbLaser.prefs().trail" in trail
    looks = CSS[CSS.index('.wb-laser-layer[data-look="dot"]') : CSS.index("/* The template gallery")]
    assert "prefers-reduced-motion" not in looks
    for keyframes in ("wb-laser-pulse", "wb-laser-fade"):
        body = CSS[CSS.index(f"@keyframes {keyframes}") :].split("\n}\n")[0]
        props = set(re.findall(r"^\s+([a-z-]+):", body, re.M))
        assert props <= {"opacity", "transform"}, (keyframes, props)
    assert looks.count('[data-motion="reduced"]') >= 2


def test_a_menu_opens_at_least_as_wide_as_its_labelled_opener():
    """INBOX 1577: the present bar's page picker (320px) opened a 206px list."""
    menus = (ROOT / "frontend" / "js" / "menus.js").read_text(encoding="utf-8")
    body = menus[menus.index("function openActionMenu(") :]
    body = body[: body.index("escapeMenuIfClipped(menu, opener);")]
    assert 'aria-haspopup") === "menu"' in body and "icon-only" in body and "menu.style.minWidth" in body


def test_the_rings_pulse_is_a_switch_like_the_trail():
    """INBOX 1628, the owner: "that pulsing on the ring option ... should be like the trail
    in that it can be toggled on or off". On by default, kept with the other choices, a
    menu row while the ring is the look, and off stills the pulse in CSS."""
    laser = WB[WB.index("const wbLaser = {") : WB.index("function wbPresentLaserButton(")]
    assert "pulse: saved.pulse !== false," in laser
    assert 'layer.dataset.pulse = pulse ? "on" : "off";' in laser
    assert 'now.look === "ring" ? [{ label: now.pulse ? "Pulse: on" : "Pulse: off"' in laser
    assert "wbLaser.set({ pulse: !now.pulse })" in laser
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    still = css[css.index('.wb-laser-layer[data-pulse="off"] .wb-laser-head::after'):]
    assert "animation: none;" in still[: still.index("}")]
