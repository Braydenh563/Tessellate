"""L656 palette rows per act, L668 rowActions in tidy rows, L596 inbox grid rows."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _text(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_palette_has_a_row_for_note_meeting_and_search_acts():
    quick = _text("quickadd.js")
    for intent in ("new_note", "meeting", "find"):
        assert f'qaIntent(state.reading, "{intent}")' in quick
    assert "openNewMeeting({ title" in quick and "openFinder(String(read.about)" in quick
