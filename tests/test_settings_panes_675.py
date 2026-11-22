"""L675 and L676: each Settings pane is a surface of its own, and a closed window parks them.

The window's body was one surface: the first open (or the first `$` of any of its
784 ids) put all 21 panes in the page, 5,000 to 7,000 elements, and the ~240
listeners of settings-controls.js each asked `$` for their control, so loading
that file built all of it. Now each `<section class="settings-section">` holds
its own `<template data-surface="settings-<pane>">`, nested under the window's
surface (`data-nests`); a listener waits for its pane (`SURFACES.wire`); a
visit builds the one pane; a search builds them all (their text is what it
reads). Closing the window parks every built pane: its nodes move into a
fragment with their listeners and what was typed in them, and the next visit
moves the same nodes back. The numbers are in CHANGELOG.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
BODY_JS = (JS / "settings-body.js").read_text(encoding="utf-8")
CONTROLS = (JS / "settings-controls.js").read_text(encoding="utf-8")
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _sections() -> list[str]:
    return re.findall(r'<section class="settings-section[^"]*"[^>]*\bid="(settings-[\w-]+)"', INDEX)


def test_every_pane_holds_its_own_template_named_after_it():
    sections = _sections()
    assert len(sections) == 21, sections
    for name in sections:
        start = INDEX.index(f'id="{name}"')
        head = INDEX[start : INDEX.index("\n", INDEX.index("\n", start) + 1)]
        assert f'<template data-surface="{name}">' in head, f"{name} does not open with its own template"


def test_the_window_names_every_pane_as_nested_and_the_code_knows_the_same_list():
    nests = re.search(r'data-surface="settings"\s+data-nests="([^"]+)"', INDEX)
    assert nests, "the window's surface no longer pre-registers its panes"
    assert nests.group(1).split() == _sections()
    listed = re.search(r"const SETTINGS_SECTIONS = \[([^\]]+)\]", SETTINGS)
    assert listed, "SETTINGS_SECTIONS moved"
    #: The nav's order, not the page's: the same panes either way.
    assert sorted(f"settings-{n}" for n in re.findall(r'"([\w-]+)"', listed.group(1))) == sorted(_sections())


def test_no_listener_in_settings_controls_asks_for_its_control_at_load():
    # Each `$("id").addEventListener` at the file's top level built the pane holding it,
    # and the file's ~240 of them built all 21 when it loaded with the first open.
    asks = re.findall(r'^  \$\(\s*"[\w-]+"\s*\)\??\.addEventListener\(', CONTROLS, re.M)
    assert not asks, f"{len(asks)} listeners build their pane at load; use wire(id): {asks[:3]}"
    assert len(re.findall(r'^  wire\("[\w-]+"\)\.addEventListener\(', CONTROLS, re.M)) > 200


def test_a_visit_builds_its_pane_and_a_search_builds_every_pane():
    show = SETTINGS[SETTINGS.index("function showSettingsSection(") :]
    assert "surfaceBuild(`settings-${name}`)" in show[:400], "a visit no longer builds its own pane first"
    search = SETTINGS[SETTINGS.index("function filterSettings(") :]
    search = search[: search.index("\n}\n")]
    assert "for (const name of SETTINGS_SECTIONS) surfaceBuild(`settings-${name}`)" in search


def test_closing_parks_the_panes_and_the_close_button_goes_through_the_wrapper():
    # The button bound the first `closeSettingsModal` at load, so a wrapper added by the
    # lazy file never ran from it: every way out must call the name, not hold the function.
    assert '$("settings-close").addEventListener("click", closeSettingsModal)' not in SETTINGS
    wrapper = CONTROLS[CONTROLS.index("function closeSettingsModalEndingPreview(") :][:700]
    assert "SURFACES.park(`settings-${name}`)" in wrapper
    assert 'classList.contains("hidden")' in wrapper, "a window opened again before the park must keep its panes"


#: The least of a DOM that the surface code touches: nodes that move, fragments that
#: answer getElementById, templates that hold a fragment.
FAKE_DOM = r"""
class Node {
  constructor(id) { this.id = id; this.kids = []; this.parentNode = null; this.listeners = []; this.dataset = {}; }
  get childNodes() { return [...this.kids]; }
  append(...nodes) { for (const n of nodes) { const list = n.isFrag ? n.childNodes : [n]; for (const k of list) { if (k.parentNode) k.parentNode.kids.splice(k.parentNode.kids.indexOf(k), 1); k.parentNode = this; this.kids.push(k); } } }
  replaceWith(frag) { const p = this.parentNode; const at = p.kids.indexOf(this); p.kids.splice(at, 1); this.parentNode = null; const moved = frag.childNodes; for (const k of moved) { frag.kids.splice(frag.kids.indexOf(k), 1); k.parentNode = p; } p.kids.splice(at, 0, ...moved); }
  getElementById(id) { for (const k of this.kids) { if (k.id === id) return k; const deep = k.getElementById(id); if (deep) return deep; } return null; }
  walk(out = []) { for (const k of this.kids) { out.push(k); k.walk(out); } return out; }
  addEventListener(...args) { this.listeners.push(args[0]); }
}
class Frag extends Node { constructor() { super(null); this.isFrag = true; } }
const root = new Node("root");
const tpls = [];
for (const pane of ["settings-a", "settings-b"]) {
  const section = new Node(pane);
  const tpl = new Node(null);
  tpl.dataset.surface = pane;
  tpl.content = new Frag();
  tpl.content.append(new Node(pane + "-field"));
  section.append(tpl);
  root.append(section);
  tpls.push(tpl);
}
const document = {
  getElementById: (id) => root.getElementById(id),
  querySelectorAll: () => tpls,
  createDocumentFragment: () => new Frag(),
  createElement: () => Object.assign(new Node(null), { content: new Frag(), dataset: {} }),
};
const window = {};
const setTimeout = () => 0;
"""


@needs_node
def test_a_listener_waits_for_its_pane_and_a_parked_pane_comes_back_with_the_same_nodes():
    script = "\n".join(
        [
            FAKE_DOM,
            BODY_JS,
            """
            const out = {};
            const ran = [];
            const once = () => ran.push("once");
            SURFACES.wire("settings-a-field", "click", () => {});
            out.waits = document.getElementById("settings-a-field") === null && !SURFACES.get("settings-b").done;
            onSurface("settings-a", once);
            onSurface("settings-a", once);
            surfaceBuild("settings-a");
            const field = document.getElementById("settings-a-field");
            out.wired = field.listeners.length;
            out.ranOnce = ran.length;
            out.otherPaneUnbuilt = document.getElementById("settings-b-field") === null;
            SURFACES.park("settings-a");
            out.parkedGone = document.getElementById("settings-a-field") === null;
            out.parkedHeld = SURFACES.peek("settings-a", "settings-a-field") === field;
            out.back = surfaceFind("settings-a-field") === field;
            out.wiredAfter = field.listeners.length;
            out.oneCopy = root.walk().filter((n) => n.id === "settings-a-field").length;
            console.log(JSON.stringify(out));
            """,
        ]
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["waits"], "wire built a pane, or built the wrong one"
    assert out["wired"] == 1 and out["ranOnce"] == 1, out
    assert out["otherPaneUnbuilt"], "building one pane built its neighbour"
    assert out["parkedGone"] and out["parkedHeld"], "a parked pane is still in the page, or lost"
    assert out["back"] and out["wiredAfter"] == 1 and out["oneCopy"] == 1, out


@needs_node
def test_a_fill_waits_for_its_pane_builds_nothing_else_and_the_last_value_wins():
    # Visiting Personas read the preferences, and the read's `$("pref-...")` for the other
    # panes' controls built searchindex, preferences, general, data and account: 4 to 6
    # panes (5 to 20 ms each at 4x CPU) on a visit to a pane that holds none of them.
    script = "\n".join(
        [
            FAKE_DOM,
            BODY_JS,
            """
            const out = {};
            const seen = [];
            SURFACES.fill("settings-a-field", (el) => seen.push("first"));
            SURFACES.fill("settings-a-field", (el) => seen.push("second"));
            out.waits = seen.length === 0 && document.getElementById("settings-a-field") === null;
            out.noneBuilt = !SURFACES.get("settings-a").done && !SURFACES.get("settings-b").done;
            surfaceBuild("settings-a");
            out.applied = seen.join();
            out.neighbour = document.getElementById("settings-b-field") === null;
            SURFACES.fill("settings-a-field", (el) => seen.push("live"));
            out.live = seen.join();
            SURFACES.fill("nowhere", () => seen.push("never"));
            out.unknown = seen.includes("never");
            SURFACES.park("settings-a");
            SURFACES.fill("settings-a-field", () => seen.push("parked"));
            const before = seen.length;
            surfaceFind("settings-a-field");
            out.parkedFilled = seen.slice(before).join();
            console.log(JSON.stringify(out));
            """,
        ]
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["waits"] and out["noneBuilt"], "a fill built its pane"
    assert out["applied"] == "second", "the last fill for a control must be the one that runs"
    assert out["neighbour"], "filling one pane's control built another pane"
    assert out["live"] == "second,live" and not out["unknown"], out
    assert out["parkedFilled"] == "parked", "a parked pane's fill must run when it comes back"


def test_reading_the_preferences_touches_no_pane_through_dollar():
    # `$` builds the pane holding an id. renderPrefs and what it calls (markPrefsSaved,
    # updateProfileCount, mountProfileLook) fill four panes' controls: each goes through
    # `SURFACES.fill`, so the read for Personas builds Personas and nothing else.
    prefs = (JS / "settings-prefs.js").read_text(encoding="utf-8")
    start = prefs.index("const PREFS_FILLS")
    body = prefs[start : prefs.index("// --- Settings, Web search")]
    assert not re.search(r"(?<![\w.])\$\(", body), "renderPrefs asks `$` for a control: it builds that pane"
    saved = (JS / "settings-panes.js").read_text(encoding="utf-8")
    saved = saved[saved.index("function markPrefsSaved(") :][:400]
    assert "$(" not in saved
    assert body.count("SURFACES.fill(") >= 4


def test_watching_a_section_does_not_build_help_to_find_its_topics():
    # `settingsIndexWatchSection` ran at every visit and asked `$("help-topics")`: the first open
    # built Help (6 to 11 ms at 4x CPU, 92 elements) though Models was the pane shown.
    find = (JS / "settings-find.js").read_text(encoding="utf-8")
    watch = find[find.index("function settingsIndexWatchSection(") :][:900]
    assert 'document.getElementById("help-topics")' in watch
    assert '$("help-topics")' not in watch


@needs_node
def test_leaving_help_drops_its_topics_a_slice_at_a_time():
    # Dropping the 1,770 topic nodes in one `replaceChildren` was a 220 to 350 ms task at 4x CPU
    # on the switch after Help (the next pane's own work came with it). `helpTopicsDrop` removes
    # the rows in slices of at most HELP_DROP_SLICE, one timer apiece, then their groups.
    find = (JS / "settings-find.js").read_text(encoding="utf-8")
    start = find.index("const HELP_DROP_SLICE")
    fn = find[start : find.index("\n  }\n", find.index("function helpTopicsDrop(")) + 5]
    script = (
        r"""
        const timers = [];
        const setTimeout = (fn) => timers.push(fn);
        const mk = (kids = []) => ({ children: kids, removed: false, remove() { this.removed = true; } });
        const groups = [mk([...Array(130)].map(() => mk())), mk([...Array(40)].map(() => mk()))];
        const heads = [mk(), mk()];
        let helpTopicsLoad = null;
        const box = { children: [heads[0], groups[0], heads[1], groups[1]], dataset: {} };
        """
        + fn
        + r"""
        helpTopicsDrop(box);
        const slices = [];
        const count = () => groups.flatMap((g) => g.children).filter((r) => r.removed).length;
        let last = count();
        slices.push(last);
        while (timers.length) { timers.shift()(); const now = count(); slices.push(now - last); last = now; }
        console.log(JSON.stringify({ slices, tail: [...heads, ...groups].every((n) => n.removed), total: last, marked: "dropping" in box.dataset }));
        """
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert out["total"] == 170 and out["tail"], out
    # The "dropping" mark is cleared once the slices end, so a later search draws the topics again.
    assert not out["marked"], out
    assert max(out["slices"]) <= int(re.search(r"HELP_DROP_SLICE = (\d+)", fn).group(1)), out
    assert len(out["slices"]) >= 4, "the drop was not spread over timers"
