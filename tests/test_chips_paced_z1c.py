"""z1c-1101 leftover: a key in a long note must not rescan and redraw the attachment chips.

At 200,000 characters `renderEntryAttachmentChips` cost 0.29 ms a key (its regex reads the whole
text, then the row is rebuilt even when nothing changed). The class: every per-key reader of the
whole text paces past `CAPTURE_COUNT_SYNC`-sized text, and a redraw that would draw the same row
is skipped.
"""

import re

from tests._app_js import app_js_text

TEXT = app_js_text()


def _body(name):
    start = TEXT.index(f"function {name}(")
    end = TEXT.index("\n}\n", start)
    return TEXT[start:end]


def test_the_chips_skip_a_redraw_that_draws_the_same_row():
    body = _body("renderEntryAttachmentChips")
    assert "chipsSig" in body
    assert body.index("chipsSig") < body.index("replaceChildren")


def test_a_key_in_a_long_text_is_paced():
    body = _body("renderEntryAttachmentChips")
    assert "paced" in body and "CHIPS_PACE_CHARS" in TEXT
    assert re.search(r"length\s*[<>]=?\s*CHIPS_PACE_CHARS", body)


def test_every_input_caller_asks_for_pacing():
    callers = re.findall(r'addEventListener\("input", \(\) => renderEntryAttachmentChips\(([^)]*)\)', TEXT)
    assert callers, "the input callers moved"
    assert all("paced" in args for args in callers), callers
    assert "renderEntryAttachmentChips({ paced: true })" in TEXT or 'renderEntryAttachmentChips("entry-content", "entry-attachment-chips", { paced: true })' in TEXT
