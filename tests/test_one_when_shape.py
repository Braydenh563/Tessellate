"""A date with its time is printed one way (WORLD_CLASS_PLAN: "every date and
time follows one setting"). `whenText` (status.js) is the reader's locale to the
minute; a bare `toLocaleString()` on a date printed seconds on version lists,
note hovers and run logs while the Timeline and the reminders printed none.
A new date shown with `new Date(...).toLocaleString()` fails here."""
from __future__ import annotations

import re
from pathlib import Path

JS = sorted((Path(__file__).resolve().parents[1] / "frontend" / "js").glob("*.js"))
BARE_DATE = re.compile(r"new Date\([^;]*?\)\.toLocaleString\(\)")


def test_no_date_is_printed_with_a_bare_to_locale_string():
    found = {p.name: len(BARE_DATE.findall(p.read_text(encoding="utf-8"))) for p in JS}
    assert {k: v for k, v in found.items() if v} == {}, "use whenText(date) from status.js"


def test_when_text_is_defined_once_and_has_no_seconds():
    status = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert status.count("function whenText(") == 1
    # The formatter now follows the 12 or 24 hour setting (`clockOptions`,
    # prefs.js); the shape it asks for is unchanged: to the minute, no seconds.
    line = status[status.index("whenText.format = ") :].split("\n", 1)[0]
    assert 'clockOptions.formatter({ dateStyle: "medium", timeStyle: "short" })' in line
    assert "second" not in line
