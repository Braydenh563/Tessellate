"""INBOX 904 B16: a date field drawn after boot is still the app's own picker.

The owner: "the properties panel popups like with the date select aren't the
custom style used in the reminders tab". `watchForSelects` enhanced the date
and time inputs in the page at boot and only `<select>`s that were added later,
so the document properties panel (a typed field, `type: book` -> "finished"),
which draws its inputs when a document opens, got the browser's grey calendar.
The browser check is `scratchpad/ui-sweeps/docpropdate.js`.
"""

from __future__ import annotations

from tests._app_js import with_pieces


def test_the_observer_enhances_date_fields_added_later():
    selects = with_pieces("sheets-selects.js")
    watch = selects[selects.index("function watchForSelects()"):]
    watch = watch[: watch.index("\n}\n")]
    observer = watch[watch.index("new MutationObserver"):]
    assert "enhanceDateField(" in observer
    assert 'input:is([type="date"], [type="time"])' in observer
