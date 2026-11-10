"""A document's cover and icon (DOCUMENTS_PLAN, gap row 8: Notion's page cover
and icon): two frontmatter keys, `icon` (an emoji, or `ph:name` for a Phosphor
icon from the one picker) and `cover` (one of eight named tints, the same
names the board's panels use). Written by the properties panel's smallest-edit
model, so a document whose frontmatter was written by hand keeps its bytes."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_doc_frontmatter import model_source

ROOT = Path(__file__).resolve().parents[1]
PROPS = (ROOT / "frontend" / "js" / "documents-props.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")

DRIVER = r"""
const look = (t) => docCoverLook(docFrontmatterParse(t));
const out = {};
out.emoji = look("---\nicon: \u{1F4D8}\ncover: blue\n---\n# A");
out.named = look("---\nicon: ph:rocket-launch\ncover: Violet\n---\n# A");
out.quoted = look('---\nicon: "ph:rocket"\n---\n# A');
out.bad = look("---\nicon: two words\ncover: #ff0000\n---\n# A");
out.list = look("---\nicon: [a, b]\ncover:\n  - blue\n---\n# A");
out.none = look("---\ntags: [x]\n---\n# A");
const base = "---\ntags: [one, two]\nstatus:    draft\n---\n\n# A\n";
const set = (t, k, v) => docTableApplyEdits(t, docCoverEdits(docFrontmatterParse(t), k, v));
const withCover = set(base, "cover", "teal");
out.added = withCover;
out.sameAgain = docCoverEdits(docFrontmatterParse(withCover), "cover", "teal").length;
out.changed = set(withCover, "cover", "pink");
out.roundTrip = set(withCover, "cover", null) === base;
const both = set(set(base, "icon", "ph:star"), "cover", "red");
out.both = look(both);
out.bothText = both;
out.clearedIcon = set(both, "icon", null);
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("doccover") / "run.js"
    script.write_text(model_source() + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_look_reads_an_emoji_a_named_icon_and_a_tint_and_nothing_else(result):
    assert result["emoji"] == {"icon": {"kind": "emoji", "value": "\U0001f4d8"}, "cover": "blue"}
    assert result["named"] == {"icon": {"kind": "icon", "value": "rocket-launch"}, "cover": "violet"}
    assert result["quoted"]["icon"] == {"kind": "icon", "value": "rocket"}
    assert result["bad"] == {"icon": None, "cover": None}
    assert result["list"] == {"icon": None, "cover": None}
    assert result["none"] == {"icon": None, "cover": None}


def test_setting_and_clearing_touch_only_their_own_line(result):
    assert result["added"] == "---\ntags: [one, two]\nstatus:    draft\ncover: teal\n---\n\n# A\n"
    assert result["sameAgain"] == 0  # a write that changes nothing never reaches the undo history
    assert result["changed"].count("cover: pink") == 1 and "teal" not in result["changed"]
    assert result["roundTrip"] is True
    assert result["both"] == {"icon": {"kind": "icon", "value": "star"}, "cover": "red"}
    assert "icon: ph:star" in result["bothText"] or 'icon: "ph:star"' in result["bothText"]
    assert "icon" not in result["clearedIcon"] and "cover: red" in result["clearedIcon"]


def test_the_panel_draws_the_cover_and_offers_icon_and_cover_in_the_one_picker():
    assert "docPropsLookRow(host, fm)" in PROPS
    assert "pickIconOrEmoji({" in PROPS and "swatchPicker({" in PROPS
    assert 'entry.key === "icon" || entry.key === "cover"' in PROPS  # the look row owns both keys
    assert "var(--swatch)" in CSS.split(".doc-cover {", 1)[1].split("}", 1)[0]
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_core.py").read_text(encoding="utf-8")
    assert "Add icon and Add cover" in topics
