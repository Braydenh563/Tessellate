"""Replay of a board's pen strokes in drawing order, and the GIF export built from it (L-whiteboard-4). The pure parts run
in node; the browser half (the command, the strokes coming back, the GIF file) is `scratchpad/ui-sweeps/wbink3.js`."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests._app_js import frontend_text


def _run(body: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const wbFmtState = {};\n" + frontend_text("whiteboard-ink-replay.js") + "\n" + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_strokes_come_back_oldest_first_and_only_pen_and_marker():
    out = _run(
        "const s = [{id: 9, k: 'draw'}, {id: 2, k: 'highlighter'}, {id: 5, k: 'rect'}, {id: 4, k: 'draw'}];"
        "console.log(JSON.stringify(wbFmtState.inkReplay.order(s, (x) => ({ shape: x.k })).map((x) => x.id)));"
    )
    assert out == [2, 4, 9]


def test_the_frame_plan_ends_on_every_stroke_and_is_capped():
    plan = lambda n: _run(f"console.log(JSON.stringify(wbFmtState.inkReplay.plan({n})));")  # noqa: E731
    assert plan(0) == []
    assert plan(3) == [1, 2, 3]
    big = plan(500)
    assert len(big) == 40 and big[-1] == 500 and big == sorted(set(big))


def test_the_board_wires_replay_and_the_gif_format():
    wb = frontend_text("whiteboard.js")
    assert 'value: "gif"' in wb and "wbFmtState.inkReplay.exportGif(scope)" in wb
    assert "skipSketches?.has(sketch.id)" in wb
    commands = frontend_text("whiteboard-commands.js")
    assert 'id: "replay-ink"' in commands and "wbFmtState.inkReplay.start()" in commands
    entries = frontend_text("lazy-entries.js")
    assert entries.index("/js/whiteboard-ink-replay.js") < entries.index("/js/whiteboard-gif.js")


def test_replay_honours_reduced_motion_and_always_puts_the_strokes_back():
    src = frontend_text("whiteboard-ink-replay.js")
    assert "reducedMotionWanted()" in src
    assert 'el.style.visibility = ""' in src
