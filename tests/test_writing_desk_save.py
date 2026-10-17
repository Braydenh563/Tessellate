"""The writing room's Save files a note; the caret keeps a draft (INBOX 904 B79).

The button said "Save as note" and saved a draft, so the person's filed note
arrived in Drafts. Source-level, like its neighbours.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"
DESK = (ROOT / "js" / "writing-desk.js").read_text(encoding="utf-8")
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_save_as_note_is_a_note_unless_the_caret_says_draft() -> None:
    assert "async function saveDraftAsNote(asDraft = false)" in DESK
    assert "is_draft: asDraft === true" in DESK
    assert "is_draft: true, defer_filing" not in DESK
    assert "saveDraftAsNote(true)" in DESK and "Save as draft" in DESK


def test_the_save_is_a_split_button() -> None:
    assert 'id="draft-save-split" class="split-button' in HTML
    assert 'id="draft-save" class="split-button-main"' in HTML
    assert 'id="draft-save-menu-slot" class="split-button-slot"' in HTML
