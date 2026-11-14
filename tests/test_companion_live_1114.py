"""The companion in a real browser against a real server (ledger L84, L131, L143, L144, L147).

One boot, one pass of `tests/_companion_live.js`, then a test per row on what it measured. Skipped without node and a
Playwright browser. The CPU is slowed 4x for the throw and the click, as the owner's machine is on a bad day; the
budgets sit where the measurements do (three runs on this branch, 2026-11-14: flight median 0.5 to 1.0 ms and p95 1.6
to 5.0 ms at 4x, a mood call 4 to 15 ms median) with room for a loaded CI box.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live(tmp_path_factory: pytest.TempPathFactory):
    data = tmp_path_factory.mktemp("live-data")
    port = _free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TESSELLATE_NO_AUTO_INSTALL": "1", "TESSELLATE_DATA_DIR": str(data)}
    log = (data / "server.log").open("w")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tessellate.api.app:create_app", "--factory", "--port", str(port)],
        env=env, stdout=log, stderr=log, cwd=ROOT,
    )
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.skip("the server did not come up")
        node_env = {**env, "BASE": f"http://127.0.0.1:{port}", "SWEEPS": str(ROOT / "scratchpad" / "ui-sweeps"), "SCRATCH": str(data)}
        node_env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        node_env["NODE_PATH"] = os.pathsep.join(filter(None, [node_env.get("NODE_PATH", ""), "/opt/node22/lib/node_modules"]))
        run = subprocess.run(["node", str(ROOT / "tests" / "_companion_live.js")], capture_output=True, text=True, env=node_env, timeout=240)
        if "Executable doesn't exist" in run.stderr or "Cannot find module" in run.stderr:
            pytest.skip("needs playwright and its browser")
        assert run.returncode == 0, run.stderr[-2000:]
        result = json.loads(run.stdout.strip().splitlines()[-1])
        calm = subprocess.run(["node", str(ROOT / "tests" / "_companion_calm.js")], capture_output=True, text=True, env=node_env, timeout=120)
        assert calm.returncode == 0, calm.stderr[-2000:]
        result["calm"] = json.loads(calm.stdout.strip().splitlines()[-1])
        return result
    finally:
        server.terminate()
        server.wait(timeout=20)


def test_a_throw_by_mouse_touch_or_keyboard_scrolls_nothing(live: dict) -> None:
    """L84. Scrolled 150px in, every scroller reads the same after a mouse throw, a touch throw and the arrows, page keys and space on the figure."""
    before = live["scrollBefore"]
    assert any(v >= 100 for v in before.values()), "something was scrolled to be kept"
    for how in ("scrollMouse", "scrollTouch", "scrollKeys"):
        assert live[how] == before, how


def test_the_throws_frame_step_reads_no_layout_and_costs_under_4ms_at_4x(live: dict) -> None:
    """L143. The flight's frame callback at 4x CPU: median under 4 ms, and the page is read only in a landing frame (its three rects in one pass), never in a step."""
    flight = live["flight"]
    assert flight["rate"] == 4 and flight["frames"] > 20
    assert flight["medianMs"] < 4
    landing_reads = sum(reads for _frame, _ms, reads in live["slow"])
    assert flight["reads"] <= landing_reads, "every read was in a landing frame, none in a step"
    for _frame, _ms, reads in live["slow"]:
        assert reads <= 3


def test_the_follow_loop_looks_seldom_when_still_and_once_a_frame_when_woken(live: dict) -> None:
    """L144. Perched and still for 6 s: the loop naps (8 looks a second of an idle page was the owner's log); each look reads the panel's box once. Woken by a resize: a look a frame for about a second and a half, and no more than one forced layout a look."""
    assert live["glued"] and live["follow"]["perched"]
    assert live["follow"]["looks"] <= 12 and live["follow"]["readsPerLook"] <= 1.5
    awake = live["followAwake"]
    assert 1 <= awake["looks"] <= 14 and awake["readsPerLook"] <= 2
    forced = sum(n for key, n in live["followForced"].items() if key.startswith("Layout nameMarkBuddyFollow"))
    assert forced <= awake["looks"], "at most one forced layout a look"


def test_a_click_in_the_large_view_costs_setatlasmood_under_22ms_at_4x(live: dict) -> None:
    """L131, L147. The row measured 22 to 44 ms in the call; its blend now waits for a clean frame."""
    click = live["click"]
    assert click["calls"] >= 2 and click["rate"] == 4
    assert click["medianMs"] < 22


def test_under_the_system_reduce_hint_the_calm_loops_run_and_cost_next_to_nothing(live: dict) -> None:
    """L741. The owner: let the gentle sway and glow loops run again under the system's hint (the hop, the giggle and the rig stay stopped). Measured on this branch, an idle Atlas under the hint, one 25 s window each: 253 restyles a minute with every loop stopped, 270 with the calm ones, 1,485 with all of them (`Companion movement: always`); the budget is 400, the stopped count plus a margin.
    """
    calm = live["calm"]
    assert calm["motion"] == "reduced" and calm["calm"] == "on"
    assert calm["body"].startswith("atl-idle-sway"), "the body sways"
    assert calm["breath"].startswith("atl-breathe"), "the breath loop is declared"
    assert calm["anims"] >= 3, "the sway, breath and glow loops exist (the app's own rest rule may hold them)"
    assert calm["mood"] not in ("delighted", "laughing"), "a mood loop would make the count meaningless"
    assert calm["recalcPerMin"] < 400
