"""A map written as a document (audit brief M5, the first half).

`wbMapTreeMarkdown` (between the MAP-DOC markers in whiteboard-map.js) is pure
and runs here in node; the round trip through the app is driven by
`scratchpad/ui-sweeps/mmdoc1005-maptodoc.js`.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import shutil
import subprocess

import pytest

SRC = frontend_text("whiteboard-map.js")


def _run(roots, title="The map"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start, end = SRC.index("// MAP-DOC-BEGIN"), SRC.index("// MAP-DOC-END")
    script = SRC[start:end] + f"\nprocess.stdout.write(JSON.stringify(wbMapTreeMarkdown({json.dumps(roots)}, {json.dumps(title)})));"
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _n(text, *children, note=None):
    return {"text": text, "children": list(children), "style": {"note": note} if note else {}}


def test_branches_are_headings_and_the_rest_lists():
    out = _run([_n("Thesis", _n("Method", _n("Interviews", _n("Ten people")), note="How it was done."), _n("Results"))])
    assert out["title"] == "Thesis"
    assert out["body"] == "## Method\n\nHow it was done.\n\n### Interviews\n\n- Ten people\n\n## Results"


def test_a_note_under_a_list_item_is_indented_under_it():
    out = _run([_n("Root", _n("A", _n("A1", _n("A1a", note="Detail."))))])
    assert out["body"] == "## A\n\n### A1\n\n- A1a\n  Detail."


def test_several_trunks_keep_the_maps_name():
    out = _run([_n("One"), _n("Two")], title="Two trunks")
    assert out["title"] == "Two trunks"
    assert out["body"] == "## One\n\n## Two"
