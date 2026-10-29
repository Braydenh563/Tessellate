"""A colour added to the quick sketch's recent row can be taken off again
(the owner, 2026-10-29: "if the user adds custom colours to the colours at the
top of the quick sketch, that they can easily remove them if they wish").

Each recent swatch has its own remove button beside it (a sibling, never
nested in the swatch), shown on hover, focus and a finger; Delete or Backspace
on a focused recent swatch removes it too. The list in prefs follows.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAD = (ROOT / "frontend" / "js" / "sketch-pad.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "sketch-pad.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = PAD.index(f"function {name}(")
    return PAD[start : PAD.index("\n  }\n", start)]


def test_forgetting_a_colour_updates_the_list_and_prefs():
    body = _fn("forgetColour")
    assert "S.recent.filter(" in body
    assert 'S.host.prefs.set("recent", S.recent)' in body
    assert "paintRecent()" in body


def test_each_recent_swatch_has_a_sibling_remove_button():
    body = _fn("paintRecent")
    assert 'class: "sp-recent-item"' in body
    assert 'class: "sp-unpick"' in body
    assert re.search(r'"aria-label": `Remove \$\{hex\}', body)
    assert "forgetColour(hex)" in body


def test_delete_key_removes_a_focused_recent_swatch():
    build = PAD[PAD.index('"data-sp": "recent"') - 200 : PAD.index('"data-sp": "recent"') + 400]
    assert "onkeydown" in build and "forgetRecentKey" in build
    body = _fn("forgetRecentKey")
    assert '"Delete"' in body and '"Backspace"' in body


def test_remove_buttons_stay_out_of_the_arrow_rove():
    assert "button:not(.sp-unpick)" in _fn("roveItems")


def test_remove_button_shows_on_hover_focus_and_finger():
    assert ".sp-recent-item:is(:hover, :focus-within) .sp-unpick" in CSS
    assert "@media (pointer: coarse)" in CSS[CSS.index(".sp-unpick") :]


def test_the_pad_help_says_how():
    colours = PAD[PAD.index('["Colours", ') :]
    colours = colours[: colours.index("]")]
    assert "Delete" in colours and "recent" in colours
