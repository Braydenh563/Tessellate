"""The in-app companion dive (companion dive 1107): a bar or hang companion keeps clear of the
new tab's controls, its peek handle is the head it draws, it says how to use it, and
the palette can focus it. Source-level checks (the app runs against a fake transport
here); the measured numbers are in docs/roadmap/agent-remaining/inappdive-1107.md."""

from __future__ import annotations

from tests._help_text import help_more_text
import re
from pathlib import Path
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def test_the_peek_handle_is_the_head_it_draws() -> None:
    # 390x844, Notes: the handle hit-tested from y 710 to 784 while the head is drawn from y 752
    # (the char is translated by --nmb-edge - 34), so 38px of empty air over New note took its taps.
    # The handle is the face's ::after, so its top is cut there, not by the paint clip
    # (L-ui-modernisation-48: cutting the paint sliced the drawing, below).
    handle = re.search(r"top: (.*);", _rule('#nm-buddy[data-legs="peek"] .nm-buddy-face::after'))
    assert handle, "the tucked-behind-the-bar handle"
    #: Leaves the emerge's 10px rise (edge - 44) uncut, and no more than that.
    assert handle.group(1) == "calc(var(--nmb-edge) - 44px)", handle.group(1)


def test_a_tucked_companion_is_cut_only_at_the_bar() -> None:
    """Source text: L-ui-modernisation-48, the owner: the in-app companion was clipped about
    2/3 up while it tucked behind the status bar. Measured per frame at 480x560 (Atlas, Notes):
    the paint clip's top (edge - 44, y 458) cut the drawing as it sank from y 430 and at rest
    sliced Atlas's art (drawn from y 456, 12px over the char's box); its bottom was the
    status bar's top (y 502 against 502.4). Now only the bar's edge cuts it."""
    clip = re.search(r"clip-path: inset\((.*)\);", _rule('#nm-buddy[data-legs="peek"] .nm-buddy-face'))
    assert clip, "the tucked-behind-the-bar clip"
    assert clip.group(1) == "-80px -80px calc(92px - var(--nmb-edge)) -80px", clip.group(1)


def test_a_bar_or_hang_that_changes_tab_looks_again_for_a_clear_perch() -> None:
    av = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
    changed = av[av.index("function nameMarkBuddyTabChanged") :]
    changed = changed[: changed.index("\n}\n")]
    bar = changed[changed.index('(nmb.perch === "bar" || nmb.perch === "hang")') :]
    assert "setTimeout(queueNameMarkBuddyCheck, 900)" in bar[: bar.index("return;")]


JS = ROOT / "frontend" / "js"
HELP = help_more_text()


def _body(text: str, head: str) -> str:
    start = text.index(head)
    return text[start : text.index("\n}\n", start)]


def test_a_bare_companion_tells_a_new_person_how_to_use_it() -> None:
    # The face had a title only while a prop was on; the how-to was in aria-label alone.
    props = _body(unwrapped((JS / "avatars.js").read_text(encoding="utf-8")), "function nameMarkBuddyNameProps")
    assert 'else face.title = face.getAttribute("aria-label");' in props
    assert "drag to move" in unwrapped((JS / "avatars.js").read_text(encoding="utf-8"))


def test_the_menu_has_a_quieter_row_that_the_settings_select_agrees_with() -> None:
    menu = unwrapped((JS / "companion-menu.js").read_text(encoding="utf-8"))
    assert "Quieter" in menu and "Livelier" in menu
    # Through the Appearance select's own change, as Size and Atlas look do.
    assert 'choose("avatar-buddy-actions", lively ? "off" : "fewer")' in menu
    assert "Quieter" in HELP, "help moves with the menu (standing order 13)"


def test_the_palette_can_put_the_keyboard_on_the_companion() -> None:
    features = (JS / "app-features.js").read_text(encoding="utf-8")
    row = features[features.index('"ph:crosshair Focus companion"') :]
    row = row[: row.index("\n")]
    assert "nameMarkBuddyShowing()" in features[features.index('"ph:crosshair Focus companion"') - 80 :][:120]
    assert ".nm-buddy-face" in row and ".focus()" in row
    assert "Focus companion" in HELP


def test_the_keyboard_focus_on_the_figure_has_a_solid_ring_not_only_a_haze() -> None:
    # A radial glow fading to nothing measured about 1.9:1 against the page; WCAG 2.2 asks 3:1 for a focus indicator.
    ring = _rule("#nm-buddy .nm-buddy-face:focus-visible::before")
    assert "opacity: 1" in ring
    # An outline follows the ::before's border-radius (an ellipse, not the button's box) and survives forced colours.
    assert "outline: 2px solid var(--accent)" in ring, "a 2px accent ring on the ellipse, not a box"


def test_quieter_and_livelier_answer_in_the_companions_voice() -> None:
    # The row only relabelled itself, so the press read as nothing (blind test, companion dive round 2).
    menu = unwrapped((JS / "companion-menu.js").read_text(encoding="utf-8"))
    row = menu[menu.index('label: lively ? "ph:speaker-slash Quieter"') :]
    row = row[: row.index("\n  });")]
    assert "await choose(" in row and "nameMarkSay(buddy," in row
    assert "Reduce actions" in row, "the row's hint names the Settings control it is"


def test_hiding_from_the_keyboard_leaves_focus_on_the_way_back() -> None:
    # Hide removed the focused face, so focus fell to the page and Tab began at "Skip to content".
    settings = (JS / "companion-settings.js").read_text(encoding="utf-8")
    hide = _body(settings, "function nameMarkBuddyHide")
    assert "buddy.contains(document.activeElement)" in hide
    assert ".toast-action\")?.focus()" in hide


def test_the_menu_puts_its_speech_bubble_away_before_it_opens_over_it() -> None:
    menu = unwrapped((JS / "companion-menu.js").read_text(encoding="utf-8"))
    opens = _body(menu, "function nameMarkBuddyMenu")
    assert opens.index('querySelector(":scope > .nm-say")?.remove()') < opens.index("openMenuAtPoint(")
