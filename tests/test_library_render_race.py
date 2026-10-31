"""A Library render that was overtaken never draws (found by the e2e suite,
tests-e2e/specs/notes.spec.js, 2026-10-05).

Ctrl+K, "Open the bin" on a session that had not visited the Library yet
showed "Nothing of this kind yet." under "Everything 142". The reveal ticks
"Include the bin" while `/library` is still loading, and that tick renders
with a cross-fade: `document.startViewTransition(updateDOM)` runs `updateDOM`
a frame later, holding the `items` it filtered from the still-empty list.
The load then answered and drew all 142 cards at once (quiet, no fade), and
the late cross-fade callback replaced them with its empty list. Measured in
the browser: the fade callback ran 84 ms after the fresh draw, and the grid
ended with 0 cards and the empty state showing.

So every render takes a number, and a render's DOM update draws only while
its number is still the newest: a late one gives way to whatever came after.
Run here in node with the smallest stand-ins `renderLibrary` needs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "frontend" / "js" / "library.js"


def _function(source: str, head: str) -> str:
    start = source.index(head)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_late_cross_fade_does_not_draw_over_a_newer_render():
    source = LIBRARY.read_text(encoding="utf-8")
    declarations = "\n".join(
        line for line in source.splitlines() if line.startswith("let libraryRenderGen")
    )
    render = _function(source, "function renderLibrary(options) {")
    script = (
        """
const drawn = [];
const pending = [];
function el() {
  return { value: "", checked: false, textContent: "", title: "", disabled: false, children: [], childNodes: [],
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    replaceChildren() { this.children = []; }, append(...k) { this.children.push(...k); },
    appendChild(k) { this.children.push(k); }, setAttribute() {}, querySelector() { return null; } };
}
const nodes = {};
function $(id) { return (nodes[id] = nodes[id] || el()); }
const document = { activeElement: null, documentElement: { dataset: {} },
  createElement: () => el(), createDocumentFragment: () => el(),
  startViewTransition(cb) { pending.push(cb); } };
const reducedMotionWanted = () => false;
let libraryItems = [], libraryKind = "all", libraryTruncated = {};
let librarySemanticIds = null, libraryPageSize = "all", libraryCurrentPage = 1;
let libraryColumnsShown = 1, librarySelection = new Set();
const LIBRARY_KINDS = [], LIBRARY_EMPTY_SAYS = {};
function watchLibraryColumns() {}
function libraryColumnCount() { return 1; }
function libraryView() { return "cards"; }
function librarySorted(items) { return items; }
function renderLibraryContextBars() {}
function ensureLibraryGridStop() {}
function libraryCard(item) { return item.id; }
function renderIncrementally(grid, items, make) { drawn.push(items.map(make)); }
"""
        + declarations
        + "\n"
        + render
        + """
// The reveal's tick: a render with the fade, before the list has loaded.
renderLibrary();
// The load answers: a quiet render draws at once.
libraryItems = [{ id: 1, kind: "note" }, { id: 2, kind: "document" }];
renderLibrary({ quiet: true });
// A frame later the first render's cross-fade runs its callback.
pending.forEach((cb) => cb());
console.log(JSON.stringify(drawn));
"""
    )
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    drawn = json.loads(result.stdout.strip().splitlines()[-1])
    assert drawn[-1] == [1, 2], f"a late cross-fade drew {drawn[-1]} over the loaded list"
