"""A log record on a phone (HR23, audit 1031).

At 390 px the row grid (time, level, message, a 44 px copy button) left the
message 71 px: a one-line record stood 1,100 px tall, 52 records were 62,000 px,
and opening Settings, Logs spent 1,000 to 1,700 ms of layout at 4x CPU. The
time and level now share the first line with the copy button and the message
takes the row's width beneath them (a 58 px row, a 5,090 px list, layout 431
to 505 ms)."""

from __future__ import annotations

import re

from tests.test_ui_recipes import ROOT

CSS = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")


def test_a_log_record_stacks_its_message_under_its_time_on_a_phone():
    block = re.search(r"@media \(max-width: 599\.98px\) \{\s*\.log-list li \{(.*?)\n\}\n", CSS, re.S)
    assert block, "the phone rule for .log-list li is gone"
    phone = CSS[block.start() : block.start() + 700]
    assert "grid-template-columns: auto minmax(0, 1fr) auto" in phone
    assert re.search(r"\.log-list \.log-line \{\s*grid-column: 1 / -1;\s*grid-row: 2;", phone)
    assert re.search(r"\.log-list \.log-copy \{\s*grid-column: 3;\s*grid-row: 1;", phone)
