"""A picture's width and alignment written back into its markdown
(DOCUMENTS_PLAN decision 8, the audit's D5): `imageAltWith`, in the pure
`IMAGE-LAYOUT` region of image-layout.js, run in node. The grip and the align menu
in Live call it; `scratchpad/ui-sweeps/mmd2-1005-imagegrip.js` drives them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.test_doc_columns import blocks_source


CASES = [
    # (alt, change, wanted)
    ["A river", {"width": 300}, "A river|300"],
    ["A river|400|center", {"width": 250}, "A river|250|center"],
    ["A river|400|center", {"align": "right"}, "A river|400|right"],
    ["A river|400|center", {"align": None}, "A river|400"],
    ["A river|400|center", {"width": None}, "A river|center"],
    ["Photo|300x200|left|taken at dawn", {"width": 320}, "Photo|320|left|taken at dawn"],
    ["", {"width": 120}, "|120"],
    ["Plain", {"align": "center"}, "Plain|center"],
]


def test_an_images_options_are_rewritten_in_place():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    body = blocks_source() + "\nconst cases = " + json.dumps(CASES) + ";\n" + (
        "console.log(JSON.stringify(cases.map(([alt, change]) => imageAltWith(alt, change))));"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(body)
    try:
        out = subprocess.run([node, handle.name], capture_output=True, text=True, timeout=30, check=True)
    finally:
        Path(handle.name).unlink(missing_ok=True)
    got = json.loads(out.stdout)
    assert got == [want for _, _, want in CASES]
