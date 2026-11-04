"""More behaviour for the companion and Atlas (INBOX 1581, the owner,
2026-11-03: "is there more behaviour and npc improvements we can add to and
make with the atlas avatars and general companions??").

The ranked list is SESSION_BRIEFS.md "Brief 88 continues" (N1 to N10). Built
here: moods by the part of the day (N1), Atlas's rare habits (N2), and five
reactions every companion plays through `nameMarkBuddyReact` and
`NMB_MIND.saw` (N3 to N6: a search that finds nothing, a find after a miss,
a fast pointer, a long carry, a note binned), and first readers that wait
for an arriving page to settle (N7). Every behaviour keeps the brief's
rules, each tested below: no `pointer-events`, never while a field is typed
in, transform and opacity only with no frame loop, nothing under
`data-motion="reduced"`, no layout read in the act. The pure parts run in a
node vm with a fixed clock; the hooks are checked in the source.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_atlas_micro import HARNESS as MICRO_HARNESS
from tests.test_atlas_micro import MICRO
from tests.test_companion_mind import HARNESS as MIND_HARNESS
from tests.test_companion_mind import MIND

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
AV = (JS / "avatars.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")
MENU = (JS / "companion-menu.js").read_text(encoding="utf-8")
SETTINGS = (JS / "companion-settings.js").read_text(encoding="utf-8")
CARDS = (JS / "note-cards.js").read_text(encoding="utf-8")
TOPICS = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    match = re.search(rf"^(?:async )?function {name}\(.*?^\}}", src, re.S | re.M)
    assert match, name
    return match.group(0)


def _block(src: str, start: str) -> str:
    """From `start` to the first line indented as it is that closes it."""
    i = src.index(start)
    indent = len(start) - len(start.lstrip())
    end = re.compile(rf"^ {{{indent}}}\}}", re.M).search(src, i + len(start))
    assert end, start
    return src[i : end.end()]


def _node(script: str, *args: str):
    run = subprocess.run(["node", "-e", script, *args], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


# --- N1: the part of the day ---------------------------------------------------


@needs_node
def test_the_day_has_four_parts_and_each_has_its_pool() -> None:
    line = re.search(r"^atlasDriftState\.phase = .*$", ATLAS, re.M).group(0)
    out = _node("const atlasDriftState = {};" + line + "process.stdout.write(JSON.stringify(Array.from({length: 24}, (_, h) => atlasDriftState.phase(h))));")
    assert out[5] == "night" and out[6] == "morning" and out[10] == "morning"
    assert out[11] == "afternoon" and out[16] == "afternoon"
    assert out[17] == "evening" and out[21] == "evening" and out[22] == "night" and out[0] == "night"
    pool = re.search(r"const ATLAS_DRIFT_POOL = \{(.*?)\n\};", ATLAS, re.S).group(1)
    assert set(re.findall(r"^\s+(\w+): \[", pool, re.M)) == {"morning", "afternoon", "evening", "night"}
    pace = re.search(r"atlasDriftState\.pace = \{(.*?)\};", ATLAS).group(1)
    assert "morning: 0.85" in pace and "night: 1.3" in pace, "the drift slows as the day winds down"
    # The drift picks from the hour's part, and the companion's energy follows it.
    assert "ATLAS_DRIFT_POOL[phase]" in _fn(ATLAS, "atlasDrift")
    assert "atlasDriftState.phase(hour)" in _fn(AV, "nameMarkBuddyTick")


@needs_node
def test_the_small_moves_lean_with_the_part_of_the_day() -> None:
    out = _node(MICRO_HARNESS + r"""
const count = (phase, typing = false) => { const n = {}; for (let i = 0; i < 6000; i += 1) { const k = ctx.__pick({ hour: 12, phase, typing, idle: 0, mood: "calm", look: "masculine", sinceCast: 1e9, now: 1e12, rareAt: {}, pointer: true }); n[k] = (n[k] || 0) + 1; } return n; };
process.stdout.write(JSON.stringify({ morning: count("morning"), evening: count("evening") }));
""", MICRO)
    m, e = out["morning"], out["evening"]
    assert m["glance"] > e["glance"] * 1.2, (m, e)
    assert e["blink"] > m["blink"], (m, e)


# --- N2: Atlas's rare habits -----------------------------------------------------

RARE = ("around", "hum", "settle", "double")


@needs_node
def test_rare_habits_come_seldom_and_never_while_typing() -> None:
    out = _node(MICRO_HARNESS + r"""
