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


def _run(script: str):
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:]
    return json.loads(run.stdout)


@needs_node
def test_only_a_plain_character_in_a_field_is_a_typing_key() -> None:
    out = _run(
        _fn(AVATARS, "nameMarkBuddyTypingKey")
        + r"""
const field = { closest: (s) => (/cm-content/.test(s) ? {} : null) };
const page = { closest: () => null };
const key = (o) => nameMarkBuddyTypingKey({ type: "keyup", key: "x", target: field, ...o });
process.stdout.write(JSON.stringify({
  letter: key({}), space: key({ key: " " }), slash: key({ key: "/" }), at: key({ key: "@" }),
  enter: key({ key: "Enter" }), escape: key({ key: "Escape" }), ctrl: key({ ctrlKey: true }),
  meta: key({ metaKey: true }), alt: key({ altKey: true }), click: key({ type: "click" }), page: key({ target: page }),
}));
"""
    )
    assert out == {"letter": True, "space": True, "slash": False, "at": False, "enter": False, "escape": False,
                   "ctrl": False, "meta": False, "alt": False, "click": False, "page": False}


def _look(companion_x: float, faded: bool = False, caret: bool = True) -> dict:
    return _run(
        r"""
const NMB_TYPING_REACH = 300;
const NMB_TYPING_REACH_RIGHT = 440;
const calls = [];
const buddy = { classList: { contains: (c) => c === "nmb-dodge" && %s } };
globalThis.document = { getElementById: () => buddy };
const nmb = { x: %s, y: 400, pose: "stand", legs: "", anim: null };
const nameMarkBuddyShape = (x, y) => [{ left: x, right: x + 60, top: y, bottom: y + 90 }];
const nameMarkBuddyAttention = () => (%s ? [{ left: 100, right: 140, top: 380, bottom: 410 }] : []);
const nameMarkBuddyDodge = () => calls.push("look");
"""
        % (json.dumps(faded), companion_x, json.dumps(caret))
        + _fn(AVATARS, "nameMarkBuddyTypingFar")
        + _fn(AVATARS, "nameMarkBuddyDodgeTyping")
        + r"""
nameMarkBuddyDodgeTyping();
process.stdout.write(JSON.stringify({ looked: calls.length }));
"""
    )


@needs_node
def test_a_typing_look_is_made_only_near_the_caret_or_while_faded() -> None:
    assert _look(900)["looked"] == 0  # 760px right of the caret: no layout scan
    assert _look(-200)["looked"] == 0  # left of the caret's box: lists hang rightwards
    assert _look(300)["looked"] == 1  # inside the reach
    assert _look(900, faded=True)["looked"] == 1  # faded: fades back once clear
    assert _look(900, caret=False)["looked"] == 0  # nothing to hang a list from


def test_the_dodge_listener_uses_the_typing_look_for_typing_keys() -> None:
    src = AVATARS[AVATARS.index("for (const type of [\"click\", \"keyup\"])") :][:900]
    assert "nameMarkBuddyTypingKey(e) ? nameMarkBuddyDodgeTyping : nameMarkBuddyDodge" in src
    assert "setTimeout(look, 80)" in src and "setTimeout(look, 700)" in src
