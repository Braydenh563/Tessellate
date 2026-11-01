"""An idle page does no style work (audit 1101, rank 5 item 1).

Switching the companion from Atlas to Off left 28 running Web Animations on
detached nodes: the page then restyled 60 times a second on every tab until it
was reloaded (2 a second fresh; 0 to 2 on Notes, Dashboard and a board).
`dropAnimations` cancels a removed figure's animations while the node is still
in the page, and every place that removes or replaces a figure calls it.
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
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(src: str, name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", src, re.S | re.M)
    assert match, name
    return match.group(0)


@needs_node
def test_drop_animations_cancels_the_subtree_and_ignores_the_missing() -> None:
    script = (
        _fn(AVATARS, "dropAnimations")
        + r"""
const log = [];
const root = { getAnimations(o) { log.push(o.subtree); return [{ cancel: () => log.push("a") }, { cancel: () => log.push("b") }]; } };
dropAnimations(root);
dropAnimations(null);
dropAnimations({});
process.stdout.write(JSON.stringify(log));
"""
    )
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    assert json.loads(run.stdout) == [True, "a", "b"]


def test_every_removal_of_a_figure_drops_its_animations_first() -> None:
    hide = _fn(AVATARS, "nameMarkBuddyHide")
    assert re.search(r"dropAnimations\(buddy\);\s*buddy\?\.remove\(\)", hide)
    sync = _fn(AVATARS, "syncNameMarkBuddy")
    assert re.search(r"dropAnimations\(buddy\);\s*buddy\?\.remove\(\)", sync)
    assert re.search(r"dropAnimations\(old\);\s*old\?\.remove\(\)", sync)
    assert re.search(r"dropAnimations\(box\);\s*box\.replaceWith\(atlasFigure\(\)\)", ATLAS)


def test_the_pacer_list_is_emptied_when_the_companion_goes() -> None:
    assert "nmbTempo.anims = [];" in _fn(AVATARS, "nameMarkBuddyGone")