const RARE = ["around", "hum", "settle", "double"];
const run = (c) => { const n = {}; for (let i = 0; i < 6000; i += 1) { const k = ctx.__pick({ hour: 12, phase: "afternoon", idle: 0, mood: "calm", look: "masculine", sinceCast: 1e9, now: 1e12, rareAt: {}, pointer: true, ...c }); n[k] = (n[k] || 0) + 1; } return RARE.map((k) => n[k] || 0); };
const recent = Object.fromEntries(RARE.map((k) => [k, 1e12 - 60000]));
const old = Object.fromEntries(RARE.map((k) => [k, 1e12 - 200000]));
process.stdout.write(JSON.stringify({
  free: run({}), recent: run({ rareAt: recent }), old: run({ rareAt: old }),
  typing: run({ typing: true }), off: run({ rareOff: true }), nopointer: run({ pointer: false }),
}));
""", MICRO)
    assert all(n > 0 for n in out["free"]), out["free"]
    assert sum(out["free"]) < 6000 * 0.15, "rare: under a sixth of the beats together"
    assert out["recent"] == [0, 0, 0, 0], "each at most once in three minutes"
    assert all(n > 0 for n in out["old"])
    typing = dict(zip(RARE, out["typing"]))
    assert typing["around"] == typing["hum"] == typing["double"] == 0, typing
    assert out["off"] == [0, 0, 0, 0], "Little habits and reactions off"
    assert out["nopointer"][3] == 0, "no double take with no pointer to look at"


@needs_node
def test_rare_habits_play_transform_or_translate_with_no_frame_loop() -> None:
    out = _node(MICRO_HARNESS + r"""
const res = {};
for (const k of ["hum", "settle", "around", "double"]) {
  calls.anim.length = 0; calls.aim.length = 0; calls.blink = 0; timers.length = 0;
  ctx.atlasMicroDo(k, box);
  for (let i = 0; i < 6; i += 1) { const [f] = timers.shift() || []; if (f) f(); }
  res[k] = { props: [...new Set(calls.anim.flatMap((a) => a.frames.flatMap((f) => Object.keys(f).filter((p) => p !== "offset"))))], targets: [...new Set(calls.anim.map((a) => a.name))], aims: calls.aim.length, blink: calls.blink, at: vm.runInContext("atlasMicroState", ctx).rareAt[k] > 0 };
}
res.raf = calls.raf;
process.stdout.write(JSON.stringify(res));
""", MICRO)
    assert out["hum"]["props"] == ["transform"] and set(out["hum"]["targets"]) == {"head", "hair"}
    assert out["settle"]["props"] == ["translate"] and out["settle"]["targets"] == ["body"]
    assert out["around"]["aims"] >= 3 and out["around"]["props"] == []
    assert out["double"]["aims"] >= 3 and out["double"]["blink"] == 1
    assert all(out[k]["at"] for k in RARE), "each stamps its own cooldown"
    assert out["raf"] == 0, "no frame loop"


def test_rare_habits_read_no_layout_and_touch_no_pointer_events() -> None:
    rare = _block(MICRO, "atlasMicroDo.rare = function")
    for banned in ("getBoundingClientRect", "getComputedStyle", "offsetWidth", "requestAnimationFrame", "pointer-events", "pointerEvents", "composite"):
        assert banned not in rare, banned
    tick = _fn(MICRO, "atlasMicroTick")
    assert 'dataset.motion === "reduced"' in tick, "nothing under data-motion=reduced, the Always choice included"


# --- N3 to N6: the reactions ---------------------------------------------------------

REACT_HARNESS = r"""
const vm = require("vm");
let NOW = 1_800_000_000_000;
const timers = [];
const saw = [];
const classes = new Set();
const buddy = { classList: { contains: (c) => classes.has(c), add() {}, remove() {} }, dataset: {} };
const ctx = {
  Math, Object, Number, JSON, Date: { now: () => NOW },
  document: { hidden: false, getElementById: () => buddy, documentElement: { dataset: {} } },
  nmb: { keyAt: 0, act: "", mind: { saw: (k) => saw.push(k) } },
  off: false, still: false,
  nameMarkBuddyStill: () => ctx.still, nameMarkBuddyMenuOpen: () => false, nameMarkBuddyActOff: (a) => ctx.off && a === "habits",
  nameMarkBuddyAim() {}, nameMarkBuddyRelease() {}, nameMarkBuddyExpress() {}, nameMarkBuddyAct() {}, nameMarkBuddyRemark() {},
  NAME_MARK_BUDDY_ACTS: { peek: { poses: [] } },
  setTimeout: (f, ms) => { timers.push([f, ms]); return timers.length; }, clearTimeout() {},
};
vm.createContext(ctx);
vm.runInContext(process.argv[1], ctx);
const react = (k) => vm.runInContext(`nameMarkBuddyReact(${JSON.stringify(k)})`, ctx);
const fresh = () => { NOW += 120000; saw.length = 0; timers.length = 0; ctx.nmb.reactCool = {}; ctx.nmb.reactAt = 0; ctx.nmb.habitWait = {}; };
const out = (v) => process.stdout.write(JSON.stringify(v));
"""


def _react_src() -> str:
    table = re.search(r"^const NMB_REACTIONS = \{.*?^\};", AV, re.S | re.M).group(0)
    gap = re.search(r"^const NMB_REACT_GAP = .*$", AV, re.M).group(0)
    return "\n".join([table, gap, _fn(AV, "nameMarkBuddyReact")])


@needs_node
def test_each_reaction_fires_and_keeps_its_cooldown() -> None:
    out = _node(REACT_HARNESS + r"""
