"""Every "how long ago" reads a server time the same way (audit 2026-10-05,
FE-16).

Two formatters now (the dashboard's own copy folded into `relativeTime`,
audit 1028 S17): `relativeTime` (sheets-selects.js) read through
`parseServerTime`, which treats a zone-less timestamp as the UTC the server
keeps it in; `dashRelativeTime` (dashboard.js) and `relativeWhen`
(shell-reminders.js) used `new Date(iso)`, which reads the same string as
local time, so the dashboard and a reminder's "in 2 hours" were off by the
offset for any time sent without a zone. Their wording differs on purpose
(the reminders say "in 2 hours"); how they read the time may not.
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _function(file: str, name: str) -> str:
    text = (JS / file).read_text(encoding="utf-8")
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start)]


def test_each_reads_through_parse_server_time():
    for file, name in (
        ("sheets-selects.js", "relativeTime"),
        ("shell-reminders.js", "relativeWhen"),
    ):
        body = _function(file, name)
        assert "parseServerTime(iso)" in body, f"{file} {name}"
        assert "new Date(iso)" not in body, f"{file} {name} reads the time as local"
