"""S93 (audit 1028, shell): `flashEntry` run for real, with a 100-note fixture,
on the path where the card is not in the DOM. The older test only read the
source for the strings; this one runs the function in node with stubs.
Skipped where node is not installed."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "frontend" / "js" / "capture-ask.js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const [source, target, drawn] = [process.argv[1], Number(process.argv[2]), process.argv[3]];
const log = [];
const card = {
  classList: { remove: () => log.push("flash off"), add: (name) => log.push(`class ${name}`) },
  getBoundingClientRect: () => ({ top: 0 }), scrollIntoView: () => log.push("scrolled"),
  focus: () => log.push("focused"), offsetWidth: 1,
  querySelector: () => ({ textContent: " the note's words " }),
};
const ctx = {
  allEntries: Array.from({ length: 100 }, (_, i) => ({ id: i + 1, content: `note ${i + 1}` })),
  lastOpenedEntryId: null, activeCategory: "x", draftsOnly: true, favouritesOnly: true, noteSearch: "q",
  notesCurrentPage: 1, expandedRows: new Set(), noteEngine: { jumpId: null },
  switchTab: () => log.push("switchTab"), showNotesSection: () => {}, noteLabel: () => "label",
  recordTabVisit: (...args) => log.push(["visit", ...args]), $: () => null,
  resolveNotePage: () => 0, renderSidebar: () => {},
  renderEntries: async () => (drawn === "false" ? false : true),
  // The list is windowed: only the rows it drew are in the page. Ids 1 to 50 are; the rest are not.
  document: { querySelector: (selector) => (Number(/data-id="(\d+)"/.exec(selector)[1]) <= 50 ? card : null) },
  requestAnimationFrame: (fn) => fn(), reducedMotionWanted: () => false,
  window: { innerHeight: 800 }, announce: (text) => log.push(["announce", text]),
  toast: (text) => log.push(["toast", text]), nameMarkBuddyNoteOpened: (id) => log.push(["buddy", id]),
  setTimeout: () => 0, clearTimeout: () => {}, Math, Number, Set, Boolean,
};
vm.createContext(ctx);
vm.runInContext(source, ctx);
vm.runInContext(`flashEntry(${target}).then(() => __done())`, Object.assign(ctx, {
  __done: () => process.stdout.write(JSON.stringify({ log, jumpId: ctx.noteEngine.jumpId, last: ctx.lastOpenedEntryId, filters: [ctx.activeCategory, ctx.draftsOnly, ctx.favouritesOnly, ctx.noteSearch] })),
}));
"""


def _flash_source() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("async function flashEntry(id")
    return text[start : text.index("\n}\n", start) + 3]


def _run(target: int, drawn: str = "true") -> dict:
    done = subprocess.run(
        ["node", "-e", HARNESS, _flash_source(), str(target), drawn],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(done.stdout)


@needs_node
def test_a_note_that_is_not_in_the_page_says_so_and_returns_the_address():
    out = _run(77)  # in the 100 notes, but not among the rows drawn
    assert ["toast", "No such note."] in out["log"]
    assert ["announce", ""] in out["log"]
    assert ["visit", "notes", "browse", "", {"refine": True}] in out["log"]
    # nothing was flashed or announced as shown, and the paint-through target is released
    assert not any(entry == "class flash" for entry in out["log"])
    assert not any(isinstance(entry, list) and entry[0] == "buddy" for entry in out["log"])
    assert out["jumpId"] is None and out["last"] == 77
    # the filters were cleared so the target could be found at all
    assert out["filters"] == [None, False, False, ""]


@needs_node
def test_a_note_that_is_in_the_page_is_flashed_and_announced():
    out = _run(12)
    assert "class flash" in out["log"] and "focused" in out["log"]
    assert ["announce", "Showing note: the note's words"] in out["log"]
    assert ["buddy", 12] in out["log"]
    assert not any(isinstance(entry, list) and entry[0] == "toast" for entry in out["log"])


@needs_node
def test_a_draw_that_gave_way_says_nothing():
    out = _run(77, drawn="false")
    assert not any(isinstance(entry, list) and entry[0] in ("toast", "announce") for entry in out["log"])