const r = {};
for (const k of ["nothing", "whoosh", "carried", "binned"]) { fresh(); r[k] = [react(k), react(k), saw.slice()]; }
fresh(); r.foundAlone = [react("found"), saw.slice()];
fresh(); ctx.nmb.missAt = NOW - 5000; r.foundAfterMiss = [react("found"), saw.slice()];
out(r);
""", _react_src())
    for kind in ("nothing", "whoosh", "carried", "binned"):
        assert out[kind] == [True, False, [kind]], (kind, out[kind])
    assert out["foundAlone"] == [False, []], "a find is only news after a miss"
    assert out["foundAfterMiss"] == [True, ["found"]]


@needs_node
def test_a_reaction_waits_for_the_keys_to_rest_and_then_gives_up() -> None:
    out = _node(REACT_HARNESS + r"""
fresh(); ctx.nmb.keyAt = NOW - 300;
const first = react("nothing");
const waited = [saw.length, timers.length, timers[0] && timers[0][1]];
// Keys at rest when the timer fires: it plays.
ctx.nmb.keyAt = NOW - 2000; timers.shift()[0]();
const after = saw.slice();
// Typing throughout: four tries, then it is dropped.
fresh(); let tries = 0;
ctx.nmb.keyAt = NOW; react("whoosh");
while (timers.length && tries < 10) { tries += 1; ctx.nmb.keyAt = NOW; timers.shift()[0](); }
out({ first, waited, after, tries, dropped: saw.length });
""", _react_src())
    assert out["first"] is False and out["waited"][:2] == [0, 1] and out["waited"][2] == 1300
    assert out["after"] == ["nothing"]
    assert out["tries"] == 4 and out["dropped"] == 0


@needs_node
def test_no_reaction_under_reduced_motion_off_or_over_an_act() -> None:
    out = _node(REACT_HARNESS + r"""
const r = {};
fresh(); ctx.document.documentElement.dataset.motion = "reduced"; r.reduced = react("nothing"); delete ctx.document.documentElement.dataset.motion;
fresh(); ctx.off = true; r.off = react("nothing"); ctx.off = false;
fresh(); ctx.nmb.act = "wave"; r.act = react("whoosh"); ctx.nmb.act = "";
fresh(); ctx.still = true; r.still = react("binned"); ctx.still = false;
fresh(); classes.add("nm-buddy-dragging"); r.carried = react("carried"); classes.clear();
fresh(); r.ok = react("binned");
r.saw = saw.slice();
// The shake comes after the landing, while it looks around once.
fresh(); ctx.nmb.act = "look"; r.overLook = [react("carried"), (ctx.nmb.reactAt = 0, react("whoosh"))]; ctx.nmb.act = "";
out(r);
""", _react_src())
    assert out == {"reduced": False, "off": False, "act": False, "still": False, "carried": False, "ok": True, "saw": ["binned"], "overLook": [True, False]}


@needs_node
def test_a_reaction_before_the_first_tick_fetches_the_mind_and_plays_once() -> None:
    # Measured 2026-11-03: in the first minute nmb.mind was not loaded yet, so
    # every habit was dropped; now it fetches companionMenu and plays once.
    out = _node(REACT_HARNESS + r"""
