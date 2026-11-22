"""L-graph-20 G29: a return to the Graph tab glided the old picture toward a frame the first tick then replaced.

Measured at 2,000 notes, 4x CPU: the panels showing on return fired the panel refit while the map was being
read again, an eased 25 px glide away from the camera and an instant snap back, with a heavy frame at each
step. The refit now waits for the read, whose first tick frames the map.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parent.parent
CANVAS = unwrapped((ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8"))


def _refit_calls(state: str) -> int:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    found = re.search(r"^function gcRefitForPanels\(.*?^\}", CANVAS, re.S | re.M)
    assert found
    script = (
        "let fits = 0; const fitGraphToView = () => { fits += 1; }; const frameTree = () => {};\n"
        + found.group(0)
        + f"\ngcRefitForPanels({{ zoom: {{}}, svg: {{}}, nodes: [{{}}], dims: {{ w: 1, h: 1 }}, fittedOnce: true, {state} }});"
        + "\nconsole.log(fits);"
    )
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return int(run.stdout)


def test_the_panel_refit_waits_while_the_map_is_read_again() -> None:
    assert _refit_calls("refitPending: false") == 1
    assert _refit_calls("refitPending: true") == 0


def test_the_flag_is_set_for_a_reload_of_a_shown_map_and_cleared_after_the_read() -> None:
    body = CANVAS[CANVAS.index("s.refitPending = reframe"):]
    assert "s.refitPending = reframe && Boolean(s.shown);" in body
    assert body.index("await apiJson(endpoint)") < body.index("s.refitPending = false;")
