"""INBOX 1542: an insert panel opens in its final place in its first frame.

The owner: "I opened the emoji panel but it shifted position a split second
after, maybe from where I had previously dragged it last time". Measured
before (Playwright, a requestAnimationFrame loop over the panel's rect, a
stored drag at 269,228 and a caret at 300,250):

- second open: frame 1 at 269,228, frame 3 at 278,252 (the grow from the
  caret's origin), frame 10 back at 269,228;
- third open, caret moved: the stored offset was applied on top of the caret
  placement and clamped, so it opened at 0,388, neither at the caret nor where
  it was left;
- the centred picker (a document has no caret box to hang from) lost its
  `translate: -50%` to the first drag and jumped 192px.

The class: a popover placed at an anchor was moved by an offset measured from
a different anchor. A popover is now re-based on the middle of the window when
it is adopted (`panelAdopt.rebase`), so every stored place is measured from one
base; it fades in where it stands instead of growing from a caret it has left.
These are source checks; the numbers come from the sweep named in the commit.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend"
PANEL = (ROOT / "js" / "panel-movable.js").read_text(encoding="utf-8")
PICKER = (ROOT / "js" / "icon-picker.js").read_text(encoding="utf-8")
EDITOR = (ROOT / "js" / "editor.js").read_text(encoding="utf-8")
CSS = (ROOT / "css" / "icon-picker.css").read_text(encoding="utf-8")


def _body(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_a_popover_is_rebased_before_any_saved_place_is_applied():
    adopt = _body(PANEL, "panelAdopt")
    assert adopt.index("panelAdopt.rebase(panel, st)") < adopt.index("panelStoreRead(")
    rebase = PANEL[PANEL.index("panelAdopt.rebase = ") : PANEL.index("function panelAdopt(")]
    # The offset is the difference in layout, so a grow under way does not enter it.
    assert "offsetLeft" in rebase and "offsetTop" in rebase
    assert "getBoundingClientRect" not in rebase
    assert 'classList.add("popover-centred")' in rebase


def test_the_centred_base_never_uses_a_translate():
    block = CSS[CSS.index(".help-popover.popover-centred {") :]
    block = block[: block.index("}")]
    assert "translate" not in block, "a centring translate is dropped by the panel's own drag"
    assert "margin-inline: auto" in block
    assert "animation-name: ui-fade" in block, "no grow from an opener the panel has left"
    assert ".help-popover.popover-centred::before" in CSS
    assert "icon-picker-centred" not in CSS + PICKER


def test_the_picker_waits_for_the_movable_module_so_it_is_placed_once():
    door = _body(EDITOR, "pickIconOrEmoji")
    assert 'ensureModule("panelMovable")' in door and "openIconPicker(options)" in door
