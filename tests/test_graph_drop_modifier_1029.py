"""Audit 1029 rank 43 (G15, G14): a plain drag only moves a note, and the first
selection does not move the camera under the next click.

- G15: dragging one note onto another opened "How are these connected?" with
  nothing to say it would. Linking by drop now needs Alt held at the start of
  the drag (Shift already pins), so a plain drag places the note and nothing else.
- G14: not reproduced (see the last test): the selection dock is already a
  menu for the refit.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
HELP_CHAT = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@needs_node
def test_a_drop_target_is_looked_for_only_while_alt_is_held() -> None:
    script = (
        "let hits = 0; const graphNodeUnder = () => { hits += 1; return { id: 'b' }; };\n"
        + _function(CANVAS, "gcDropTargetFor")
        + """
        const full = { size: "full", dragGroup: [], dragTopic: null };
        const node = { _dragAlt: false };
        const plain = gcDropTargetFor(full, node, { x: 1, y: 2 });
        const hitsPlain = hits;
        node._dragAlt = true;
        console.log(JSON.stringify({
          plain, hitsPlain,
          alt: gcDropTargetFor(full, node, { x: 1, y: 2 })?.id,
          pane: gcDropTargetFor({ ...full, size: "pane" }, node, { x: 1, y: 2 }),
          group: gcDropTargetFor({ ...full, dragGroup: [{}] }, node, { x: 1, y: 2 }),
          topic: gcDropTargetFor({ ...full, dragTopic: {} }, node, { x: 1, y: 2 }),
        }));
        """
    )
    out = _run(script)
    assert out["plain"] is None and out["hitsPlain"] == 0, "a plain drag does not even look for a target"
    assert out["alt"] == "b"
    assert out["pane"] is None and out["group"] is None and out["topic"] is None


def test_the_drag_reads_alt_at_its_start_and_the_move_uses_the_helper() -> None:
    assert "node._dragAlt = Boolean(event.sourceEvent && event.sourceEvent.altKey);" in CANVAS
    assert "s.dropTarget = gcDropTargetFor(s, node, { x: wx, y: wy });" in CANVAS
    assert "d.dragAlt = Boolean(event.sourceEvent && event.sourceEvent.altKey);" in GRAPH
    assert "d.dragAlt ? graphNodeUnder(d, event) : null" in GRAPH


def test_help_says_how_to_link_by_drop() -> None:
    panel = HTML[HTML.index('id="graph-help-panel"') :]
    panel = panel[: panel.index("</div>")]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", panel))
    assert "Hold Alt and drop one note onto another" in text
    assert "Hold Alt and drop one note onto another to link" in HELP_CHAT


def test_the_selection_dock_is_a_menu_for_the_refit_so_a_first_selection_moves_nothing() -> None:
    """G14 did not reproduce on this head: measured at 1440x900, 1280x720 and
    1024x700 on 36 notes, selecting a note moved the camera 0 px and called
    `gcRefitForPanels` 0 times, because the dock is a `.dock` straight under
    `.graph-overlay`, which `GC_FIT_MENUS` names. This pins that, so moving the
    dock out of the overlay (or narrowing the menu list) fails here."""
    menus = re.search(r'const GC_FIT_MENUS = "(.*?)";', CANVAS).group(1)
    assert "#graph-card > .graph-overlay > .dock" in menus
    html = HTML[HTML.index('<div class="graph-overlay">') :]
    assert html.index('id="graph-selection-dock"') < html.index("</section>")
    assert re.search(r'<div class="dock graph-selection-dock[^"]*" id="graph-selection-dock"', html)
    assert "!entry.target.matches(GC_FIT_MENUS)" in CANVAS
