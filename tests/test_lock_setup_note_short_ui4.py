"""Source text: L-ui-modernisation-4, "Shorten the lock setup note and rename
its button" (scratchpad/first-run-472.md row 9: "A 5-line, 12px paragraph
under the field (73 words) and "Set password & start" with an ampersand").
Measured in the app after: 36px, two lines, at 1440 and 390 (see the ledger
row's evidence)."""
import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]


def test_setup_note_is_one_short_line():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    note = re.search(r'<p id="lock-setup-note"[^>]*>(.*?)</p>', html, re.S).group(1)
    assert len(note.split()) <= 20, note
    assert "eight characters" in note and "Private notes" in note


def test_setup_button_has_no_ampersand():
    src = app_js_text()
    assert '"Set password and start"' in src
    assert "Set password &" not in src
