"""L-world-class-70: the boot icon font is a subset, the full font is its fallback.

A glyph missing from an icon font draws nothing and logs nothing, so the two
things that must hold are checked from the files: the `.ph` font stack names
the subset first and the full font second (the browser fetches the second only
when a glyph is missing from the first), and the subset covers every icon the
code names. Regenerate with `python scripts/subset_phosphor.py`.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "frontend" / "vendor" / "phosphor"
CSS = (DIR / "style.css").read_text(encoding="utf-8")


def _script():
    spec = importlib.util.spec_from_file_location("subset_phosphor", ROOT / "scripts" / "subset_phosphor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_font_stack_is_subset_first_then_the_full_font():
    stack = re.search(r"\.ph \{[^}]*font-family:\s*([^;]+);", CSS).group(1)
    assert re.sub(r"\s*!important", "", stack) == '"Phosphor", "Phosphor Full"'
    faces = dict(re.findall(r'font-family: "([^"]+)";\s*src:\s*url\("\./([^"]+)"\)', CSS))
    assert faces == {"Phosphor": "Phosphor.woff2", "Phosphor Full": "Phosphor-full.woff2"}


def test_the_boot_face_is_the_small_file():
    assert (DIR / "Phosphor.woff2").stat().st_size < 70_000
    assert (DIR / "Phosphor-full.woff2").stat().st_size > 140_000


def test_the_subset_holds_every_icon_the_code_names():
    ttlib = pytest.importorskip("fontTools.ttLib")
    script = _script()
    points = script.codepoints()
    wanted = {points[name] for name in script.used_names(set(points))}
    assert len(wanted) > 500, "the scan found far fewer names than the app uses"
    have = set(ttlib.TTFont(DIR / "Phosphor.woff2").getBestCmap())
    assert wanted <= have, f"regenerate: python scripts/subset_phosphor.py ({len(wanted - have)} missing)"
    full = set(ttlib.TTFont(DIR / "Phosphor-full.woff2").getBestCmap())
    assert set(points.values()) <= full, "the fallback face must hold every icon in style.css"
    assert len(have) < len(full) // 2
