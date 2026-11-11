"""Text size in a prose document is five steps, and Ctrl+wheel moves along them (OPEN W23 D28).

It was three (small, medium, large) behind a cycling menu row, so a long read on
a big screen or a half-width window had no way past "large". Ctrl+wheel over the
editor now steps one size at a time, stopping at either end (it does not wrap the
way the menu row does), and the browser's own page zoom is left alone elsewhere.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (ROOT / "frontend/js/documents.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/library-lazy.css").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _step(current: str, delta: int) -> str:
    sizes = re.search(r"^const DOC_TEXT_SIZES = .*?;$", DOCUMENTS, re.M).group(0)
    fn = re.search(r"^function docZoomStep\(.*?^\}", DOCUMENTS, re.S | re.M).group(0)
    script = f"{sizes}\n{fn}\nprocess.stdout.write(JSON.stringify(docZoomStep({json.dumps(current)}, {delta})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_there_are_five_sizes_in_order():
    sizes = re.search(r"^const DOC_TEXT_SIZES = (\[.*?\]);$", DOCUMENTS, re.M).group(1)
    assert json.loads(sizes) == ["small", "medium", "large", "xlarge", "xxlarge"]


def test_a_step_moves_one_size_and_stops_at_each_end():
    assert _step("medium", 1) == "large"
    assert _step("large", 1) == "xlarge"
    assert _step("xxlarge", 1) == "xxlarge"
    assert _step("medium", -1) == "small"
    assert _step("small", -1) == "small"


def test_each_larger_size_has_a_rule_on_a_token_for_the_editor_and_the_reader():
    for name, token in (("xlarge", "--text-h2"), ("xxlarge", "--text-h1")):
        rule = re.search(
            rf"#tab-documents\.doc-size-{name} \.doc-source-wrap [^{{]*\{{\s*font-size: var\({token}\);", CSS
        )
        assert rule, name
        assert f"#tab-documents.doc-size-{name} #doc-preview" in CSS


def test_ctrl_wheel_over_the_editor_steps_the_size_and_other_wheels_scroll():
    wire = re.search(r'\$\("tab-documents"\)\?\.addEventListener\("wheel".*?\n\}, \{ passive: false \}\);', DOCUMENTS, re.S)
    assert wire, "no Ctrl+wheel handler on the documents tab"
    body = wire.group(0)
    assert "ctrlKey" in body and "preventDefault" in body and "docIsCodeFile()" in body
