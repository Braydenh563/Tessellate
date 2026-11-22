"""The OCR workspace's find marks every match in the extracted text (INBOX 853:
"when searching in the ocr workspace extracted text, I feel it should highlight
the key words").

Measured in Chromium (scratchpad/ui-sweeps/ocrfind853.js, a reading holding
"search" three times): typing it marks 3 occurrences on the app's find
highlight, the count reads "1 of 3", the current mark is the stronger accent
fill and sits inside the scroller; Enter and Shift+Enter move it ("2 of 3",
then wrapping to "3 of 3"); clearing the box removes every mark. The same at
390 wide in dark. This runs the splitting function in node against a small DOM
stand-in and pins the wiring.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
INDEX = index_html_text()


def _function(source: str, head: str) -> str:
    start = source.index(head)
    return source[start : source.index("\n}\n", start) + 3]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_every_occurrence_becomes_a_mark_and_clearing_restores_the_text():
    fn = _function(LIBRARY, "function ocrFindMarkRegion(")
    script = (
        """
const document = {
  createTextNode: (t) => ({ kind: "text", t }),
  createDocumentFragment: () => ({ kids: [], appendChild(n) { this.kids.push(n); } }),
  createElement: () => ({ kind: "mark", className: "", textContent: "" }),
};
function region(text) {
  const el = {
    text, classList: { contains: () => false }, kids: null,
    get textContent() { return this.kids ? this.kids.map((k) => k.t ?? k.textContent).join("") : this.text; },
    set textContent(v) { this.kids = null; this.text = v; },
    querySelector() { return this.kids && this.kids.some((k) => k.kind === "mark") ? {} : null; },
    replaceChildren(frag) { this.kids = frag.kids; },
  };
  return el;
}
"""
        + fn
        + """
const el = region("Search the notes. A search again, SEARCH!");
const marks = ocrFindMarkRegion(el, "search");
const joined = el.textContent;
const again = ocrFindMarkRegion(el, "");
console.log(JSON.stringify({ n: marks.length, texts: marks.map((m) => m.textContent), cls: marks[0].className, joined, restored: el.textContent, after: again.length }));
"""
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    got = json.loads(out)
    assert got["n"] == 3 and got["texts"] == ["Search", "search", "SEARCH"], "case kept, every one marked"
    assert got["cls"] == "global-find-hit", "the app's one find highlight, not a second look"
    assert got["joined"] == got["restored"] == "Search the notes. A search again, SEARCH!"
    assert got["after"] == 0


def test_the_count_is_of_occurrences_and_the_buttons_are_wired():
    assert "`${ocrFindCurrent + 1} of ${ocrFindHits.length}`" in LIBRARY
    for id_ in ("ocr-find-prev", "ocr-find-next"):
        assert f'id="{id_}"' in INDEX
        assert f'$("{id_}")?.addEventListener("click"' in LIBRARY
    assert 'event.key !== "Enter"' in LIBRARY and "ocrFindStep(event.shiftKey ? -1 : 1)" in LIBRARY


def test_the_current_match_scrolls_by_its_own_scroller_never_scrollintoview():
    body = "\n".join(
        line for line in _function(LIBRARY, "function ocrFindShowCurrent(").splitlines() if "//" not in line
    )
    assert "scrollIntoView" not in body and "scrollTop" in body
