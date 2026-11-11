"""The Suggested links head's "Link all above 70%" (WORLD_CLASS_PLAN item 92).

The control was already on the row (`linkSure`, the integration's own build);
what it lacked, and what the world-class branch's version (a749b9d) had, is
checked here: it asks first (it links many pairs at once), it counts the pairs
that actually linked rather than the ones it tried, a failed link leaves its row
where it was instead of marking it done, and the Links help line says it exists.
"""

from __future__ import annotations

from pathlib import Path
from tests import _js_scope

INBOX = _js_scope.unwrapped((Path(__file__).resolve().parents[1] / "frontend" / "js" / "suggestions-inbox.js").read_text(encoding="utf-8"))


def _linkSure() -> str:
    return INBOX.split("const linkSure = smallButton(", 1)[1].split("const tools", 1)[0]


def test_it_asks_before_linking_many_pairs():
    handler = _linkSure()
    assert "confirmDialog(" in handler and "LINK_ALL_AT" in handler
    assert INBOX.count("const LINK_ALL_AT = 0.7;") == 1


def test_it_counts_the_pairs_that_linked_not_the_ones_it_tried():
    handler = _linkSure()
    assert "linked++" in handler or "linked += 1" in handler
    assert "Linked ${linked} of" in handler
    # A row's link says whether it worked.
    row = INBOX.split("const linkIt = async", 1)[1].split("rowState.link = linkIt", 1)[0]
    assert "return false" in row and "return true" in row


def test_a_failed_link_does_not_mark_its_row_done():
    row = INBOX.split("const linkIt = async", 1)[1].split("rowState.link = linkIt", 1)[0]
    assert row.index("return false") < row.index('inboxDone("links", row)')


def test_the_links_help_line_names_it():
    line = next(h for h in INBOX.split("const INBOX_HELP = [", 1)[1].split("];", 1)[0].splitlines() if h.strip().startswith('"Links:'))
    assert "Link all above 70%" in line
