"""A board's PNG is sharp, can be transparent, and is named after the board (FEAT-14).

The features audit (2026-10-05): the PNG was 1x (board units as pixels), had
no transparent option, and every file was `whiteboard-whole.png` or
`whiteboard-selection.png`. The browser half (a 2x export measures twice the
board's size, a transparent one has no ground) is
`scratchpad/ui-sweeps/wb1005-export.js`.
"""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = SOURCE.index(f"function {name}(")
    return SOURCE[start : SOURCE.index("\n}\n", start) + 3]


def _name(title: str, scope: str, ext: str = "png", is_map: bool = False) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        f"function wbBoardTitleForExport() {{ return {json.dumps(title)}; }}\n"
        f"function wbIsMap() {{ return {json.dumps(is_map)}; }}\n"
        + _function("wbExportFileName")
        + f"\nconsole.log(JSON.stringify(wbExportFileName({json.dumps(scope)}, {json.dumps(ext)})));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def test_the_file_is_named_after_the_board() -> None:
    assert _name("Launch plan", "whole") == "Launch plan.png"
    assert _name("Launch plan", "selection") == "Launch plan (selection).png"
    assert _name("Launch plan", "visible", "svg") == "Launch plan (view).svg"


def test_a_name_a_file_system_refuses_is_cleaned() -> None:
    assert _name('Q3: plan / "draft"?', "whole") == "Q3 plan draft.png"


def test_an_unnamed_board_still_says_what_it_is() -> None:
    assert _name("", "whole", is_map=True) == "Mind map.png"
    assert _name("", "whole") == "Whiteboard.png"


def test_the_png_takes_a_scale_and_a_transparent_ground() -> None:
    png = _function("wbExportPng")
    assert "width * scale" in png and "transparent" in png
    assert "transparent ? \"\"" in _function("wbBuildExportSvg")
    dialog = _function("wbExportBoard")
    assert "WB_EXPORT_SCALES" in dialog and "Transparent background" in dialog
