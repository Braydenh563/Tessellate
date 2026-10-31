"""Audit 1031 class 26 (N27, N37, N46): the Notes dock keeps its list controls.

N27: Sort, Cards or Rows and Select sat in the dock's ⋯ at 1440 (a count
rule: past seven items a dock folds). The Notes dock now folds by width alone,
below 900. N37: a suggested tag is a button (class 28 made it one), and a batch
act hands focus back to Select. N46: a note opened from the list is a step of
the one history, so Back names the view before it."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_the_notes_dock_folds_by_width_below_900_and_never_by_count():
    text = _js("phone-shell.js")
    assert 'const DOCK_KEEPS_ABOVE = "(min-width: 900px)";' in text
    arrange = text.split("function foldDockArrange(narrow)", 1)[1].split("\n}\n", 1)[0]
    assert 'const keeps = dock.dataset.dockName === "notes";' in arrange
    assert "keeps ? !roomy : narrow || dockItemCount(dock) > DOCK_FOLD_PAST" in arrange
    # Select is not pulled into the ⋯ by the second fold either.
    assert 'dock.dataset.dockName !== "notes" && dockItemCount(dock, false) > DOCK_FOLD_PAST' in text
    # And the 900 line re-decides when a window is dragged across it.
    assert 'window.matchMedia(DOCK_KEEPS_ABOVE).addEventListener("change"' in text


def test_a_batch_act_hands_focus_back_to_select():
    text = _js("skills.js")
    body = text.split("function exitSelectMode()", 1)[1].split("\n}\n", 1)[0]
    assert 'restoreFocusTo(() => ($("select-btn").offsetParent ? $("select-btn")' in body


def test_a_note_opened_from_the_list_is_a_step_of_the_one_history():
    text = _js("capture-ask.js")
    assert 'recordTabVisit("notes", `note:${id}`' in text
    nav = _js("navigation.js")
    assert "title: prev ? `Back to ${entryLabel(prev)}`" in nav
