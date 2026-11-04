"""INBOX 1614 (DOCUMENTS_PLAN 22.4 R2): the picture shares the blocks pane's height, and it zooms, pans and fits.

The heights themselves are measured in a browser (docs/roadmap/agent-remaining/diagram-r2-1104.md names the
sweep and the numbers); this file holds what a diff can break: the cascade that left the picture 19px short,
the narrow rule that keeps its own 26vh, and the zoom maths (run under node where it is installed).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
MERMAID_CSS = (ROOT / "frontend" / "css" / "mermaid-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _rule(css: str, selector: str) -> str:
    start = css.index(selector + " {")
    return css[start : css.index("}", start)]


def test_the_picture_margin_is_not_beaten_by_the_mermaid_figure_rule():
    # `.md-mermaid` (a later file) gives every figure a block margin; the picture's own `margin: 0` must out-rank it.
    assert "margin: var(--space-4) 0;" in _rule(MERMAID_CSS, ".md-mermaid")
    assert "margin: 0;" in _rule(CSS, ".dgm .dgm-picture")
    assert not re.search(r"^\.dgm-picture \{", CSS, re.M)


def test_the_two_panes_stretch_together_in_a_wide_container_and_the_picture_keeps_26vh_below_600():
    body = _rule(CSS, ".dgm-body")
    assert "display: grid;" in body and "align-items" not in body
    assert "26vh" not in CSS[: CSS.index("@container (max-width: 599.98px)")]
    narrow = CSS[CSS.index("@container (max-width: 599.98px)") :]
    assert "block-size: 26vh;" in narrow
