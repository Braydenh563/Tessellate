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
}


def test_no_new_body_has_rules():
    found = set()
    for path in sorted(CSS.glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"body:has\([#.]?[\w-]*", text):
            found.add((path.name, match.group(0)))
    assert found <= ALLOWED, sorted(found - ALLOWED)


def test_no_page_wide_has_keyed_on_a_tab():
    """A tab flip toggles `.hidden` on the pages. A `:has()` on body, :root
    or html that looks for `#tab-x` or a `.tab-page` is
    re-matched against every flip; the four toast rules that did it were 30
    to 45 percent of a tab switch's style time at 4x CPU (agent-remaining/
    lag-1029.md). `revealTab` sets `body[data-tab]` for them."""
    bad = []
    for path in sorted(CSS.glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for rule in re.finditer(r"([^{}]+)\{", text):
            for sel in re.split(r",\s*(?![^()]*\))", rule.group(1)):
                sel = " ".join(sel.split())
                head = re.match(r"^(?:@media[^{]*\{\s*)?((?::root|html|body)\b.*)", sel)
                if not head:
                    continue
                if re.search(r":has\([^)]*(#tab-|\.tab-page)", head.group(1)):
                    bad.append((path.name, sel[:90]))
    assert not bad, bad
