"""The top bar and the status bar, polished and decluttered (INBOX 618).

The owner: "do the top bar and bottom bar need a more modern and professional
ui/ux redesign or adjustments at all or are they fine??" The recommendation
taken: the space picker a ghost the tab pills' shape, the selected tab with no
extra weight, a smaller logo tile, Quit quieter than the other header icons;
in the status bar the counts quiet, Agent, Guide and Find icon-only with a
tooltip, Commands the one worded doorway, and the page arrows and undo/redo
one group. Measured with `scratchpad/ui-sweeps/bars618.js` at 1440 and 390,
light and dark: 11 findings at 1440 before, 0 after.
"""

import re
from pathlib import Path
from tests._css_paths import css_glob_text

ROOT = Path(__file__).resolve().parents[1]
CSS = css_glob_text()
STATUS = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")


def _rules(selector: str) -> list[str]:
    """Every top-level-or-nested rule body whose selector list is exactly this."""
    return [m.group(1) for m in re.finditer(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)]


def test_the_space_picker_is_a_ghost_the_shape_of_a_tab():
    body = "".join(_rules("#top-bar .space-switcher-btn.ghost"))
    assert "background: transparent;" in body
    assert "border-color: transparent;" in body
    assert "height: var(--control-h-body);" in body
    assert "--field-inset" not in body and "--control-edge" not in body


def test_the_selected_tab_is_not_drawn_heavier():
    for body in _rules("#tab-bar button.active .tab-label"):
        assert "text-stroke" not in body


def test_the_logo_tile_is_smaller_than_the_controls():
    body = "".join(_rules("#top-bar #brand-logo"))
    assert "width: 1.75rem;" in body and "height: 1.75rem;" in body


def test_quit_is_at_full_strength_like_its_neighbours():
    """Reversed 2026-10-06 (the owner: "the quit button looks dimmed??"):
    INBOX 618's dimmed Quit read as disabled; its red hover sets it apart."""
    assert not _rules("#top-bar #quit-btn:not(:hover, :focus-visible)")


def test_the_counts_are_quiet():
    body = "".join(_rules(".status-item b"))
    assert "font-weight: 500;" in body and "color: inherit;" in body


def test_agent_guide_and_find_are_icons_at_every_width():
    # The words stay in the accessibility tree (clipped, never display: none),
    # and each button is named by its word and explained by its title.
    rule = "#status-bar :is(#status-agent, #status-guide, #status-find) > span"
    bodies = _rules(rule)
    assert any("clip-path: inset(50%);" in b for b in bodies)
    for name in ("Agent", "Guide", "Find"):
        assert f'setAttribute("aria-label", "{name}")' in STATUS, name
    assert "word.textContent = \"Commands\";" in STATUS


def test_the_page_arrows_and_undo_are_one_group():
    body = "".join(_rules(".status-nav"))
    assert "border-right" not in body
