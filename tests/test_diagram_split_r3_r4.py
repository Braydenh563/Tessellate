"""DOCUMENTS_PLAN 22.4 R3 (the divider) and R4 (labels and the walkthrough).

What a diff can break is here; the pixels (a drag of N px moves the column N px, the reload restores it, the visible
words) are measured in a browser and named in docs/roadmap/HISTORY.md.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
SPLIT = (JS / "diagram-split.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MERMAID_JS = (JS / "documents-mermaid.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _rule(selector: str) -> str:
    start = CSS.index(selector + " {")
    return CSS[start : CSS.index("}", start)]


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-split.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.split.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_list_column_is_clamped_so_the_picture_keeps_240px():
    assert _math("m.clamp(100, 1000, 16)") == 224  # never under the list's old 14rem
    assert _math("m.clamp(900, 1000, 16)") == 1000 - 16 - 240
    assert _math("m.clamp(300.4, 1000, 16)") == 300
    assert _math("m.clamp(900, 300, 16)") == 224  # a body too small for both: the list keeps its least


def test_the_divider_is_the_sidebar_handle_wired_by_a_lazy_file():
    assert 'diagramSplit: ["/js/diagram-split.js"]' in MERMAID_JS
    assert 'ensureModule("diagramSplit")' in BUILDER and "diagramModel.split.wire(S)" in BUILDER
    assert 'handle.className = "sidebar-resize dgm-split-handle"' in SPLIT
    for needle in ('"separator"', '"tabindex", "0"', "trackSeparatorValue(", "prefs.set(KEY", "const STEP = 12", "const BIG = 40", "const KEEP = 240"):
        assert needle in SPLIT, needle
    assert "diagramModel.split = " in SPLIT


def test_the_divider_sets_a_column_variable_and_is_gone_on_a_phone():
    assert "--dgm-list" in _rule(".dgm-body.dgm-split")
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert ".dgm-split-handle" in narrow and "display: none" in narrow[narrow.index(".dgm-split-handle") :][:200]
    assert ".dgm-split-handle" in CSS[CSS.index('.dgm-dialog[data-view="source"] .dgm-dock') :][:300]


def test_the_direction_button_names_its_state_in_words():
    # 1661 D2 replaced the caption over four arrows with one cycling button that shows the arrow and the word.
    bar = (JS / "diagram-bar.js").read_text(encoding="utf-8")
    assert "Direction: ${WORD[dir]}. Press to turn it." in bar and "dgm-dirword" in bar
    assert ".dgm-dirs-caption" not in CSS


def test_undo_and_redo_keep_their_words_where_the_row_fits_and_connect_to_shows_its_text_on_wide_rows():
    assert 'b.classList.add("icon-only")' not in BUILDER
    assert ".dgm-hist .ph-text" in CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert "container-type" not in _rule(".dgm-pane")
    assert ".dgm-tight .dgm-connect .ph-text" in CSS and "dgm-tight" in SPLIT and "const TIGHT = 304" in SPLIT
    # Shown on every row by default; a phone (the narrow container rule) keeps only the arrow.
    assert "display: none" in CSS[CSS.index("@container (max-width: 599.98px)") :][CSS[CSS.index("@container (max-width: 599.98px)") :].index(".dgm-connect .ph-text") :][:60]


def test_the_empty_state_is_a_three_step_walkthrough_with_a_button_each():
    steps = (JS / "diagram-steps.js").read_text(encoding="utf-8")
    assert "Start a diagram" not in BUILDER and "Start a diagram" not in steps
    for words in ("Add a shape", "Name it", "Connect it"):
        assert f'"{words}"' in steps, words
    assert 'diagramSteps: ["/js/diagram-steps.js"]' in MERMAID_JS and 'ensureModule("diagramSteps")' in BUILDER
    assert "dgm-steps" in steps and "dgm-steps" in CSS


@needs_node
def test_an_unmounted_body_does_not_pull_a_saved_width_down_to_the_least():
    # Review finding 2: wired while the body is not laid out (width 0), a saved 400 px must stay 400 px.
    assert _math("m.clamp(400, 0, 0)") == 400
    assert _math("m.clamp(100, 0, 0)") == 224


def test_reset_and_resize_keep_the_tight_class_and_aria_max_true():
    # Review findings 1 and 3: Home / double-click re-derives dgm-tight; a resize refreshes aria-valuemax.
    home = SPLIT[SPLIT.index('event.key === "Home"') :][:400]
    assert "tight()" in home
    assert "aria-valuemax" in SPLIT[SPLIT.index("const tight = ") :][:500]
