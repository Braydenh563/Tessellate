"""Settings: the pane's help buttons sit right, and a reset keeps off its dropdown (BACKLOG, the owner 2026-10-12).

"The '?' help button in a section header sits mid-row; it belongs right-aligned
with a token gap, left of 'Reset N changes'. No gap between a select ('5
minutes') and its per-row reset button."

Measured (1440x900, Appearance, one setting changed): the pane's actions
(Expand all and the '?') stood at x 767 to 883 of a bar 477 to 1205 wide, the
Reset button at 1068 to 1194, because both carried `margin-inline-start: auto`
and split the free space. And the Account page's "Auto-lock when idle" select
(opener 494 to 618) had its reset at 618: the reset is appended inside the
dropdown's `.select-shell`, where the old inline margin looked only for a shell
that was its previous sibling. Both are now rules of the lazy Settings sheet
(the boot sheets are at their budget), on tokens.
"""

from __future__ import annotations

from tests._app_js import FRONTEND_DIR, JS_DIR

SHEET = (FRONTEND_DIR / "css" / "settings-controls-lazy.css").read_text(encoding="utf-8")
ROWS = (JS_DIR / "settings-rows.js").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = SHEET.index(selector)
    return SHEET[start : SHEET.index("}", start)]


def test_the_reset_button_follows_the_pane_actions_at_the_docks_own_gap():
    rule = _rule("#settings-modal .dock > .dock-actions ~ .settings-reset-section")
    assert "margin-inline-start: 0;" in rule


def test_a_reset_inside_or_after_a_dropdown_keeps_a_token_gap_from_it():
    rule = _rule("#settings-modal :is(.select-shell > .setting-reset, .select-shell + .setting-reset)")
    assert "margin-inline-start: var(--space-2);" in rule
    # The inline margin that only handled one of the two shapes is gone.
    assert 'style.marginInlineStart = "var(--space-2)"' not in ROWS


def test_on_a_phone_the_reset_stays_last_so_the_help_is_left_of_it():
    phone = SHEET[SHEET.index("@media (max-width: 599.98px)") :]
    assert ".settings-reset-section" in phone and "order: 3;" in phone
