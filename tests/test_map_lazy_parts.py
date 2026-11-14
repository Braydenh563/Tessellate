"""A topic's hidden parts are made on first use (L-mindmap-13).

A plain topic was 25 elements, 17 of them hidden, and the first style
recalculation of a new topic walked all of them. `wbMapCache.part` makes a
part in its old slot the first time the paint has something for it. The proof
is behavioural: the accessor's source is run in a real page (playwright, with
the handlers stubbed) and the order of the children is read back.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
PW = "/opt/node22/lib/node_modules/playwright"
needs_pw = pytest.mark.skipif(
    not shutil.which("node") or not Path(PW).exists(), reason="needs node and playwright"
)

#: The cache object and its accessor, cut out of the shipped file.
SNIPPET = MAP[MAP.index("const wbMapCache = {") : MAP.index("//: **The level of every topic**")]
BUILD = MAP[MAP.index("function wbBuildMapNode(") : MAP.index("//: **The ink a core node's label")]

SCRIPT = r"""
const { chromium } = require(process.argv[2]);
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent('<div id="o" data-id="7" class="wb-object wb-map-node"></div>');
  const out = await page.evaluate((src) => {
    for (const n of ["wbMapToggleTaskDone", "wbMapOpenNote", "wbMapOpenLink", "wbMapEditCallout",
      "wbMapStampSet", "wbMapEditLabels", "wbMapToggleCollapse", "wbMapStartResizeDrag"]) window[n] = () => {};
    window.wbMapLiveDatum = (d) => d;
    const cache = new Function(src + "; return wbMapCache;")();
    const node = document.getElementById("o");
    node.innerHTML = '<div class="wb-map-node-body"><div class="wb-map-text"></div></div>'
      + '<div class="wb-map-actions"><button class="wb-map-add"></button></div>';
    const last = (c) => c.className.split(" ").pop();
    const kids = () => [...node.children].map(last).concat(["|"], [...node.firstChild.children].map(last));
    const res = { plain: kids(), look: cache.part(node, "callout", false) };
    res.noCreate = kids();
    for (const name of ["link", "note", "task", "tags", "callout", "count", "collapse", "grip", "icon",
      "markers", "picture", "number", "progress"]) {
      const el = cache.part(node, name);
      res[name] = [last(el), cache.part(node, name) === el];
    }
    res.full = kids();
    return res;
  }, process.argv[3]);
  console.log(JSON.stringify(out));
  await browser.close();
})();
"""


@needs_pw
def test_parts_are_made_on_first_use_in_their_old_slot(tmp_path):
    script = tmp_path / "run.js"
    script.write_text(SCRIPT, encoding="utf-8")
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")}
    done = subprocess.run(
        ["node", str(script), PW, SNIPPET], capture_output=True, text=True, timeout=90, env=env, check=True
    )
    got = json.loads(done.stdout.strip().splitlines()[-1])
    assert got["plain"] == ["wb-map-node-body", "wb-map-actions", "|", "wb-map-text"]
    assert got["look"] is None and got["noCreate"] == got["plain"], "a lookup never creates"
    assert all(got[n][1] for n in ("link", "note", "task", "tags", "callout", "count", "collapse", "grip")), "once"
    assert got["full"] == [
        "wb-map-node-body", "wb-map-callout", "wb-map-tags", "wb-map-count", "wb-map-collapse",
        "wb-map-resize-grip", "wb-map-actions", "|",
        "wb-map-task", "wb-map-markers", "wb-map-node-icon", "wb-map-node-picture", "wb-map-number",
        "wb-map-text", "wb-map-progress", "wb-map-note", "wb-map-link",
    ]


def test_a_new_topic_builds_only_what_it_shows():
    for hidden in ("callout", "tags", "task", "markers", "icon", "picture", "number", "progress", "note", "link",
                   "count", "collapse", "resize-grip"):
        assert f"wb-map-{hidden}" not in BUILD and f"wb-map-node-{hidden}" not in BUILD, hidden
    assert "wb-map-text" in BUILD and "wb-map-actions" in BUILD


def test_painters_ask_the_accessor_and_hiding_never_creates():
    for name in ("task", "markers", "icon", "picture", "number", "progress", "note", "link", "callout", "tags",
                 "count", "collapse"):
        # The painter moved to whiteboard-map-notes.js on the whiteboard branch (L286 carve); same assert.
        assert f'wbMapCache.part(node, "{name}", ' in MAP + (ROOT / "frontend" / "js" / "whiteboard-map-notes.js").read_text(encoding="utf-8"), name
    # The selection paint moved to whiteboard-bar.js on the whiteboard branch (L286 carve); same assert.
    wb = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8") + (ROOT / "frontend" / "js" / "whiteboard-bar.js").read_text(encoding="utf-8")
    assert 'wbMapCache.part(el, "grip")' in wb
