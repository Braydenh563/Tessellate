"""Audit 1031 class 48 (SH10, SH13, SH14, SH16, SH17): the shell's loose ends.

SH10: Shift with the slash key is "?", the shortcuts list, never the jump to
search. SH13: a reminder's past due time is refused before the request.
SH14: the empty tray already opens a panel saying what it holds (checked, no
change). SH16: the backup line reads the newest backup. SH17: the tour card
carries no panel chrome."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_shift_slash_is_the_question_mark_not_the_search():
    body = _js("settings-wiring.js").split("function matchesShortcut(event, combo)", 1)[1].split("\n}\n", 1)[0]
    assert 'event.shiftKey && event.key === "/" ? "?" : event.key' in body
    assert "key === combo" in body


def test_a_past_reminder_is_refused_before_the_request():
    body = _js("shell-reminders.js").split("async function addReminder(", 1)[1].split("\n}\n", 1)[0]
    check = body.index("Date.now() - 60000")
    assert check < body.index('apiJson("/reminders"')
    assert "throw new Error(" in body[check:]
    # The server's sentence, so the field's line reads the same either way.
    server = (ROOT / "src" / "tessellate" / "api" / "routes_reminders.py").read_text(encoding="utf-8")
    sentence = "That reminder's due time is in the past. Pick a time that hasn't happened yet."
    assert sentence in body and sentence in server


def test_an_empty_tray_says_what_it_holds():
    draw = _js("obj-tray.js").split("function objTrayDraw(holder)", 1)[1].split("\n}\n", 1)[0]
    assert "Drop a card here, or choose Add to tray in its menu." in draw
    assert "clear.disabled = !rows.length;" in draw


def test_the_backup_line_reads_the_newest_backup():
    body = _js("settings-data.js").split("async function renderBackups()", 1)[1].split("for (const item of backups)", 1)[0]
    assert "backups.find((b) => b.latest) || backups[0]" in body
    assert "`Last backup ${relativeTime(newest.created_at)}." in body
    # A "Saved ..." the Back up now button wrote is not overwritten.
    assert 'startsWith("Last backup")' in body


def test_the_tour_card_carries_no_panel_chrome():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    card = html.split('<div id="tour-card"', 1)[1].split(">", 1)[0]
    assert "data-panel-fixed" in card
