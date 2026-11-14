"""New document makes a new document, and that is the one showing (found
by the e2e suite, tests-e2e/specs/documents.spec.js, 2026-10-05).

Library, Create, New document on a session that had not opened Documents
yet opened the last document instead: the row switched tabs and pressed
`#doc-new` 160 ms later, before documents.js (fetched on the tab's first
visit) had bound that button, so nothing was made, and the tab's own loader
opened `docs[0]`. A person then typed a title and text into an existing
document believing it was new: measured in the browser, the seeded
"Sourdough method" was renamed and appended to, and no document was made.

Two fixes, each pinned here:

* the row waits for the tab (and so its code) and then makes the document
  itself, no timer;
* `openDocument` answers only its newest call: the tab's loader opening the
  last document and the new one opening race, and whichever fetch landed last
  used to win.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


def test_the_library_row_waits_for_the_tab_instead_of_a_timer():
    source = (JS / "library.js").read_text(encoding="utf-8")
    start = source.index('label: "ph:plus New document"')
    row = source[start : source.index("\n  },", start)]
    assert "setTimeout" not in row, row
    assert re.search(r"await switchTab\(\"documents\"\);\s*await createDocument\(\)", row), row


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def _run(scenario: str) -> dict:
    """Run documents.js's `loadDocumentsNow` and `openDocument` in node.

    Everything they call besides the two fetches is a no-op stand-in: a
    `with` over a proxy answers any free name with a function that returns
    itself, so the scenario reads only which document ends up open. A
    document's fetch takes `delays[id]` ms; the list takes 30 ms."""
    source = (JS / "documents.js").read_text(encoding="utf-8")
    declarations = "\n".join(
        line for line in source.splitlines() if line.startswith(("let docOpenSeq", "const docLoadSeen"))
    )
    opener = _function(source, "async function openDocument(id) {").replace(
        "async function openDocument(id) {", "globalThis.openDocument = async function (id) {", 1
    )
    loader = _function(source, "async function loadDocumentsNow(selectId) {").replace(
        "async function loadDocumentsNow(selectId) {",
        "globalThis.loadDocumentsNow = async function (selectId) {",
        1,
    )
    own = "currentDoc docDirty docs apiJson apiPagedList docOpenSeq docLoadSeen stub delays fetched".split()
    script = (
        """
let currentDoc = null, docDirty = false, docs = [];
const stub = new Proxy(function () {}, { get: (t, k) => (k === "then" ? undefined : k === Symbol.toPrimitive ? () => "" : stub), apply: () => stub, set: () => true });
const delays = { 2: 5, 3: 50, 9: 5 };
const fetched = [];
function apiJson(path) {
  const id = Number(path.split("/").pop());
  return new Promise((resolve) => setTimeout(() => { fetched.push(id); resolve({ id, title: "d" + id, content: "" }); }, delays[id]));
}
function apiPagedList() {
  return new Promise((resolve) => setTimeout(() => resolve([{ id: 3 }, { id: 2 }, { id: 1 }]), 30));
}
"""
        + declarations
        + f"\nconst own = {json.dumps(own)};\n"
        + "const scope = new Proxy({}, { has: (t, k) => !(k in globalThis) && !own.includes(k), get: (t, k) => (k === Symbol.unscopables ? undefined : stub) });\n"
        + "with (scope) {\n"
        + opener
        + "\n"
        + loader
        + "\n}\n(async () => {\n"
        + scenario
        + "\nconsole.log(JSON.stringify({ open: currentDoc && currentDoc.id, fetched }));\n})();\n"
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_newest_open_wins_when_an_older_one_lands_last():
    out = _run(
        """
const older = openDocument(3); // the tab's loader: the last document
const newer = openDocument(9); // New document, made a moment later
await Promise.all([older, newer]);
"""
    )
    assert out["fetched"] == [9, 3], out  # the older fetch did land last
    assert out["open"] == 9, f"the older open won: {out}"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_loader_does_not_open_the_last_document_over_one_asked_for():
    """`#/docs/2` on a fresh load: the route opens document 2 while the tab's
    loader is still fetching the list, and the loader then opened the newest
    document (3) over it. Measured in the browser before the fix: the address
    said `#/docs/2` and the editor held document 3."""
    out = _run(
        """
const loading = loadDocumentsNow(null); // the tab's own first load
delays[2] = 60; // the editor engine loads first, so this open is slow
const routed = openDocument(2);         // the address names document 2
await Promise.all([loading, routed]);
"""
    )
    assert out["open"] == 2, f"the loader opened the last document instead: {out}"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(
    "scenario",
    [
        # the route's open lands first, the loader starts after (DC7)
        "delays[2] = 60; delays[9] = 60;\nconst routed = openDocument(2);\nconst loading = loadDocumentsNow(null);\nawait Promise.all([loading, routed]);",
        # New document asked before the loader starts
        "delays[2] = 60; delays[9] = 60;\nconst routed = openDocument(9);\nawait new Promise((r) => setTimeout(r, 1));\nconst loading = loadDocumentsNow(null);\nawait Promise.all([loading, routed]);",
    ],
)
def test_an_open_asked_before_the_loader_starts_is_honoured(scenario):
    """The class behind DC7: any open requested before the list loads, not
    only one made while it loads, beats the loader's own default."""
    out = _run(scenario)
    assert out["open"] in (2, 9) and 3 not in out["fetched"], out


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_loader_still_opens_the_last_document_when_nothing_was_asked():
    out = _run("await loadDocumentsNow(null);")
    assert out["open"] == 3, out


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_later_visit_opens_the_last_document_again_after_a_settled_ask():
    """An ask settles at the first load, so a second visit with nothing open
    (the open document was deleted) is not stuck on an old request."""
    out = _run(
        "await openDocument(2);\nawait loadDocumentsNow(null);\ncurrentDoc = null;\nawait loadDocumentsNow(null);"
    )
    assert out["open"] == 3, out


@pytest.mark.parametrize("kind, button", [("board", '$("wb-boards-new")'), ("mindmap", 'wbNewUntitledBoard("map")')])
def test_new_board_and_new_mind_map_wait_for_the_boards_code(kind, button):
    """The same shape for boards (found by tests-e2e/specs/boards.spec.js):
    Create, New board pressed `#wb-boards-new` straight after opening the
    Boards sub-tab, whose code (whiteboard.js) is fetched on that first
    visit, so the button had no listener yet and nothing happened: no
    gallery, no board. Measured: the click reached the button, and
    `createNewBoard` was never called."""
    source = (JS / "library.js").read_text(encoding="utf-8")
    start = source.index(f"  {kind}: {{\n")
    row = source[start : source.index("\n  },", start)]
    wait = row.find('await ensureModule("boards")')
    press = row.find(button)
    assert 0 <= wait < press, row


def test_a_door_into_a_library_sub_tab_waits_for_the_library():
    """Graph's Mind maps button (wiring.js, always loaded) switched to the
    Library and pressed its Boards sub-tab at once; the sub-tab's handler is
    library.js's, fetched on the Library's first visit, so the press landed
    on nothing and the button arrived at the Library's All view (measured:
    `library-view-documents` showing, not `library-view-whiteboard`). Any
    file outside the Library's own bundle that presses a Library sub-tab
    must await the tab first."""
    bundle = {
        "library.js", "documents.js", "documents-code.js", "documents-prose.js",
        "margin-reader.js", "undo-store.js", "whiteboard.js", "whiteboard-map.js",
        "whiteboard-library.js", "whiteboard-commands.js", "whiteboard-format.js",
        "whiteboard-history.js", "whiteboard-interchange.js", "whiteboard-templates.js",
    }
    offenders = []
    for path in sorted(JS.glob("*.js")):
        if path.name in bundle:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "#library-subtabs" in line and ".click()" in line:
                before = "\n".join(lines[max(0, i - 3) : i])
                waited = 'await switchTab("library")' in before or 'switchTab("library").then(' in before
                if 'switchTab("library")' in before and not waited:
                    offenders.append(f"{path.name}:{i + 1}")
    assert not offenders, offenders


def test_a_press_on_a_boards_button_from_outside_waits_for_the_boards_code():
    """The class behind New board, New mind map and the Dashboard's boards
    widget's New board (navigation.js): FE-03(c) made the Library tab load
    library.js alone, so a `$("wb-...").click()` from a file outside the
    boards' bundle reached a button with no listener on a first visit and did
    nothing. v0.3.32 loaded the whole bundle with the tab and these worked.
    Every such press waits for `ensureModule("boards")` in the lines before
    it. Since D22 (2026-11-11) that is the `boards` bundle, which carries the
    whiteboard files; `library` no longer does."""
    bundle = {
        "documents.js", "documents-code.js", "documents-prose.js", "margin-reader.js",
        "whiteboard.js", "whiteboard-map.js", "whiteboard-library.js", "whiteboard-commands.js",
        "whiteboard-format.js", "whiteboard-history.js", "whiteboard-interchange.js",
        "whiteboard-templates.js",
    }
    offenders = []
    for path in sorted(JS.glob("*.js")):
        if path.name in bundle:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if '$("wb-boards-new' in line and ".click()" in line:
                before = "\n".join(lines[max(0, i - 6) : i])
                if 'ensureModule("boards")' not in before:
                    offenders.append(f"{path.name}:{i + 1}")
    assert not offenders, offenders
