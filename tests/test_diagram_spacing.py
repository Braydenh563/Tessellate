"""Node and rank spacing in the diagram's ... menu (DD-13, owner 2026-11-09).

The finding (diagbuild-1107): a `config: flowchart: nodeSpacing` front matter did not change the drawn size. Cause, measured
in the vendored Mermaid 12.2 (a 4-box chart, front matter lines in, viewBox out): the default layout is ELK, which has no
spacing setting; `nodeSpacing` and `rankSpacing` are dagre's. 552 x 219 whatever the spacing said; with `layout: dagre`
beside them the drawing was 512 x 179 at 20, 572 x 239 at 50 and 672 x 339 at 100. So a level is front matter that names
the engine too. The pure `withSpacing` runs in node; the drawn sizes are the browser sweep's (remaining file).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import shutil

ROOT = Path(__file__).resolve().parent.parent
EMBED = (ROOT / "frontend" / "js" / "diagram-embed.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

PLAIN = "flowchart TD\n  A --> B\n"
ROOMY = "---\nconfig:\n  layout: dagre\n  flowchart:\n    nodeSpacing: 100\n    rankSpacing: 100\n---\n" + PLAIN


def _run(call: str):
    start = EMBED.index("const SPACINGS = ")
    end = EMBED.index("//: end withSpacing")
    program = (
        "const front=(text)=>{const m=/^---\\n[\\s\\S]*?\\n---\\n/.exec(text);return {front:m?m[0].replace(/\\n$/,'').split('\\n'):[],rest:m?text.slice(m[0].length):text};};"
        "const diagramModel={front};"
        + EMBED[start:end]
        + f"process.stdout.write(JSON.stringify({call}));"
    )
    return json.loads(subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True).stdout)


def _set(source: str, level: str):
    return _run(f"withSpacing({json.dumps(source)},{json.dumps(level)})")


@needs_node
def test_a_level_is_front_matter_with_the_engine_and_normal_takes_it_out_again():
    assert _set(PLAIN, "roomy") == ROOMY
    assert _set(PLAIN, "compact") == ROOMY.replace("100", "20")
    assert _set(ROOMY, "normal") == PLAIN
    assert _set(_set(PLAIN, "compact"), "roomy") == ROOMY  # one step between levels, no lines left over
    assert _set(ROOMY, "roomy") == ROOMY


@needs_node
def test_the_level_is_read_back_from_the_text():
    assert _run(f"spacingOf({json.dumps(ROOMY)})") == "roomy"
    assert _run(f"spacingOf({json.dumps(ROOMY.replace('100', '20'))})") == "compact"
    assert _run(f"spacingOf({json.dumps(PLAIN)})") == "normal"
    assert _run(f"spacingOf({json.dumps(ROOMY.replace('100', '37'))})") == "normal"  # a gap typed by hand is not one of the levels


@needs_node
def test_other_front_matter_and_the_look_stay_and_a_flow_mapping_config_is_refused():
    titled = "---\ntitle: Plan\nconfig:\n  look: handDrawn\n  flowchart:\n    curve: basis\n---\n" + PLAIN
    roomy = _set(titled, "roomy")
    assert roomy == (
        "---\ntitle: Plan\nconfig:\n  layout: dagre\n  look: handDrawn\n  flowchart:\n    nodeSpacing: 100\n    rankSpacing: 100\n    curve: basis\n---\n" + PLAIN
    )
    assert _set(roomy, "normal") == titled
    assert _set("---\nconfig: {theme: dark}\n---\n" + PLAIN, "roomy") is None


def test_the_menu_offers_the_two_levels_that_are_not_on_and_says_why_it_is_dagre():
    assert "...spacingRows()," in EMBED and "const now = spacingOf(history[at]);" in EMBED
    for words in ("Compact spacing", "Roomy spacing", "Normal spacing"):
        assert words in EMBED
    assert "has no spacing setting" in EMBED
