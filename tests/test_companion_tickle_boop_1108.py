"""Companion catalogue B5, the in-app half (`int.tickle`, `int.boop_nose`; INBOX 1696 kk): a fast small rub on the body is a
tickle, a click on the nose is a boop. The two decisions are pure functions run as written in node; the wiring (the pointer
move handler, the click's poke, the switch under What it does) is pinned as text. The desk half is
`tests/test_overlay_tickle_boop_1108.py`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
RECT = {"left": 100, "top": 200, "width": 100, "height": 120}  # the head is the top 42 percent: y 200 to 250


def fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def touch_scope() -> str:
    """The one scope `nmb.touch` is built in (the shared scope gains one name, not seven)."""
    start = AV.index("nmb.touch = (() => {")
    return AV[start : AV.index("\n})();\n", start) + 7]


def inner(name: str) -> str:
    scope = touch_scope()
    start = scope.index(f"  function {name}(")
    return scope[start : scope.index("\n  }\n", start)]


def run(body: str):
    script = f"const nmb = {{}};\n{fn('nameMarkBuddyStrokes')}\n{touch_scope()}\nconsole.log(JSON.stringify({body}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def zigzag(x: int, y: int, n: int, swing: int, every: int = 100, rise: int = 0) -> list[list[int]]:
    return [[x + (swing if i % 2 else -swing) // 2, y + rise * i // max(1, n), i * every] for i in range(n + 1)]


def tickled(samples: list[list[int]]) -> bool:
    return run(f"nmb.touch.tickled({json.dumps(samples)}, {json.dumps(RECT)})")


@needs_node
def test_a_fast_small_rub_below_the_head_is_a_tickle() -> None:
    assert tickled(zigzag(150, 290, 10, 10))


@needs_node
def test_a_long_slow_rub_on_the_head_two_strokes_and_a_tremor_are_not() -> None:
    assert not tickled(zigzag(150, 290, 10, 50)), "a long stroke is a rub"
    assert not tickled(zigzag(150, 290, 2, 10)), "two strokes"
    assert not tickled(zigzag(150, 220, 10, 10)), "on the head, a pat or a rub"
    assert not tickled(zigzag(150, 290, 10, 10, every=400)), "too slow: the strokes are spread over 4 s"
    tremor = [[150 + (i * 7919) % 5 - 2, 290 + (i * 104729) % 5 - 2, i * 16] for i in range(80)]
    assert not tickled(tremor), "a hand's tremor turns as often, but never as far as a stroke"
    assert not tickled(zigzag(150, 290, 10, 10, rise=60)), "up as far as across is a wipe, not a tickle"


@needs_node
def test_a_click_on_the_nose_is_a_boop_and_elsewhere_is_not() -> None:
    def on(x: int, y: int) -> bool:
        return run(f"nmb.touch.onNose({json.dumps(RECT)}, {x}, {y})")

    assert on(150, 240)  # the middle of the face, between 18 and 42 percent of the height
    assert not on(150, 290), "the belly"
    assert not on(150, 205), "the top of the head"
    assert not on(105, 240), "the face's far edge"
    assert not run("nmb.touch.onNose(null, 150, 240)")


def test_the_handlers_are_wired_and_have_a_switch() -> None:
    assert "nmb.touch.tickled(rub, face.getBoundingClientRect())" in AV and "nmb.touch.tickle(buddy)" in AV
    assert "nmb.touch.onNose(face.getBoundingClientRect(), event.clientX, event.clientY)" in AV
    assert "if (nose && !wasAsleep && nmb.touch.boop(buddy)) return;" in AV
    row = re.search(r'\["rub", "[^"]*", \[([^\]]*)\]\]', AV)
    assert row and '"tickle"' in row.group(1) and '"boop"' in row.group(1)
    for name in ("tickle", "boop"):
        assert "nameMarkBuddyStill()" in inner(name), f"{name} stays still under Still motion"
        assert f'nameMarkBuddyActOff("{name}")' in inner(name)
    assert "nameMarkBuddyAsleep(buddy)" in inner("tickle")


def test_the_catalogue_counts_both_as_built_on_both_sides() -> None:
    entries = {e["id"]: e for e in json.loads((ROOT / "frontend" / "companion-catalogue.json").read_text(encoding="utf-8"))["entries"]}
    for key in ("int.tickle", "int.boop_nose"):
        assert entries[key]["app"]["s"] == "built" and entries[key]["desk"]["s"] == "built", key
