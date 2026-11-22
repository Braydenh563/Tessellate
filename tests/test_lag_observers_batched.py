"""Two ResizeObserver callbacks that paid for other callbacks' writes (lag trace, 2026-11-11).

A read of a size or a style inside an observer callback is free on a clean page and a full style and
layout pass on one an earlier callback has written. Measured at 4x CPU with 34k nodes in the Library
Images grid:

* `docGutterObserver` called `syncDocGutterMetrics` once per resized box, so the second numbered box's
  reads came after the first box's writes: 141 ms over a 20-frame drag of two boxes, now 43 ms (one
  call per delivery, 19 calls instead of 38).
* `keepLibraryScroll`'s `restore` read `clientHeight` of all eight sections on every delivery: with an
  earlier observer writing the grid, 13 deliveries cost 1920 ms (150 ms each), now 1.6 ms. Whether a
  section is showing comes from the entry, and `scrollHeight` is read only for a section that is
  showing again with an offset still to put back.

The functions are cut out of the real source and run in node against a recording page, so a read
after a write is counted, not guessed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
DOCS = documents_text()
LIB = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _braced(src: str, start: int) -> str:
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(start)


def _node(script: str) -> dict:
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    return json.loads(run.stdout)


def test_the_gutter_observer_makes_one_call_for_the_whole_delivery() -> None:
    start = DOCS.index("docGutterObserver = new ResizeObserver(")
    body = _braced(DOCS, start)
    assert "syncDocGutterMetrics(boxes)" in body
    assert "syncDocGutterMetrics(entry.target)" not in body, (
        "a call per entry puts one box's reads after another's writes"
    )
    assert 'entry.target.id === "doc-counts"' in body, (
        "the status bar's counts still ride this observer"
    )


@needs_node
def test_sync_reads_every_box_before_it_writes_any() -> None:
    sync = _braced(DOCS, DOCS.index("function syncDocGutterMetrics("))
    script = (
        r"""
const log = [];
const DOC_GUTTER_PROPS = ["lineHeight", "paddingTop", "paddingBottom"];
const DOC_GUTTER_BASELINE = 0.43;
const mk = (name, h) => {
  const style = new Proxy({}, { set(t, k, v) { log.push("write:" + name + ":" + k); t[k] = v; return true; } });
  const gutter = { name, style, classList: { contains: (c) => c === "hidden" && name === "off" } };
  const box = {
    name,
    get offsetHeight() { log.push("read:" + name + ":height"); return h; },
  };
  return { gutter, box };
};
const pairs = [mk("a", 100), mk("b", 220), mk("off", 50)];
const cs = new Map();
globalThis.getComputedStyle = (el) => {
  log.push("read:" + el.name + ":style");
  return el.style ? { fontSize: "11px" } : { lineHeight: "24px", paddingTop: "8px", paddingBottom: "8px", fontSize: "16px" };
};
const docGutters = () => pairs;
"""
        + sync
        + r"""
syncDocGutterMetrics(pairs.slice(0, 2).map((p) => p.box));
const firstWrite = log.findIndex((e) => e.startsWith("write:"));
const lastRead = log.map((e) => e.startsWith("read:")).lastIndexOf(true);
const only = (e) => e.split(":")[1];
const out = { firstWrite, lastRead, boxes: [...new Set(log.map(only))], heights: pairs.map((p) => p.gutter.style.height || null) };
log.length = 0;
syncDocGutterMetrics(pairs[1].box);
out.single = [...new Set(log.map(only))];
log.length = 0;
syncDocGutterMetrics();
out.all = [...new Set(log.map(only))];
out.paddingTop = pairs[0].gutter.style.paddingTop;
out.paddingBottom = pairs[0].gutter.style.paddingBottom;
process.stdout.write(JSON.stringify(out));
"""
    )
    out = _node(script)
    assert out["lastRead"] < out["firstWrite"], (
        "every read of the delivery comes before its first write"
    )
    assert out["boxes"] == ["a", "b"], "the boxes handed over, and no others"
    assert out["heights"] == ["100px", "220px", None]
    assert out["single"] == ["b"], "one box still works"
    assert out["all"] == ["a", "b"], "no argument is every shown gutter (a hidden one is skipped)"
    # 16px text, 11px figures: the baseline drop is 0.43 * 5 = 2.15px, written once to its final value.
    assert out["paddingTop"] == "calc(8px + 2.15px)"
    assert out["paddingBottom"] == "max(0px, calc(8px - 2.15px))"


def test_each_gutter_padding_is_written_once_to_its_final_value() -> None:
    sync = _braced(DOCS, DOCS.index("function syncDocGutterMetrics("))
    assert sync.count("gutter.style.paddingTop =") == 1
    assert sync.count("gutter.style.paddingBottom =") == 1


def _restore() -> str:
    keep = _braced(LIB, LIB.index("function keepLibraryScroll("))
    start = keep.index("const restore = (entries) => {")
    return _braced(keep, start) + ";"


def test_restore_takes_the_entries_and_reads_no_section_it_was_not_told_about() -> None:
    restore = _restore()
    code = "\n".join(line for line in restore.splitlines() if not line.strip().startswith("//:"))
    assert "for (const el of sections)" not in code, "a pass over every section reads every section"
    assert code.count("clientHeight") == 1 and code.count("scrollHeight") == 1, (
        "only the pending, showing section is measured"
    )


@needs_node
def test_restore_measures_only_a_section_that_is_showing_again_with_an_offset_to_put_back() -> None:
    script = (
        r"""
