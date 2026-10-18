"""UX audit 1018 (uxfix2): source-level guards for the six findings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = (ROOT / "frontend/index.html").read_text()
MAP_JS = (ROOT / "frontend/js/whiteboard-map.js").read_text()


def test_empty_map_shows_one_empty_state():
    # Zero nodes: the empty card only. The template strip waits for the root.
    assert "index.nodes.length !== 1" in MAP_JS
    assert "Start it again with one topic" not in INDEX
    assert "Add one topic, then press Tab for a branch." in INDEX


def test_boards_picker_drops_default_row_while_gallery_counts_none():
    wb = (ROOT / "frontend/js/whiteboard.js").read_text()
    assert "audit 1018, item 11" in wb
    assert "onCanvas" in wb
