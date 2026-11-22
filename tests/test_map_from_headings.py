"""A document's headings as a mind map (MINDMAP_PLAN decision 35, the audit's
M5 second half): the outline `wbMapHeadingsOutline` hands the Markdown import.

The marked region of whiteboard-map.js (`WB-MAP-HEADINGS-BEGIN` to `-END`) is
pure string work, so node runs it here; the map it makes is checked in the
browser by `scratchpad/ui-sweeps/mmd2-1005-maptodochead.js`.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = ROOT / "frontend" / "js" / "whiteboard-map.js"


def _region() -> str:
    text = frontend_text("whiteboard-map.js")
    start = text.index("// WB-MAP-HEADINGS-BEGIN")
    end = text.index("// WB-MAP-HEADINGS-END")
    return text[start:end]


def _outline(cases: list[tuple[str, str]]) -> list:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = _region() + "\nconst cases = " + json.dumps(cases) + ";\n" + (
        "console.log(JSON.stringify(cases.map(([t, title]) => wbMapHeadingsOutline(t, title))));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_one_top_heading_is_the_centre_and_levels_nest():
    text = "# Trip\n\nIntro.\n\n## Pack\n\n### Passport\n\n## Book\n"
    assert _outline([(text, "Doc")]) == ["- Trip\n  - Pack\n    - Passport\n  - Book"]


def test_several_top_headings_hang_under_the_title():
    text = "## One\n### One a\n## Two\n"
    assert _outline([(text, "My doc")]) == ["- My doc\n  - One\n    - One a\n  - Two"]


def test_a_skipped_level_hangs_one_down_and_code_is_not_a_heading():
    text = "# Root\n#### Deep\n```\n# not a heading\n```\n## Next ##\n"
    assert _outline([(text, "")]) == ["- Root\n  - Deep\n  - Next"]


def test_no_headings_is_none():
    assert _outline([("Just prose.\n\n- a list", "Doc")]) == [None]
