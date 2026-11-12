"""Opening a note from a dashboard list does not read layout in a write loop (INBOX 1667, the owner's 2026-11-07 log).

The log: `frame 5188ms on notes: avatars.js TimerHandler:setTimeout 4551ms (forced layout 4445ms); obj-drag.js
objDragMove 174ms; dashboard.js LI.onclick 156ms`, and the `input 4016ms` lines on `pointerout` and
`#agent-monitor-close` that are only events waiting behind that one task. A browser cannot run in pytest, so
these are static; the measured sweep is `scratchpad/p1667/open.js` (4x CPU, long-animation-frame, 48 titled
notes, companion on), and its numbers are in the CHANGELOG line.

The class: a loop over elements that writes and reads layout in the same body pays one whole-page layout a
turn; the readers named here read first (or only read) and write after.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

READS = re.compile(r"getBoundingClientRect|getClientRects|elementFromPoint|elementsFromPoint|offsetTop|offsetLeft|offsetHeight|offsetWidth|clientHeight|clientWidth|scrollHeight|scrollTop|getComputedStyle")
WRITES = re.compile(r"classList\.(?:add|remove|toggle)|\.style\.|\.style\.setProperty|setAttribute|removeAttribute|\.textContent\s*=|\.append|\.remove\(\)|\.innerHTML\s*=")
QUERY_LOOP = re.compile(r"for\s*\([^)]*\bof\b[^)]*querySelectorAll\([^)]*\)[^)]*\)\s*\{")


def _balanced(src: str, open_at: int) -> str:
    depth = 0
    for i in range(open_at, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_at : i + 1]
    raise AssertionError("unbalanced braces")


def _function(src: str, head: str) -> str:
    at = src.index(head)
    return _balanced(src, src.index("{", at))


def mixed_loops(body: str) -> list[str]:
    """Loop bodies over querySelectorAll that both read layout and write the DOM."""
    bad = []
    for m in QUERY_LOOP.finditer(body):
        loop = _balanced(body, m.end() - 1)
        if READS.search(loop) and WRITES.search(loop):
            bad.append(loop[:80])
    return bad


def test_the_lint_sees_a_read_after_a_write_in_one_loop() -> None:
    bad = "function f(){ for (const el of root.querySelectorAll('a')) { el.classList.add('x'); const r = el.getBoundingClientRect(); } }"
    assert mixed_loops(bad)
    fine = "function f(){ const boxes = []; for (const el of root.querySelectorAll('a')) { boxes.push(el.getBoundingClientRect()); } }"
    assert not mixed_loops(fine)


NAMED = [
    ("avatars.js", "function nameMarkBuddyControlsIn("),
    ("avatars.js", "function nameMarkBuddyControlBoxes("),
    ("avatars.js", "function nameMarkBuddyViewChanged("),
    ("avatars.js", "function nameMarkBuddyBeat("),
    ("avatars.js", "function nameMarkBuddyTick("),
    ("avatars.js", "function queueNameMarkBuddyCheck("),
    ("avatars.js", "function nameMarkBuddyCheck("),
    ("shell-reminders.js", "function syncScrollEdges("),
    ("capture-ask.js", "async function flashEntry("),
    ("notes-rail-spy.js", "function notesSpyPick("),
]


def test_the_readers_an_opened_note_wakes_do_not_read_in_a_write_loop() -> None:
    for name, head in NAMED:
        body = _function((JS / name).read_text(encoding="utf-8"), head)
        assert not mixed_loops(body), f"{name} {head}: a loop over querySelectorAll reads layout and writes the DOM"


def test_obj_drag_looks_once_a_frame_after_the_frame_has_drawn() -> None:
    src = (JS / "obj-drag.js").read_text(encoding="utf-8")
    assert "afterFrames(() => setTimeout(look), 1);" in src, "the hover look is a timer past the frame"
    assert "if (!overFrame) {" in src, "one look a frame, not one per pointerover"
    body = _function(src, "const look = () =>")
    assert body.count("show(") == 1, "the look reads boxes once"


def test_the_tab_switch_edge_sync_reads_a_frame_on_not_in_the_observers_microtask() -> None:
    src = (JS / "shell-reminders.js").read_text(encoding="utf-8")
    at = src.index("const scrollEdgeObserver = new MutationObserver(")
    block = src[at : at + 400]
    assert "new MutationObserver(() => syncScrollEdges())" not in src, "a direct call reads scrollTop right after the switch's writes"
    assert "afterFrames(() => setTimeout(() => {" in block and "syncScrollEdges();" in block
    # Intent moved (2026-11-07): a mutation before dashboard.js has loaded found no `afterFrames` and threw on
    # every boot; it is skipped until then (the first tab switch syncs).
    assert "if (scrollEdgeSync || !window.afterFrames) return;" in block, "once a frame, and never before the helper"
