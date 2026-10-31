"""One behaviour model for every companion, with a state and traits (INBOX 1463).

The owner, 2026-10-31: "I think the companions need a much better npc upgrade
like with decision making ai, behaviorur, patetrns, methods of moving or
switching positions, atlas and how it acts/looks/does everything, the regular
companions ... and for it to be a non intrusive companion".

Pinned here: its state is named (resting, idling, moving, reacting,
sleeping) and the tick decides nothing while it moves or reacts; it never
sits on the focused control or the caret's line; it makes room when the
pointer rests on a control it covers; far wanders wait until you have left it
alone; and Atlas and the others run the same decisions with a few traits.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_state_is_worked_out_from_what_it_keeps() -> None:
    consts = "\n".join(re.search(rf"^const {n} = .*;$", AV, re.M).group(0) for n in ("NMB_REACT_HOLD_MS",))
    script = "\n".join([
        consts,
        'const NMB_RESTING_ACTS = new Set(["lie", "read"]);',
        "let nmb = {};",
        "const el = (...cls) => ({ classList: { contains: (c) => cls.includes(c) } });",
        _fn("nameMarkBuddyStateOf"),
        "const NOW = 100000; const out = [];",
        "nmb = {}; out.push(nameMarkBuddyStateOf(el('nmb-sleep', 'nmb-walking'), NOW));",
        "nmb = {}; out.push(nameMarkBuddyStateOf(el('nmb-walking'), NOW));",
        "nmb = { anim: { playState: 'running' } }; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "nmb = { flight: {} }; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "nmb = { lastPoke: NOW - 1000, act: 'wave' }; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "nmb = { reactAt: NOW - 5000, act: 'wave' }; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "nmb = {}; out.push(nameMarkBuddyStateOf(el('nmb-think'), NOW));",
        "nmb = { act: 'read', anim: { playState: 'finished' } }; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "nmb = {}; out.push(nameMarkBuddyStateOf(el(), NOW));",
        "console.log(JSON.stringify(out));",
    ])
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert got == ["sleeping", "moving", "moving", "moving", "reacting", "idling", "reacting", "resting", "resting"]
    states = re.search(r"^const NMB_STATES = \[(.*)\];$", AV, re.M).group(1)
    assert states == '"resting", "idling", "moving", "reacting", "sleeping"'


def test_the_state_is_written_only_on_a_change_and_steers_the_tick() -> None:
    state = _fn("nameMarkBuddyState")
    assert "if (was !== state) {" in state and "buddy.dataset.state = state;" in state and "nmb.stateAt = Date.now();" in state
    # A reaction ends by the clock: looked at again when its hold is up (stateprobe.js read "reacting" ten seconds on).
    assert 'if (state === "reacting") nmb.stateTimer = setTimeout(() => nameMarkBuddyState(), NMB_REACT_HOLD_MS + 100);' in state
    tick = _fn("nameMarkBuddyTick")
    hold = tick[tick.index("const state = nameMarkBuddyState(buddy);") :]
    assert hold.index('if (state === "moving" || state === "reacting") {') < hold.index("nameMarkBuddyDecide()")
    # Kept current where it changes: an act, the schedule after one, a move and its end.
    assert "nameMarkBuddyState(buddy);" in _fn("nameMarkBuddyAct")
    assert "nameMarkBuddyState(buddy);" in _fn("nameMarkBuddySchedule")
    move = _fn("nameMarkBuddyMoveTo")
    assert "moving?.finished.then(() => nmb.anim === moving && nameMarkBuddyState(buddy), () => {});" in move


def test_it_never_sits_on_the_focused_control_or_the_caret() -> None:
    attention = _fn("nameMarkBuddyAttention")
    assert "document.activeElement" in attention and "box.width * box.height <= NMB_FOCUS_AREA" in attention
    assert "nameMarkBuddyCaret()" in attention
    caret = _fn("nameMarkBuddyCaret")
    assert "[contenteditable='true'], .cm-content" in caret and "range.getBoundingClientRect()" in caret
    assert "box.left - NMB_CARET_PAD" in caret
    assert "...nameMarkBuddyAttention()" in _fn("nameMarkBuddyObstacles")
    # A key or a press under it fades it at once, as a popup does, and it steps aside.
    assert "...nameMarkBuddyAttention()" in _fn("nameMarkBuddyDodge")


def test_it_makes_room_for_a_control_the_pointer_rests_on() -> None:
    soon = _fn("nameMarkBuddyRoomSoon")
    # Nothing read while the pointer moves; on it is reaching for it.
    assert "getBoundingClientRect" not in soon and "elementFromPoint" not in soon
    assert "if (d === 0 || d > nameMarkBuddyTraits().room) return;" in soon
    assert "setTimeout(() => nameMarkBuddyRoom(px, py), NMB_ROOM_MS)" in soon
    room = _fn("nameMarkBuddyRoom")
    assert "now - (nmb.roomAt || 0) < NMB_ROOM_COOL_MS" in room
    assert room.count("document.elementFromPoint(px, py)") == 1
    assert 'nmb.moveWhy = "making room for the pointer";' in room
    assert "nameMarkBuddyStepAside(here, [...nameMarkBuddyObstacles(nameMarkBuddyTab()), reach])" in room
    assert "nameMarkBuddyRoomSoon(px, py);" in _fn("nameMarkBuddyPointer")


def test_atlas_and_the_others_share_the_decisions_with_traits() -> None:
    traits = AV[AV.index("const NMB_TRAITS = {") :][:400]
    for name in ("atlas:", "shy:", "bold:", '"":'):
        assert name in traits, name
    assert "isAtlasSeed(" in _fn("nameMarkBuddyTraits")
    decide = _fn("nameMarkBuddyDecide")
    assert "const { loud } = nameMarkBuddyTraits();" in decide and "if (NMB_LOUD_ACTS.includes(act)) w *= loud;" in decide
    wander = _fn("nameMarkBuddyWander")
    assert "NMB_WANDER_ODDS) * nameMarkBuddyTraits().wander" in wander
    # Off across the page only once you have left it alone a minute; a few steps along its edge any time.
    assert wander.index("if (now - nmb.lastInput < NMB_WANDER_FAR_IDLE_MS) return false;") < wander.index("nameMarkBuddyChoose(tab, obstacles, [nmb.x + off, nmb.y], 4)")
    assert int(re.search(r"^const NMB_WANDER_FAR_IDLE_MS = (\d+);$", AV, re.M).group(1)) >= 60000
