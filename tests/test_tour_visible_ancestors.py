"""L685's sweep pass: scratchpad/ui-sweeps/toursteps.js at 1440 found the graph section's "Moving around" ring round
`#graph-zoom` while `#graph-card` stood at opacity 0 (about 800ms after the tab opens). `tourVisible` read the
control's own opacity, which is 1; opacity multiplies down the tree, so the wait now reads the product."""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _visible() -> str:
    return re.search(r"function tourVisible\(el\) \{(.*?)\n\}", app_js_text(), re.S).group(1)


def test_a_target_in_a_faded_ancestor_is_not_visible() -> None:
    body = _visible()
    assert "for (let n = el.parentElement; n && n !== document.documentElement && seen > 0.05; n = n.parentElement)" in body
    assert 'seen *= Number(getComputedStyle(n).opacity || "1")' in body
    assert body.rstrip().endswith("return seen > 0.05;")
