"""A narrow documents sidebar puts its tab strip under the toggle (audit FE-19).

At 1024 the sidebar is 192px and "Outline" ran 7px under the collapse
toggle. The decision (DOCUMENTS_PLAN, decisions): below a 14rem content box
the strip starts one toggle-height down, full width, with less side room per
tab. Measured by scratchpad/ui-sweeps/perf2-1005-docside.js (in git history).
"""

from __future__ import annotations

import re
from pathlib import Path

_CSSDIR = Path(__file__).resolve().parents[1] / "frontend" / "css"
CSS = (_CSSDIR / "07-whiteboard-misc.css").read_text(encoding="utf-8")
# The strip's rules moved to library-lazy.css with the Library bundle (L308); the query is split between the two.
LAZY = (_CSSDIR / "library-lazy.css").read_text(encoding="utf-8")


def test_the_sidebar_is_a_named_container():
    assert re.search(r"#doc-sidebar\s*\{\s*container:\s*doc-sidebar\s*/\s*inline-size;", CSS)


def test_a_narrow_sidebar_drops_the_lane_and_the_pull_up():
    q = "@container doc-sidebar (width < 14rem)"
    block = "".join(t[t.index(q) : t.index("\n}\n", t.index(q))] for t in (CSS, LAZY))
    assert "padding-right: 0" in block
    assert "var(--sidebar-toggle-size)" in block and "margin-top" in block
    #: --space-1 since L-world-class-39: at --space-2 the strip ran 5px past the sidebar.
    assert "padding-inline: var(--space-1)" in block
