"""L-chat-198 (CHAT_PLAN research row, Raycast prefix grammar): "remind me friday 9 dentist" typed in the palette
shows the reminder it would make as the first row, with the reading's own title and day (the chips under the box say
the same), and a sentence with no recognised act leaves the palette's own rows first."""

from __future__ import annotations

from tests._app_js import frontend_text
from tests.test_quickadd import slots  # noqa: F401  (the node harness fixture)


def test_the_reminder_row_is_first_and_names_the_title_and_the_day():
    palette = frontend_text("app-palette.js")
    start = palette.index("const act = (typeof quickAddPaletteRow")
    assert "return [...(act ? [act] : []), ...utilityPaletteRows(lowered)" in palette[start : start + 1400]
    row = frontend_text("quickadd.js")
    row = row[row.index("function quickAddPaletteRow") : row.index("async function qaPaletteRemind")]
    assert 'label: `ph:bell Remind you: ${slots.title || query.trim()} (${words})`' in row and 'group: "Do it"' in row


def test_the_reading_behind_the_row_is_the_dentist_on_friday_at_nine(slots):  # noqa: F811
    joined = slots["joined"]
    assert joined["title"] == "dentist" and not joined["missing"], joined
    assert joined["due"] == "2026-10-16T09:00:00.000Z", joined
