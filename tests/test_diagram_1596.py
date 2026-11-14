"""INBOX 1596: the Diagram builder's found-not-fixed list.

(a) was read as a boot race (`switchTab` straight after boot threw "addEventListener of null" at library.js and
documents.js). Trials (28) across 0 to 300 ms after unlock, at 1x, 4x and 6x CPU, in a fresh profile, threw nothing; the
same two lines threw only when the sweep had deleted every `.modal-overlay` (including the static `#binned-overlay`
and `#doc-ai-panel`) before the bundle first loaded. So the cause was the sweep, and the class guard is the one that
already exists (every id a script looks up is in the markup) plus the one below: nothing removes a static dialog.
(b) to (d) are pinned below.
"""

from __future__ import annotations

from tests._help_text import help_more_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_DIR = ROOT / "frontend" / "js"
BUILDER = (JS_DIR / "diagram-builder.js").read_text(encoding="utf-8")


def test_no_script_removes_a_static_dialog_of_index_html():
    # The static overlays are wired once, at the bundle's first load; deleting one would make the next lazy load throw
    # "addEventListener of null" (1596 a). Only elements a script made may be removed.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="binned-overlay"' in html and 'id="doc-ai-panel"' in html
    bad = []
    for path in JS_DIR.glob("*.js"):
        text = path.read_text(encoding="utf-8")
        for name in ("binned-overlay", "doc-ai-panel"):
            if re.search(rf'(?:\$|getElementById)\("{name}"\)\??\.remove\(\)', text):
                bad.append(f"{path.name}: {name}")
        if re.search(r'querySelectorAll\(["\']\.modal-overlay["\']\)\.forEach\([^)]*\.remove\(\)', text):
            bad.append(f"{path.name}: every .modal-overlay")
    assert not bad, bad


def test_a_source_the_blocks_cannot_place_draws_its_error_not_the_empty_hint():
    draw = BUILDER.split("function drawPicture(S) {", 1)[1].split("// --- the tree", 1)[0]
    # Empty is a header and nothing else; a kept line (text that is no diagram, a dangling arrow) is drawn so the
    # picture area carries mermaidFailure.note's reason, and drawing never rewrites the source.
    assert "const empty = !source.trim() || (!S.plain && blank && bare);" in draw
    # Intent kept (DD-4, 1107 moved the call): the failure is drawn by diagram-picture.js `failure`, which still builds
    # mermaidFailure.note's reason, now under the last good picture; the builder only hands it the result.
    assert "sequenceDiagram\\b" in draw and "diagramModel.picture.failure(S, result, source, smallButton)" in draw
    assert "S.io.set" not in draw
    picture = (JS_DIR / "diagram-picture.js").read_text(encoding="utf-8")
    failure = picture.split("function failure(", 1)[1].split("diagramModel.picture =", 1)[0]
    assert "mermaidFailure.note(error, source)" in failure
    # The picture is kept and marked stale (the CSS dims it), an error new to the pane is an alert and a repeat a status,
    # and the "tall for this pane" offer is hidden because there is no current picture to offer it for.
    assert 'toggle("dgm-picture-stale", !result.svg)' in failure
    assert 'setAttribute("role", fresh ? "alert" : "status")' in failure
    assert 'S.sideways?.classList.add("hidden")' in failure
    assert "replaceChildren(note)" in failure and ".md-mermaid-img" in failure
    assert ".dgm-picture-stale" in (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


KINDS = (JS_DIR / "diagram-kinds.js").read_text(encoding="utf-8")


def test_a_kinds_render_keeps_the_rows_that_did_not_change_as_the_flowchart_does():
    render = KINDS.split("  function render(S) {", 1)[1].split("\n  }\n", 1)[0]
    assert "kit.reconcile(S.tree, built)" in render and "S.tree.replaceChildren" not in render
    assert "S.cache = fresh" in render and "kit.stops(S, stop)" in render
    assert "if (had && document.activeElement !== stop) stop?.focus();" in render
    build = KINDS.split("  function buildBlock(S, row, level, fresh) {", 1)[1].split("  function buildRow(", 1)[0]
    # A row is kept only for the same node object with the same fields: the menu's actions hold the node.
    assert "hit.sig === sig && hit.node === row.node" in build and "kids.map((k) => fresh.get(k.dataset.key))" in build
    fields = KINDS.split("  function fieldsOf(S, row, level, kids) {", 1)[1].split("\n  }\n", 1)[0]
    # Everything a row draws or its menu offers is in the signature.
    for field in ("row.fixed", "n.type", "S.k.text(n)", "meta", "kind", "n.shape", "n.arrow", "n.act", "n.pos", "n.kw", "n.actor", "n.from", "n.to", "Boolean(row.kids)"):
        assert field in fields, field
    assert "reconcile, stops };" in BUILDER


def test_the_dock_is_one_row_at_320_because_suggest_folds_into_the_more_menu():
    css = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
    rule = css.split(".dgm-compact .dgm-suggest {", 1)[1].split("}", 1)[0]
    assert "display: none;" in rule
    #: The narrow fold moved from the builder's more() to diagram-kindbar.js's fold() (e768ad94, the builder's
    #: gzip cap); the same rows are read there.
    more = (JS_DIR / "diagram-kindbar.js").read_text(encoding="utf-8").split("  function fold(S, DIRS, suggestMenu) {", 1)[1].split("\n  }\n", 1)[0]
    # The hidden button's rect is empty, so the menu anchors the suggestions to its own trigger.
    assert "S.suggestBtn && matchMedia(COMPACT).matches" in more
    assert "ph:sparkle Suggest…" in more and ".dgm-more button" in more
    help_text = help_more_text()
    assert "Suggest (... on a phone)" in help_text
