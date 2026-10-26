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


def test_chat_with_no_model_does_not_name_one_or_send_you_to_notes_ask():
    # 17: "Inherited: llama3.2 (not connected)" and "Try in Notes, Ask:".
    assert '"No model connected"' in (JS / "ai-tools.js").read_text()
    assert "(not connected)`" not in (JS / "ai-tools.js").read_text()
    assert '"Try in Ask:"' in (JS / "sheets-selects.js").read_text()


def test_settings_search_opens_the_first_match():
    # 18: "phone" listed results while the pane stayed on Models.
    src = (JS / "settings.js").read_text()
    assert "findSettings(query, 1)[0]?.section" in src


def test_chat_hint_is_left_off_a_one_row_box_in_a_narrow_window():
    # 20: at 700px "Press / for blocks and commands." was cut to "Press / for bl".
    assert "innerWidth < 800" in (JS / "editor.js").read_text()


def test_a_formatting_toolbar_is_one_tab_stop():
    # 21: Tab from the note title walked every toolbar button before the editor.
    src = (JS / "documents.js").read_text()
    assert "function wireToolbarRoving" in src
    assert "wireToolbarRoving(bar);" in src.split("function wireMarkdownToolbar")[1][:400]


def test_note_cards_show_list_markers_as_bullets_not_dashes():
    # 9: "- item" lines showed as raw text in the notes list.
    assert '"$1•"' in (JS / "note-cards.js").read_text()


def test_the_toolbar_arrow_keys_are_written_down_in_help_and_both_shortcut_lists():
    # 21: Left and Right move inside a toolbar; the Guide and both key lists say so.
    from tessellate.ai import help_chat

    index = (JS.parent / "index.html").read_text()
    assert index.count("Move between a formatting toolbar's buttons") == 2
    body = " ".join(topic.get("body", "") for topic in help_chat.HELP_TOPICS)
    assert "A formatting toolbar, here or in a document, is one Tab stop" in body and "Left and Right move between its buttons" in body


def test_a_month_taller_than_its_pane_fades_its_bottom_edge():
    # 5: at 1280x800 the last week row sat below the fold with no hint
    # (measured: scrollHeight 729 over clientHeight 579; the mask is on at scrollTop 0, off at 150).
    src = (JS / "timeline-calendar.js").read_text()
    assert "timelineCalMoreHint(box);" in src.split("timelineCal.painted = drawn;")[1][:80]
    css = (JS.parent / "css" / "timeline-calendar-lazy.css").read_text()
    assert ".timeline-scroll.is-more-below:has(.timeline-cal-month) {" in css and "mask-image" in css