const mind = ctx.nmb.mind; delete ctx.nmb.mind;
let fetched = 0, then = null;
ctx.ensureModule = (name) => { fetched += 1; return { then: (f) => { then = () => f(name === "companionMenu"); } }; };
fresh();
const first = react("nothing");
ctx.nmb.mind = mind; NOW += 10; then();
out({ first, fetched, saw: saw.slice() });
""", _react_src())
    assert out == {"first": False, "fetched": 1, "saw": ["nothing"]}


@needs_node
def test_what_it_does_about_it_is_a_face_a_tilt_or_a_short_translate() -> None:
    out = _node(MIND_HARNESS + r"""
const anims = [];
const body = { animate: (frames, opts) => { anims.push([frames, opts]); return {}; } };
const me = { isConnected: true, dataset: { seed: "x" }, classList: { contains: () => false }, querySelector: () => body };
ctx.setAtlasMood = (m) => calls.push(["mood", m]);
ctx.nameMarkBuddyExpress = (e) => calls.push(["express", e]);
ctx.nmb.pointer = [10, 10];
const r = {};
for (const k of ["nothing", "found", "whoosh", "carried", "binned"]) {
  calls.length = 0; anims.length = 0; timers.length = 0;
  ctx.nmb.carriedMs = 6000;
  MIND.saw(k, me, NOW);
  timers.splice(0).forEach(([f]) => f());
  r[k] = { calls: calls.map((c) => c.slice(0, 2)), props: [...new Set(anims.flatMap(([f]) => f.flatMap((x) => Object.keys(x))))], opts: anims.map(([, o]) => o) };
}
r.missAt = ctx.nmb.missAt;
out(r);
""", MIND)
    assert ["tilt", 0.55] in out["nothing"]["calls"] or ["tilt", -0.55] in out["nothing"]["calls"]
    assert ["express", "confused"] in out["nothing"]["calls"]
    assert ["act", "nod"] in out["found"]["calls"]
    assert ["act", "blink"] in out["whoosh"]["calls"] and ["aim"] in [c[:1] for c in out["whoosh"]["calls"]]
    assert out["carried"]["props"] == ["translate"], "the shake moves translate only"
    assert all("composite" not in o and o["duration"] <= 700 for o in out["carried"]["opts"])
    assert ["express", "dizzy"] in out["carried"]["calls"], "dizzy after more than five seconds held"
    assert ["express", "nervous"] in out["binned"]["calls"]


def test_the_reactions_read_no_layout_and_touch_no_pointer_events() -> None:
    saw = _block(MENU, "  saw(kind, buddy, now) {")
    for banned in ("getBoundingClientRect", "getComputedStyle", "offsetWidth", "requestAnimationFrame", "pointer-events", "pointerEvents", "composite"):
        assert banned not in saw, banned


def test_the_app_tells_it_what_happened() -> None:
    on = _fn(ATLAS, "atlasOn")
    assert "nameMarkBuddyReact(event)" in on, "found or nothing, the last of a burst only"
    assert 'window.nameMarkBuddyReact?.("binned")' in _fn(CARDS, "binNoteWithUndo")
    notice = _fn(AV, "nameMarkBuddyNotice")
    assert 'nameMarkBuddyReact("whoosh")' in notice and "speed > 2200 && last" in notice
    assert "< 160) nameMarkBuddyReact" in notice, "close is the nearest point of the path between two samples"
    # Measured: a fixed 1.1 s after the release fell inside the landing when
    # it dropped first, and was refused; the landing's own end plays it now.
    act = _fn(AV, "nameMarkBuddyAct")
    assert 'act === "land" && nmb.carriedMs >= 2500' in act and 'nameMarkBuddyReact("carried")' in act
    assert "nmb.carriedMs = (event?.timeStamp" in AV


# --- N7: first readers wait for the page to settle --------------------------------------


def test_first_readers_wait_for_an_arriving_page() -> None:
    frame = _fn(MOTION, "atlasRigFrame")
    assert "const settling = !!rig.reads && (now < (globalThis.uiSettlingUntil || 0) || (!!buddy && nameMarkBuddyBehindCover()));" in frame  # INBOX 1667: a dialog over the figure holds the rig the same way
    assert "const look = (rig.dirty || !rig.reads) && !settling;" in frame
    assert "rig.still = busy || (settling && rig.dirty) ? 0" in frame, "it stays awake until it has read again"
    mood = _fn(ATLAS, "setAtlasMood")
    assert "window.uiSettlingUntil" in mood and "setTimeout(() => nmb.afterClean(() => nameMarkBuddyBlend(boxes, apply, 700), 6, apply), Math.max(0, settling + 20))" in mood  # INBOX 1667: a frame on as well, and a dirty page snaps
    # The follow frame holds only while it is glued to a panel (1575's hold). One
    # harness (1575's nine-tab series at 4x, 500 seeded notes, three runs each),
    # reads and forced ms under the follow frame: glue-only 155 and 2.65 s, no hold
    # 218 and 3.05 s, an unconditional hold 152 and 2.86 s (1581's two flip runs
    # had favoured no hold over the unconditional one, 32 and 131 ms against 41
    # and 220; neither was the glue-only hold).
    follow = _fn(AV, "nameMarkBuddyFollowFrame")
    assert "const settling = !!nmb.glue && now < (window.uiSettlingUntil || 0);" in follow


@needs_node
def test_atlas_play_restarts_with_no_forced_layout() -> None:
    out = _node(r"""
