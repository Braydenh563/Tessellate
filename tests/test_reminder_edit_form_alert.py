"""Brief 101b: the reminder edit form can change and clear an alert.

An alert was set by words only ("dentist tomorrow 3pm, 1 day before"); the
inline edit form had text, time, priority and repeat, and no way to change or
remove it. The form is built by DOM code the suite cannot run, so this holds
the shape: a select named Alert whose values are the API's minutes (0 is
none), sent on Save, and put back by Undo.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR


def _form() -> str:
    source = (JS_DIR / "shell-reminders.js").read_text(encoding="utf-8")
    match = re.search(r"^function reminderEditForm\(reminder\) \{.*?^\}", source, re.S | re.M)
    assert match, "reminderEditForm is gone"
    return match.group(0)


def test_the_form_has_an_alert_select_with_a_no_alert_choice():
    form = _form()
    assert 'alertSelect.title = "Alert"' in form
    assert '[0, "No alert"]' in form
    #: The alert select sits with the other fields (one row of equal height), then the buttons.
    assert "[dueInput, prioritySelect, recurringSelect, alertSelect]" in form
    assert "wrap.append(textInput, fields, row)" in form


def test_save_sends_the_alert_and_undo_puts_the_old_one_back():
    form = _form()
    assert "alert_minutes: Number(alertSelect.value)" in form
    assert "alert_minutes: alertNow" in form, "the undo snapshot must carry the old alert (0 when none)"


def test_an_alert_the_menu_has_no_word_for_is_kept():
    assert "alertPresets.push([alertNow" in _form()
