"""An idle dashboard's follow loop looks seldomer the longer its panel holds still (INBOX 1741).

The owner's log (real Windows, dashboard): `nameMarkBuddyKeepUp` 7 calls a second, 20.7ms each. A resize
observer or a page transition renewed the loop's 1.5s for ever and a fixed 120ms nap made 8 looks a
second. Reproduced at 4x CPU with a renewal a second: 44 looks in 15s before.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _nap(args: list[list]) -> list[int]:
    script = _fn("nameMarkBuddyNapMs") + f"\nconsole.log(JSON.stringify({json.dumps(args)}.map(([r, ride]) => nameMarkBuddyNapMs(r, ride))));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_the_nap_lengthens_with_the_stillness() -> None:
    assert _nap([[0, False], [2, False], [3, False], [7, False], [8, False], [15, False], [16, False], [400, False]]) == [0, 0, 120, 120, 350, 350, 700, 700]


@needs_node
def test_a_cat_riding_its_area_keeps_its_slower_early_beat() -> None:
    assert _nap([[3, True], [9, True]]) == [300, 350]


def test_the_frame_uses_it_and_a_move_still_starts_over() -> None:
    assert "now + nameMarkBuddyNapMs(nmbFollow.rest, nmb.ride)" in AV
    assert "nmbFollow.rest = nmb.x === x && nmb.y === y ? nmbFollow.rest + 1 : 0;" in AV
