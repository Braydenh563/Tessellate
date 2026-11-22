"""L-world-class-879: boot read the open reminders twice, once for the due
poll (`openReminderList`, a month's window) and once for the dashboard and
the bell (`openReminders`, the shared slice). The poll's first look now takes
its month from the slice, so the dashboard joins that read: one GET."""

from __future__ import annotations

from tests._app_js import frontend_text


def test_the_first_due_look_reads_the_shared_slice():
    status = frontend_text("status.js")
    start = status.index("const openReminderList = ")
    body = status[start : status.index("\n})();\n", start)]
    assert "cache.all\n" in body and "await openReminders().then(" in body
    assert 'apiJson("/reminders?include_done=false&due_within_days=31"' in body, "later looks keep the month"
    assert "Date.parse(r.due_at) <= month" in body, "the slice is cut to the same month"
