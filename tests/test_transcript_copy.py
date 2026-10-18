"""INBOX 1300 C40: a recording's transcript lines can be copied one at a time,
as a Shift-click run, or all of them, with or without times
(the `c40` Playwright sweep (kept out of the repo, which is at its scratchpad file cap) drives it in the app)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend"
JS = (ROOT / "js" / "meetings.js").read_text(encoding="utf-8")
CSS = (ROOT / "css" / "meetings-lazy.css").read_text(encoding="utf-8")


def test_every_line_has_its_own_copy_button_and_the_menu_copies_runs_and_all() -> None:
    assert 'smallButton("ph:copy", "Copy this line"' in JS
    for label in ("Copy picked lines", "Copy picked lines with times", "Copy all", "Copy all with times"):
        assert f'"ph:copy {label}"' in JS or f'"ph:clock {label}"' in JS
    assert "event.shiftKey" in JS and '"Copy the transcript"' in JS


def test_the_copy_button_shows_on_hover_and_focus_and_always_without_hover() -> None:
    assert ".recording-line-row:is(:hover, :focus-within) .recording-line-copy" in CSS
    assert "@media (hover: none)" in CSS