const vm = require("vm");
let reads = 0;
const rafs = [];
const mk = () => { const c = new Set(); return { classList: { add: (x) => c.add(x), remove: (x) => c.delete(x), contains: (x) => c.has(x) }, getBoundingClientRect: () => { reads += 1; return {}; }, isConnected: true, c }; };
const marks = [mk(), mk()];
// The move goes on two frames on (1575's afterFrames, merged here); a second
// call before then takes the first one's place (its turn guard).
const ctx = { document: { querySelectorAll: () => marks, hidden: false }, requestAnimationFrame: () => { throw new Error("no frame"); }, afterFrames: (f) => rafs.push(f), setTimeout: () => {} };
vm.createContext(ctx);
vm.runInContext(process.argv[1], ctx);
ctx.atlasPlay("nod");
rafs.shift()();
const first = marks.map((m) => m.c.has("atl-play-nod"));
ctx.atlasPlay("nod");
const during = marks.map((m) => m.c.has("atl-play-nod"));
ctx.atlasPlay("nod");
rafs.shift()();
const stale = marks.map((m) => m.c.has("atl-play-nod"));
rafs.shift()();
const after = marks.map((m) => m.c.has("atl-play-nod"));
process.stdout.write(JSON.stringify({ reads, first, during, stale, after }));
""", _fn(ATLAS, "atlasPlay"))
    assert out == {"reads": 0, "first": [True, True], "during": [False, False], "stale": [False, False], "after": [True, True]}


# --- N7: the switch, its help and its Guide topic (standing order 13) ------------------------


def test_the_switch_its_popover_and_its_guide_topic() -> None:
    row = re.search(r'\["habits", "([^"]+)", \["habits"\]\]', AV)
    assert row and row.group(1).startswith("Little habits and reactions")
    assert 'if (key === "habits") mountBuddyActivities.help(host, row);' in SETTINGS
    help_src = _block(SETTINGS, "mountBuddyActivities.help = (host, row) => {")
    assert 'help.dataset.helpFor = id;' in help_src and '"avatar-buddy-habits-help"' in help_src
    assert "row.after(body)" in help_src, "the popover sits outside the label, so its text never flips the switch"
    assert "initHelpToggles(host)" in help_src
    assert '"id": "companion-habits"' in TOPICS and "Little habits and" in TOPICS
    assert '"companion-habits": {"title"' in TOPICS
    assert '"companion-remarks", "companion-habits"' in TOPICS, "listed in the Guide's Look and feel"
