"""The companion reads along with a long note even when the list sent it cut short (L-world-class-413, companionreact.js).

The notes list carries a long note's first 297 characters with `content_truncated` set, so the
"longer than 1200 characters" test never held for any real long note and the reading glasses
never came out on Show more.
"""

import re
from pathlib import Path

AVATARS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def test_read_reaction_counts_a_truncated_note_as_long():
    m = re.search(r"function nameMarkBuddyNoteOpened\(.*?\n  \}\n", AVATARS, re.S)
    assert m, "nameMarkBuddyNoteOpened moved"
    #: A cut row is judged by the server's whole-text word count (routes_entries keeps it on the row), so a
    #: long note reads along and a short one cut at 300 characters does not (test_clipped_readers_1525c runs it).
    assert "entry.content_truncated ? (entry.word_count" in m.group(0)
    assert 'nameMarkBuddyReact("read", row)' in m.group(0)
