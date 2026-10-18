"""The Playwright specs open tabs by name (`openTab(page, "x")` clicks
`#tab-btn-x`). A tab that was renamed (Documents became Library) made the
Performance workflow's frame spec wait out its whole 180 s timeout on a click
that could never land, and skip every scenario after it."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
TABS = set(re.findall(r'id="tab-btn-([a-z]+)"', INDEX))


def test_every_tab_the_e2e_specs_open_exists():
    missing = []
    for spec in sorted((ROOT / "tests-e2e").rglob("*.js")):
        if "node_modules" in spec.parts:
            continue
        text = re.sub(r"//[^\n]*", "", spec.read_text(encoding="utf-8"))
        named = set(re.findall(r'openTab\(\s*page\s*,\s*"([a-z]+)"', text))
        named |= set(re.findall(r"#tab-btn-([a-z]+)", text))
        for loop in re.findall(r"for \(const tab of \[([^\]]+)\]", text):
            named |= set(re.findall(r'"([a-z]+)"', loop))
        missing += [f"{spec.name}: {tab}" for tab in sorted(named - TABS)]
    assert not missing, missing
