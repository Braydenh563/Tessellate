"""INBOX 1696 f, the owner's lag log: "input 456ms on dashboard: pointerout on div in #settings-nav" and
"frame 216ms: Response.json.then 195ms (forced layout 89ms) [apiJson /preferences from settings-panes.js
renderPrefs, /jobs/last-runs from settings.js refreshJobRuns, /preferences from personas-pane.js renderPersonas]".

Measured at 4x CPU on a 60-note notebook (scratch probes, lag1696-1108b.md):
- the first slider hover in Settings loads value-field.js, whose scan of the page ran one
  `output[for=...]` query and one `labels` walk per slider: 64 to 72 ms in one task, which a pointer
  event moving over the nav waited behind;
- Settings, Personas asked for /preferences twice (renderPrefs and renderPersonas) and drew each new
  persona face inside the row loop, so the face's measure paid the page's pending style and layout
  (181 to 206 ms, forced layout 89 to 113 ms, in the probe);
- `refreshJobRuns` read `offsetParent` on every job line right after painting them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"

SCAN_HARNESS = r"""
const fs = require("fs"), vm = require("vm");
class HTMLInputElement {}
const queries = [];
let labelReads = 0;
const node = (tag) => ({
  tagName: tag.toUpperCase(), children: [], dataset: {}, attrs: {}, className: "", textContent: "",
  classList: { add() {}, remove() {}, toggle() {} },
  setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] ?? null; },
  append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; },
  addEventListener() {}, after(el) { this.next = el; }, select() {}, focus() {}, blur() {},
});
const sliders = [], outputs = [], labels = [];
for (let i = 0; i < 30; i += 1) {
  const s = Object.assign(Object.create(HTMLInputElement.prototype), {
    type: "range", id: `s${i}`, dataset: {}, min: "0", max: "10", step: "1", value: "3",
    parentElement: { querySelector: () => null }, hasAttribute: () => false, getAttribute: () => null, title: "",
    addEventListener() {}, after() {},
  });
  Object.defineProperty(s, "labels", { get() { labelReads += 1; return []; } });
  sliders.push(s);
  const out = node("output"); out.attrs.for = `s${i}`; out.textContent = `${i}px`; outputs.push(out);
  const label = node("label"); label.textContent = `Size ${i} ${i}px`; label.control = s; labels.push(label);
}
const document = {
  createElement: node, getElementById: () => null, activeElement: null, addEventListener() {},
  querySelectorAll: (sel) => { queries.push(sel); return /range/.test(sel) ? sliders : /^output/.test(sel) ? outputs : /^label/.test(sel) ? labels : []; },
  querySelector: (sel) => { queries.push(sel); return null; },
};
const sandbox = { document, window: { addEventListener() {} }, HTMLInputElement, CSS: { escape: (s) => s }, kebabMenu: () => node("div") };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), sandbox);
console.log(JSON.stringify({
  perSlider: queries.filter((q) => /^output\[for="/.test(q)).length,
  labelReads,
  found: outputs.filter((o) => o.next).length,
  named: outputs.filter((o) => o.next && /^Size \d+, type a value$/.test(o.next.children[0]?.children[0]?.attrs["aria-label"] || "")).length,
}));
"""


def _scan() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", SCAN_HARNESS, str(JS / "value-field.js")], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_the_value_field_scan_reads_the_readouts_and_labels_once_not_per_slider():
    probe = _scan()
    assert probe["perSlider"] == 0, probe
    assert probe["labelReads"] == 0, probe
    # Still every readout found, and every field named by its label without the readout's own text.
    assert probe["found"] == 30 and probe["named"] == 30, probe


def _function(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    match = re.search(rf"^( *)(?:async )?function {name}\(.*?^\1\}}", source, re.S | re.M)
    assert match, f"{name} is gone from {path.name}"
    return match.group(0)


def test_personas_reads_the_preferences_renderprefs_is_already_fetching():
    show = _function(JS / "settings.js", "showSettingsSection")
    assert re.search(r"const (\w+) = \[[^\]]*\"personas\"\]\.includes\(name\) && renderPrefs\(\)", show), "renderPrefs' read is kept"
    read = re.search(r"const (\w+) = \[[^\]]*\"personas\"\]\.includes\(name\) && renderPrefs\(\)", show).group(1)
    assert f"renderPersonas({read})" in show
    body = _function(JS / "personas-pane.js", "renderPersonas")
    # Its own GET only when no read was handed over (a save, an edit, the lazy stand-in).
    assert re.search(r"\(await \w+\) \?\?|await \(\w+ \|\|", body) or "|| apiJson(\"/preferences\")" in body, body[:600]


def test_persona_faces_are_drawn_after_the_rows_have_painted():
    body = _function(JS / "personas-pane.js", "renderPersonas")
    assert "afterFrames(" in body, "the faces wait for the rows' frame"
    loop = body[body.index("for (const persona of rows)") : body.rindex("afterFrames(")]
    # Not inside the row loop: each new face is measured, and a measure after a row write paid the page's layout.
    assert "fillPersonaMark(mark" not in loop
    assert re.search(r"afterFrames\(\(\) => setTimeout\(", body), "the faces wait for the rows' frame"


def test_job_lines_read_layout_only_for_a_running_job():
    body = _function(JS / "settings.js", "refreshJobRuns")
    line = next(row for row in body.splitlines() if "const running" in row)
    assert line.index("jobRunning") < line.index("offsetParent"), line


def test_a_scroll_over_the_page_reads_no_layout():
    # A Settings section switch scrolled its pane, and the edge timer's scrollTop read paid the pane's pending
    # style (274 ms at 4x CPU in the trace): a menu, a dialog or Settings is skipped before any timer is set.
    body = _function(JS / "shell-reminders.js", "onScrollEdge")
    guard = body.index("#settings-modal")
    assert guard < body.index("requestAnimationFrame("), body
    assert body.count("#settings-modal") == 1, "one guard, before the timer"
