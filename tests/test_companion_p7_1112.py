"""P7 (Brief 88 N8 and N10): the companion looks at a popup before it steps aside, and cheers when the note count crosses a
round number. Node with stubs; a fixed clock, nothing reads the real one."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
NODE = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _block(start_marker: str, end_marker: str) -> str:
    a = AV.index(start_marker)
    return AV[a : AV.index(end_marker, a)]


def _node(script: str) -> dict:
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_dodge_glances_at_the_popup_on_the_first_look_that_finds_it() -> None:
    body = _fn("nameMarkBuddyDodge")
    assert ".find((b) =>" in body and "nameMarkBuddyDodge.glance(hit)" in body
    assert 'if (over && !buddy.classList.contains("nmb-dodge"))' in body  # only the first look, not every 500 ms re-look
    glance = _block("nameMarkBuddyDodge.glance = ", "let nmbDodgeTimer")
    assert "nameMarkBuddyStill()" in glance and 'dataset.motion === "reduced"' in glance and "nameMarkBuddyAsleep" in glance
    assert "getBoundingClientRect" not in glance and "getComputedStyle" not in glance  # the box is already read: no layout


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_glance_aims_at_the_popups_middle_and_lets_go_after_a_beat() -> None:
    script = "\n".join([
        "const calls = [];",
        "let still = false, asleep = false, motion = '';",
        "const nmb = {};",
        "const document = { documentElement: { dataset: { get motion() { return motion; } } }, getElementById: () => ({}) };",
        "const nameMarkBuddyStill = () => still, nameMarkBuddyAsleep = () => asleep;",
        "const nameMarkBuddyAim = (p) => calls.push(['aim', p]), nameMarkBuddyRelease = () => {};",
        "const timers = []; const setTimeout = (f, ms) => { timers.push(ms); return timers.length; }; const clearTimeout = () => {};",
        "const nameMarkBuddyDodge = () => {};",
        _block("nameMarkBuddyDodge.glance = ", "let nmbDodgeTimer"),
        "nameMarkBuddyDodge.glance({ left: 100, right: 300, top: 40, bottom: 140 });",
        "still = true; nameMarkBuddyDodge.glance({ left: 0, right: 2, top: 0, bottom: 2 }); still = false;",
        "motion = 'reduced'; nameMarkBuddyDodge.glance({ left: 0, right: 2, top: 0, bottom: 2 }); motion = '';",
        "asleep = true; nameMarkBuddyDodge.glance({ left: 0, right: 2, top: 0, bottom: 2 });",
        "console.log(JSON.stringify({ calls, timers }));",
    ])
    out = _node(script)
    assert out["calls"] == [["aim", [200, 90]]]  # one look, at the middle; still, reduced motion and asleep look at nothing
    assert out["timers"] == [900]


def _milestone_run(total: int, kept: str | None) -> dict:
    start = AV.index("const NMB_MILESTONES")
    end = AV.index("\n};\n", AV.index("nameMarkBuddyStreak.milestone = ")) + 4
    script = "\n".join([
        f"const store = {json.dumps({} if kept is None else {'nm-buddy-milestone': kept})};",
        "const prefs = { get: (k, d) => (k in store ? store[k] : d), set: (k, v) => { store[k] = v; } };",
        "const reacts = [];",
        "const nameMarkBuddyReact = (k, t) => reacts.push([k, t]);",
        "function nameMarkBuddyStreak() {}",
        AV[start:end],
        f"const got = nameMarkBuddyStreak.milestone({total});",
        "console.log(JSON.stringify({ got, reacts, store }));",
    ])
    return _node(script)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_notebook_opened_at_a_round_number_only_records_it() -> None:
    r = _milestone_run(100, None)
    assert r["reacts"] == [] and r["store"]["nm-buddy-milestone"] == "100"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_crossing_the_next_round_number_cheers_once_and_says_the_count() -> None:
    r = _milestone_run(100, "50")
    assert r["got"] == 100 and r["reacts"] == [["milestone", {"say": "100 notes. That is a lot of thinking."}]]
    assert r["store"]["nm-buddy-milestone"] == "100"
    again = _milestone_run(101, "100")
    assert again["reacts"] == [] and again["got"] == 0  # the same number is never cheered twice
    assert _milestone_run(1999, "1000")["reacts"] == []
    assert _milestone_run(2000, "1000")["reacts"][0][1]["say"].startswith("2000 notes")
    assert _milestone_run(9, "0")["reacts"] == []  # under ten there is nothing to count


def test_the_milestone_is_a_reaction_row_with_its_own_cool_down_and_the_dashboard_passes_the_count() -> None:
    assert re.search(r"milestone: \{ cool: 60 \* 60 \* 1000, ms: 2400 \}", AV)
    assert 'kind === "streak" || kind === "milestone"' in AV
    dash = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert "nameMarkBuddyStreak(streak, stats.total_entries)" in dash
