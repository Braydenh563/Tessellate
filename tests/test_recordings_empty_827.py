"""INBOX 827 L2: the Recordings empty state records and imports (sweep `l12.js`: two buttons, an icon, two lines)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text()


def test_recordings_empty_state_records_and_imports():
    js = _read("frontend", "js", "meetings.js")
    #: The record action is labelled by outcome, "Open recorder" (test_recording_is_unsaved_work_1029, the older rule).
    assert '" Open recorder"' in js and '" Import audio"' in js
    assert "A meeting's recording and its transcript land here too." in js
    html = _read("frontend", "index.html")
    assert 'id="recordings-import"' in html and 'id="recordings-import-file"' in html
