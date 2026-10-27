"""`body:has(...)` makes the browser re-check the rule on DOM changes
anywhere in the page. One such rule for the documents' full-screen popups
took the 500-object board budget from under 170 ms to about 400 ms
(e2e budgets, 2026-10-25). State that styles things outside its element
goes on a body class set by the code that changes it. The allowlist is the
ratchet: it may shrink, never grow."""

import re
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css"
ALLOWED = {
    ("07-whiteboard-misc.css", "body:has(#library-media-selectbar"),
    ("08-consistency.css", "body:has(#library-media-selectbar"),
    ("graph-lazy.css", "body:has(#tab-graph"),
}


def test_no_new_body_has_rules():
    found = set()
    for path in sorted(CSS.glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"body:has\([#.]?[\w-]*", text):
            found.add((path.name, match.group(0)))
    assert found <= ALLOWED, sorted(found - ALLOWED)
