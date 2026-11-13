"""Source text: the sidebar's Notes rows start at the same pixel as Linked from's (L421).

Measured at 1440 dark: Linked from's rows draw a lead icon at x=37 and their
words at 59, a comment's at 40 and 59, and a Notes row had no icon, so its
words began at 37, 22px left of every row above it. A note row now leads with
the note icon Linked from gives a note.
"""

from __future__ import annotations

import re

from tests._app_js import script_file_text


def test_a_notes_row_leads_with_the_note_icon():
    body = re.search(r"function renderDocNotes\(\) \{(.*?)\n\}\n", script_file_text("documents.js"), re.S).group(1)
    assert 'ph-note ph-lead' in body
