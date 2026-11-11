"""The node popup writes a note only when Save is pressed (INBOX 1769).

History: audit G2 made every way out of the popup (Escape, the X, a click on
the map, another note) save a dirty edit. The owner, 2026-11-11, reversed it:
"I just clicked off the popup and it saved ... it should have canceled unless I
pressed save", with a confirm offering cancel. The test's stated intent moved,
so it now pins the opposite: leaving asks, and only Save calls the PUT route.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")


def _fn(name: str, kind: str = "function") -> str:
    start = GRAPH.index(f"{kind} {name}(")
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def test_close_and_switch_both_ask_before_going():
    assert "graphPopupMayLeave()" in _fn("closeGraphPopup", "async function")
    assert "graphPopupMayLeave()" in _fn("openGraphPopup", "async function")


def test_the_card_offers_discard_changes_or_keep_editing():
    body = _fn("graphPopupMayLeave", "async function")
    assert "graphPopupIsDirty()" in body
    assert "confirmDialog(" in body
    assert 'confirmLabel: "Discard changes"' in body
    assert 'cancelLabel: "Keep editing"' in body


def test_the_guard_only_counts_a_loaded_dirty_popup():
    assert "Loading…" in _fn("graphPopupIsDirty")


def test_nothing_saves_on_the_way_out():
    assert "keepGraphPopupEdit" not in GRAPH
    assert "leaving" not in _fn("saveGraphPopup", "async function")
    # The only caller of the write is the Save button.
    assert GRAPH.count("saveGraphPopup(") == 2  # the definition and the click


def test_a_late_save_does_not_close_or_overwrite_the_next_popup():
    body = _fn("saveGraphPopup", "async function")
    assert body.count("graphPopupId === id") >= 2
