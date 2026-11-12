"""Library Activity reads as a log, in words, and the Bin's tick clears the
card's menu (INBOX 426 z, images 89 to 91).

Measured with `scratchpad/ui-sweeps/libactivity.js` at 1440: in the grid an
activity row's detail was 11px wide (the masonry dealt one-line records into
17rem columns), a settings record read "notificationsmutedexcept_reminders"
(markdown stripped server-side and rendered again client-side), rows with no
detail slid to x 1227 in Rows, and the Bin's tick sat 4px from the ⋯ in the
grid and over the date in Rows. After: 0 narrow previews, keys in words
("Mute notifications except reminders: off"), the tick 6px from the ⋯ and
over nothing in both views. The server half is in tests/test_library.py.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")


def test_activity_is_dealt_into_one_column() -> None:
    body = LIBRARY[LIBRARY.index("function libraryColumnCount"):]
    body = body[: body.index("\n}\n")]
    assert 'if (libraryKind === "activity") return 1;' in body


def test_an_activity_detail_is_plain_text_in_words() -> None:
    card = LIBRARY[LIBRARY.index("function libraryCard"):]
    card = card[: card.index("\nfunction ")]
    assert 'preview.textContent = activityDetailText(shownPreview);' in card
    assert "ACTIVITY_SETTING_NAMES" in LIBRARY


def test_the_tick_keeps_the_gap_token_from_the_menu() -> None:
    css = re.sub(
        r"/\*.*?\*/", "", (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8"),
        flags=re.S,
    )
    ticks = re.findall(r"\.library-card-tick\s*\{[^}]*right:\s*calc\(([^;]*)\);", css)
    assert ticks, "no tick placement found"
    for value in ticks:
        assert "var(--target-min) + var(--space-2)" in value, value