const reads = [];
const mk = (id, h, content) => {
  const el = {
    id, parentElement: null, _top: 0,
    get clientHeight() { reads.push(id + ":clientHeight"); return h; },
    get scrollHeight() { reads.push(id + ":scrollHeight"); return content; },
    set scrollTop(v) { this._top = v; }, get scrollTop() { return this._top; },
  };
  return el;
};
const docs = mk("docs", 600, 2000), skills = mk("skills", 600, 2000), images = mk("images", 600, 90000);
const childOf = (el) => ({ id: "child-of-" + el.id, parentElement: el });
const sections = [docs, skills, images];
const saved = new Map();
const pending = new Set();
"""
        + _restore()
        + r"""
const own = (el, h) => ({ target: el, borderBoxSize: [{ blockSize: h }], contentRect: { height: h } });
const kid = (el, h) => ({ target: childOf(el), borderBoxSize: [{ blockSize: h }], contentRect: { height: h } });
const out = {};

// Steady state: nothing saved, a resize of a showing section and of a child. Not one read.
restore([own(images, 700), kid(images, 80000), own(docs, 700)]);
out.steady = reads.length;

// A person scrolled the Documents section to 900, then it was hidden: remembered, still no read.
saved.set("docs", 900);
restore([own(docs, 0)]);
out.hidden = { reads: reads.length, pending: [...pending] };

// Another section resizing does not make the hidden one measure.
restore([own(images, 710)]);
out.otherSection = reads.length;

// A child delivered with nothing (an empty child) says nothing about the section.
restore([kid(docs, 0)]);
out.emptyChild = { reads: reads.length, pending: [...pending] };

// It shows again: measured, and the offset goes back.
restore([own(docs, 700)]);
out.shown = { reads: reads.slice(), top: docs.scrollTop, pending: [...pending] };

// Showing again but too short to hold the offset: kept pending, found again when a child grows.
saved.set("skills", 1900);
restore([own(skills, 0)]);
skills.scrollTop = 0;
const shortContent = mk("skills", 600, 1000);
sections[1] = shortContent; saved.set("skills", 1900);
restore([own(shortContent, 0)]);
reads.length = 0;
restore([own(shortContent, 700)]);
out.tooShort = { top: shortContent.scrollTop, pending: [...pending] };
process.stdout.write(JSON.stringify(out));
"""
    )
    out = _node(script)
    assert out["steady"] == 0, "a resize with nothing to restore costs no layout read"
    assert out["hidden"] == {"reads": 0, "pending": ["docs"]}, (
        "hiding is read from the entry, not from clientHeight"
    )
    assert out["otherSection"] == 0
    assert out["emptyChild"] == {"reads": 0, "pending": ["docs"]}
    assert out["shown"]["top"] == 900 and out["shown"]["pending"] == []
    assert out["shown"]["reads"] == ["docs:scrollHeight", "docs:clientHeight"]
    assert out["tooShort"]["top"] == 0 and out["tooShort"]["pending"] == ["skills"], (
        "kept until the content is tall enough"
    )
