"""Read view headings (audit 1102 DX23).

The renderer demotes `#` to `h3` because the app's page already has an `h1` and
an `h2`, so `####`, `#####` and `######` all became `h6` and a screen reader's
heading list merged three levels. Each heading now carries `aria-level` (the
demoted level, 3 to 8). And the Read view prepends the document's name as a
heading when the body does not open on it; the contents list left that title
out of its entries (it is not the author's text).
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_every_demoted_heading_keeps_its_level_in_aria_level() -> None:
    source = (JS / "navigation.js").read_text(encoding="utf-8")
    block = source[source.index("const level = Math.min(6, heading[1].length + 2);"):]
    block = block[: block.index("container.appendChild(el);")]
    assert 'el.setAttribute("aria-level", heading[1].length + 2)' in block


def test_the_contents_list_leaves_the_added_title_out() -> None:
    documents = documents_text()
    preview = documents[documents.index("function renderDocPreview("):]
    preview = preview[: preview.index("\n}\n")]
    assert preview.index("head?.remove()") < preview.index("mdFillTocs(preview)") < preview.index("preview.prepend(head)")
