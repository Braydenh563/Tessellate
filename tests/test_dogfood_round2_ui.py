"""Blind-test round 2 (dog2-1025): UI fixes the suite can only pin by source.

Each check names the finding it guards; the measured behaviour was driven in
Chromium (numbers in the commit).
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_month_calendar_scrolls_today_into_view():
    # 5: a 6-row month is 729px in a 579px pane at 1280x800; today's row was clipped.
    src = (JS / "timeline-calendar.js").read_text()
    assert "timelineCalShowToday" in src
    assert 'span === "month" && timelineCal.painted !== drawn' in src


def test_reminder_rows_show_the_day_and_the_relative_time():
    # 8: "in 5 days" alone said nothing about which day.
    src = (JS / "shell-reminders.js").read_text()
    assert 'weekday: "short"' in src.split("due.textContent")[1][:300]
    assert "relativeWhen(reminder.due_at)" in src.split("due.textContent")[1][:300]


def test_a_title_ending_in_due_keeps_its_day_word():
    from datetime import datetime

    from tessellate.ai.recognise import parse_reminder_text

    now = datetime(2026, 10, 25, 12, 0)
    assert parse_reminder_text("Essay due friday 5pm", now)["text"] == "Essay due Friday"
    assert parse_reminder_text("Essay due tomorrow at 5pm", now)["text"] == "Essay due Tomorrow"
    assert parse_reminder_text("Essay due 5pm", now)["text"] == "Essay due"
    assert parse_reminder_text("buy milk friday 5pm", now)["text"] == "Buy milk"


def test_quick_add_holds_a_day_that_asked_its_time():
    # 7: "exam 12 dec" asks the time (decision 50: ask, never guess). The next
    # phrase either answers it or is told what was left out.
    src = (JS / "quickadd.js").read_text()
    assert "function qaHold" in src and "function qaResume" in src
    assert "Left out “" in src
    assert "09:00" not in src.split("function qaHold")[1].split("function quickAddClear")[0]
    assert "reminder.duplicate" in src


def test_create_with_an_empty_title_is_answered_and_the_h1_is_not_doubled():
    # 15: promptDialog's Create closed silently on an empty name, and a new
    # document began with a "# Title" line under its own title field.
    app = (JS / "app.js").read_text()
    assert app.count("input.reportValidity() && close(input.value.trim())") == 2
    assert "required = true" in (JS / "capture-ask.js").read_text()
    for name in ("capture-ask.js", "editor.js"):
        assert "content: `# ${" not in (JS / name).read_text().split("apiJson(\"/documents\"")[1][:200]
    assert "A blank line is inside nothing" in (JS / "documents.js").read_text()


def test_a_leading_hash_is_not_part_of_a_tag():
    # 16: "#biology" was stored as "##biology" once the UI added its own mark.
    from tessellate.entry.tagnames import normalise_tags

    assert normalise_tags(["#biology", "##Chem", "  # spaced", "#", "Biology"]) == ["biology", "Chem", "spaced"]
