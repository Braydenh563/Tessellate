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


PALETTE = (ROOT / "frontend/js/app-palette.js").read_text()


def test_palette_offers_three_matching_notes_after_commands():
    assert "PALETTE_NOTE_ROWS = 3" in PALETTE
    # Commands first, then the notes, then the hand-off row.
    assert "...commands, ...paletteNoteRows(typed), handoff" in PALETTE
    assert "kind=note&limit=${PALETTE_NOTE_ROWS}" in PALETTE


def test_palette_focuses_before_it_draws_the_catalogue():
    body = PALETTE.split("async function openPalette()")[1].split("function closePalette")[0]
    assert body.index('$("palette-input").focus()') < body.index("requestAnimationFrame(draw)")
    # A late usage answer must not draw 108 rows into a closed palette.
    assert 'classList.contains("hidden")) renderPalette("")' in body


def test_system_log_lines_do_not_count_as_unread():
    status = (ROOT / "frontend/js/status.js").read_text()
    assert 'NOTIFICATION_LOG_KINDS = new Set(["task", "job"])' in status
    body = status.split("function isNotificationUnread")[1].split("}\n")[0]
    # A hand-set unread flag still wins; the log kinds only skip the watermark.
    assert body.index("forced.has") < body.index("NOTIFICATION_LOG_KINDS")


def test_more_carries_the_reminders_due_count():
    shell = (ROOT / "frontend/js/phone-shell.js").read_text()
    rem = (ROOT / "frontend/js/shell-reminders.js").read_text()
    assert "const shown = due || runs;" in shell
    assert "function phoneMoreDueCount" in shell
    # The reminders fetch repaints More, or the badge would wait for a run.
    assert 'typeof syncPhoneMoreRuns === "function"' in rem
