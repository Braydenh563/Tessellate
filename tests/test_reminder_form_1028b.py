"""Sweep 1028b W2, W3, W13, W28, W29: the reminders compose form.

Driven in the app (port 8798, 1280): "Pay rent next tuesday at 9am" in
`#reminder-text` saved due Tue 3 Nov 09:00 (was in two minutes); a past date
showed the server's reason under the form with the date opener focused and
`aria-describedby` set; an empty add showed the same line with the text field
focused and `aria-invalid`. The form's Add lives in quickadd.js, which loads
after the gzip-counted scripts.
"""

from __future__ import annotations

import re

from tests._app_js import INDEX_HTML, JS_DIR, app_js_text


def _compose_add() -> str:
    quick = (JS_DIR / "quickadd.js").read_text(encoding="utf-8")
    start = quick.index("async function reminderComposeAdd")
    return quick[start: quick.index("\n}\n", start)]


def test_the_sentence_box_is_read_for_its_time_before_the_add():
    body = _compose_add()
    assert "quickAddSlots(box)" in body and "slots?.due" in body
    quick = (JS_DIR / "quickadd.js").read_text(encoding="utf-8")
    assert 'quickAddAttach($("reminder-text"), "reminder"' in quick
    wiring = (JS_DIR / "wiring.js").read_text(encoding="utf-8")
    assert '$("reminder-add").addEventListener("click", reminderComposeAdd)' in wiring
    assert '"reminderComposeAdd"' in (JS_DIR / "lazy-entries.js").read_text(encoding="utf-8")


def test_the_form_errors_are_inline_and_nothing_rejects_unhandled():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert re.search(r'<p id="reminder-form-error"[^>]*role="alert"', html)
    body = _compose_add()
    assert "try {" in body and "catch (error)" in body and "reminderFormError(error.message" in body
    assert "reminderFormError(" in body and "reminder-text" in body
    quick = (JS_DIR / "quickadd.js").read_text(encoding="utf-8")
    assert '$("reminder-date").min' in quick


def test_a_question_is_said_once_and_the_due_label_is_a_word():
    quick = (JS_DIR / "quickadd.js").read_text(encoding="utf-8")
    ask = quick[quick.index("qaHold(input, slots, text);"):]
    assert 'status.textContent = "";' in ask[:300]
    assert "tmrw" not in app_js_text()
