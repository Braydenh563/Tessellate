"""Line shape (straight, curved, stepped) in the diagram's ... menu (R13, OPEN W18).

Measured in the vendored Mermaid 12.2 (a 4-box chart, the first two edge paths): the default ELK layout ignores
`flowchart.curve` (identical paths for `linear` and `step` and none), while with `layout: dagre` beside it `linear` draws
`M..L..L..`, `basis` draws cubic `C` segments and `step` draws right-angle runs. So a line shape is front matter that names
the engine too, and the spacing rows (test_diagram_spacing.py) share that engine line: Normal spacing keeps it while a
curve is set.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EMBED = (ROOT / "frontend" / "js" / "diagram-embed.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

PLAIN = "flowchart TD\n  A --> B\n"
STEPPED = "---\nconfig:\n  layout: dagre\n  flowchart:\n    curve: step\n---\n" + PLAIN


def _run(call: str):
    start = EMBED.index("const SPACINGS = ")
    end = EMBED.index("//: end withCurve")
    program = (
        "const front=(text)=>{const m=/^---\\n[\\s\\S]*?\\n---\\n/.exec(text);return {front:m?m[0].replace(/\\n$/,'').split('\\n'):[],rest:m?text.slice(m[0].length):text};};"
        "const diagramModel={front};" + EMBED[start:end] + f"process.stdout.write(JSON.stringify({call}));"
    )
    return json.loads(subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True).stdout)


def _set(source: str, shape: str):
    return _run(f"withCurve({json.dumps(source)},{json.dumps(shape)})")


@needs_node
def test_a_shape_is_front_matter_with_the_engine_and_usual_takes_it_out_again():
    assert _set(PLAIN, "stepped") == STEPPED
    assert _set(PLAIN, "straight") == STEPPED.replace("step", "linear")
    assert _set(PLAIN, "curved") == STEPPED.replace("step", "basis")
    assert _set(STEPPED, "usual") == PLAIN
    assert _set(_set(PLAIN, "straight"), "curved") == _set(PLAIN, "curved")  # one step between shapes


@needs_node
def test_the_shape_is_read_back_from_the_text():
    assert _run(f"curveOf({json.dumps(STEPPED)})") == "stepped"
    assert _run(f"curveOf({json.dumps(STEPPED.replace('step', 'basis'))})") == "curved"
    assert _run(f"curveOf({json.dumps(STEPPED.replace('step', 'linear'))})") == "straight"
    assert _run(f"curveOf({json.dumps(PLAIN)})") == "usual"
    assert _run(f"curveOf({json.dumps(STEPPED.replace('step', 'cardinal'))})") == "usual"  # a name typed by hand is not one of the shapes


@needs_node
def test_spacing_stays_and_the_engine_stays_while_either_is_set():
    spaced = _run(f"withSpacing({json.dumps(PLAIN)},'roomy')")
    both = _set(spaced, "stepped")
    assert both == (
        "---\nconfig:\n  layout: dagre\n  flowchart:\n    curve: step\n    nodeSpacing: 100\n    rankSpacing: 100\n---\n" + PLAIN
    )
    assert _set(both, "usual") == spaced  # the spacing still needs the engine
    # Normal spacing on a stepped chart keeps the line shape drawing (the menu re-applies the shape).
    assert _set(_run(f"withSpacing({json.dumps(both)},'normal')"), "stepped") == STEPPED


@needs_node
def test_a_flow_mapping_config_is_refused_and_other_front_matter_stays():
    assert _set("---\nconfig: {theme: dark}\n---\n" + PLAIN, "stepped") is None
    titled = "---\ntitle: Plan\nconfig:\n  look: handDrawn\n---\n" + PLAIN
    out = _set(titled, "curved")
    assert out == "---\ntitle: Plan\nconfig:\n  layout: dagre\n  flowchart:\n    curve: basis\n  look: handDrawn\n---\n" + PLAIN
    assert _set(out, "usual") == titled


def test_the_menu_offers_the_shapes_that_are_not_on_and_spacing_re_applies_the_shape():
    assert "...curveRows()," in EMBED and "const now = curveOf(history[at]);" in EMBED
    for words in ("Straight lines", "Curved lines", "Stepped lines", "Usual lines"):
        assert words in EMBED
    assert "ignores `flowchart.curve`" in EMBED
