"""One resolved Motion value, and the raw query only where it is resolved (INBOX 1506).

The owner's browser reports `prefers-reduced-motion` and the owner wants the
animations, so the Motion setting is its own choice: follow the system (the
default), always on, off. `MOTION.apply` (theme-boot.js) resolves the choice,
Performance mode and the system's request into `data-motion` on the root,
"reduced" or "full"; every stylesheet and script reads that, never the query.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BOOT = FRONTEND / "js" / "theme-boot.js"
RAW = "prefers-reduced-motion"

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _strip_css(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_the_raw_query_is_written_only_by_the_boot() -> None:
    """No `@media (prefers-reduced-motion ...)` block, no `media=` attribute
    and no `matchMedia` of it outside theme-boot.js: a block of its own is the
    system's request answered a second way, the thing that left an owner who
    chose "Always on" with half the page still."""
    found: list[str] = []
    for css in sorted((FRONTEND / "css").glob("*.css")):
        for m in re.finditer(r"@media[^{;]*" + RAW, _strip_css(css.read_text(encoding="utf-8"))):
            found.append(f"{css.name}: {m.group(0)[:60]}")
    for js in sorted((FRONTEND / "js").glob("*.js")):
        if js == BOOT:
            continue
        text = js.read_text(encoding="utf-8")
        if re.search(r"matchMedia[^;\n]{0,40}" + RAW, text) or f'"({RAW}' in text:
            found.append(f"{js.name}: a matchMedia read")
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    if re.search(r'media="[^"]*' + RAW, index):
        found.append("index.html: a media attribute")
    assert not found, "the one resolved value is `data-motion` (reducedMotionWanted in script): " + "; ".join(found)


def test_the_boot_reads_the_query_once_and_scripts_ask_one_helper() -> None:
    boot = BOOT.read_text(encoding="utf-8")
    assert len(re.findall(r'matchMedia\("\(' + RAW, boot)) == 1
    assert "function reducedMotionWanted()" in boot
    for js in sorted((FRONTEND / "js").glob("*.js")):
        if js != BOOT:
            assert "function reducedMotionWanted()" not in js.read_text(encoding="utf-8"), js.name


def test_the_motion_setting_is_three_choices_in_one_well() -> None:
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    well = re.search(r'<div class="seg seg-compact" id="motion-seg".*?</div>', index, re.S)
    assert well, "Motion is a .seg"
    assert re.findall(r'data-motion-choice="(\w+)">([^<]+)<', well.group(0)) == [
        ("follow", "Follow the system"),
        ("on", "Always on"),
        ("off", "Off"),
    ]
    assert "reduce-motion-toggle" not in index


def _run(choice: str | None, os_reduce: bool, perf: bool, ui_motion: str = "on") -> dict:
    script = r"""
const vm = require("vm"), fs = require("fs");
const [choice, osReduce, perf, uiMotion] = JSON.parse(process.argv[1]);
const sheet = { media: "not all" };
const store = { perf: perf ? "on" : "off", "ui-motion": uiMotion };
if (choice !== null) store.motion = choice;
const listeners = [];
const query = { matches: osReduce, addEventListener: (t, f) => listeners.push(f) };
const ctx = vm.createContext({
  window: { matchMedia: (q) => (q.includes("prefers-reduced-motion") ? query : { matches: false }) },
  document: {
    documentElement: { dataset: {}, style: { setProperty() {} } },
    getElementById: (id) => (id === "motion-still-sheet" ? sheet : null),
    dispatchEvent() {},
  },
  localStorage: { getItem: (k) => (k in store ? store[k] : null) },
  navigator: {},
  Event: class {},
});
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const read = () => vm.runInContext("({ motion: document.documentElement.dataset.motion, cause: MOTION.cause, wanted: reducedMotionWanted() })", ctx);
const first = read();
const sheetFirst = sheet.media;
query.matches = !osReduce;
listeners.forEach((f) => f());
process.stdout.write(JSON.stringify({ first, sheet: sheetFirst, flipped: read() }));
"""
    run = subprocess.run(
        ["node", "-e", script, json.dumps([choice, os_reduce, perf, ui_motion]), str(BOOT)],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
@pytest.mark.parametrize(
    "choice, os_reduce, perf, motion, cause",
    [
        (None, False, False, "full", ""),
        (None, True, False, "reduced", "os"),
        ("follow", True, False, "reduced", "os"),
        ("follow", False, True, "reduced", "perf"),
        ("on", True, False, "full", ""),
        ("on", True, True, "full", ""),
        ("off", False, False, "reduced", "off"),
        ("off", True, False, "reduced", "off"),
        ("auto", True, False, "reduced", "os"),
        ("auto", False, False, "full", ""),
        ("reduced", False, False, "reduced", "off"),
    ],
)
def test_the_choice_the_system_and_performance_mode_resolve_to_one_value(choice, os_reduce, perf, motion, cause) -> None:
    got = _run(choice, os_reduce, perf)["first"]
    assert got == {"motion": motion, "cause": cause, "wanted": motion == "reduced"}


@needs_node
def test_the_resolved_value_follows_the_system_while_the_page_is_open() -> None:
    """The query's change event re-resolves: follow flips with it, the other two do not."""
    follow = _run("follow", False, False)
    assert follow["first"]["motion"] == "full" and follow["flipped"]["motion"] == "reduced"
    for choice, motion in (("on", "full"), ("off", "reduced")):
        got = _run(choice, False, False)
        assert got["first"]["motion"] == got["flipped"]["motion"] == motion


@needs_node
def test_the_still_sheet_matches_only_while_a_switch_is_on() -> None:
    assert _run("follow", False, False)["sheet"] == "not all"
    assert _run("follow", True, False)["sheet"] == "all"
    assert _run("on", True, False)["sheet"] == "not all"
    assert _run("on", False, False, ui_motion="off")["sheet"] == "all"
