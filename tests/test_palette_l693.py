"""L693: palette rows that had no command (Library Boards, Recordings, Notifications unread, note rows)."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
FEATURES = (JS / "app-features.js").read_text(encoding="utf-8")
PALETTE = (JS / "app-palette.js").read_text(encoding="utf-8")
REVEAL = (JS / "reveal-targets.js").read_text(encoding="utf-8")


def test_library_sub_tabs_have_rows_and_targets():
    for key in ("library-boards", "library-recordings", "library-skills", "library-contents"):
        assert f'reveal: "{key}"' in FEATURES
        assert f'"{key}":' in REVEAL


def test_notifications_row_says_the_unread_count():
    assert "about: notificationsUnreadSaid()" in FEATURES


def test_note_in_hand_rows_chat_and_file():
    assert "askAtlasAboutNote(held)" in PALETTE and "reevaluateEntry(held)" in PALETTE
