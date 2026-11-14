"""The Library tab loads library.js alone (audit 2026-10-05, FE-03(c)).

One click on Library fetched both editors, d3 and the whiteboard to draw a
list. `libraryList` is library.js on its own; the `library` bundle still
holds it, so a document or a board brings the whole surface. Every editor
function library.js calls has to be one of `library`'s stand-ins, or the
call throws while the editors are absent: this test reads the calls.
`scratchpad/ui-sweeps/perf2-1005-libsplit.js` measured it in a browser:
the tab fetched library.js only, All and Documents drew, Boards fetched the
editors, a document opened, no page errors.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
EDITORS = ["undo-store.js", "documents-code.js", "documents-prose.js", "documents.js", "whiteboard-map.js", "whiteboard.js"]
APP = (JS / "app.js").read_text(encoding="utf-8")


def _table(name: str) -> str:
    start = APP.index(f"const {name} = {{")
    return APP[start : APP.index("\n};\n", start)]


def test_the_library_tab_takes_the_list_bundle():
    assert 'library: "libraryList"' in APP and 'documents: "library"' in APP
    modules = _table("LAZY_MODULES")
    #: The list's own stylesheet rides with it (library-lazy.css's header).
    #: library-links.js (the Links tab's folders and cards) is list-only too.
    #: undo-store.js since DX11 (audit 1102): a purge from the list forgets the item's stored history.
    assert re.search(r'libraryList: \[("/css/library-lazy\.css", )?("/js/undo-store\.js", )?"/js/library\.js"(, "/js/library-links\.js")?\]', modules)
    library = re.search(r"\n  library: \[(.*?)\]", modules, re.S).group(1)
    assert '"/js/library.js"' in library, "the whole surface still includes the list"


def test_every_editor_call_from_the_list_is_a_stand_in():
    defined = set()
    #: A file the list bundle itself loads is present whenever library.js is.
    listed = re.search(r"libraryList: \[(.*?)\]", _table("LAZY_MODULES")).group(1)
    for name in [n for n in EDITORS if f'"/js/{n}"' not in listed]:
        defined |= set(re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", (JS / name).read_text(encoding="utf-8"), re.M))
    code = "\n".join(
        line for line in (JS / "library.js").read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("//")
    )
    used = {n for n in defined if re.search(r"(?<![\w$.])" + re.escape(n) + r"(?![\w$])", code)}
    entry = _table("LAZY_ENTRY_POINTS")
    library = re.search(r"\n  library: \[(.*?)\]", entry, re.S).group(1)
    stand_ins = set(re.findall(r'"([A-Za-z_$][\w$]*)"', library))
    #: Since D22 (2026-11-11) the board code is the `boards` bundle, so the list's calls into it
    #: are `boards`' stand-ins, installed in lazy-entries.js.
    extra = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    boards = re.search(r"installStandIns\(\{.*?\n  boards: \[(.*?)\]", extra, re.S).group(1)
    stand_ins |= set(re.findall(r'"([A-Za-z_$][\w$]*)"', boards))
    missing = sorted(used - stand_ins)
    assert not missing, f"library.js names editor functions with no stand-in: {missing}"
