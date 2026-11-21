"""L-world-class-105 (22.3): one Phosphor weight app-wide.

The vendored font is the regular weight only, so a weight class (`ph-bold`,
`ph-fill`, ...) draws nothing different: the model menu's pinned pin carried
`ph-fill` for a fill that never loaded (its pressed state is the accent ink).
Measured 2026-11-21 at 1093x614 and 1440x900: every drawn icon in the shell,
the Notes list and Settings is Phosphor at 400
(`scratchpad/ui-sweeps/design-remeasure-105.js`)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
WEIGHT_CLASS = re.compile(r"\bph-(?:bold|fill|light|thin|duotone)\b")


def _sources():
    for path in FRONTEND.rglob("*"):
        if path.suffix in {".js", ".css", ".html"} and "vendor" not in path.parts:
            yield path


def test_no_icon_asks_for_a_weight_the_font_does_not_have():
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in _sources() for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if WEIGHT_CLASS.search(line)]
    assert not hits, hits


def test_the_vendored_icon_font_is_one_weight():
    css = (FRONTEND / "vendor" / "phosphor" / "style.css").read_text(encoding="utf-8")
    weights = set(re.findall(r"font-weight:\s*([^;]+);", css))
    assert weights == {"normal"}, weights
