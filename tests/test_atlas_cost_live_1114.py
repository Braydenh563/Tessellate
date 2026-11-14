"""What the Atlas companion costs when it changes, in a real browser (ledger L232, L233, L238).

Median of three runs at 4x CPU, headless Chromium 153, 2026-11-14 (loaded four-core container), the dashboard with the
feminine Atlas:

- a class change on `#nm-buddy` restyles 113 to 166 elements (the row quoted 1,244 before the band moved under html,
  36ecedeb1), 9 ms at 1x and 35 to 74 ms at 4x;
- a mood change is 3 to 5 style recalcs and 3 to 4 layouts, 34 to 70 ms at 1x and 65 to 149 ms at 4x;
- a click on the face: `pointerup` handler 0.1 to 3.1 ms and `click` 0.6 to 7.6 ms. The 190 to 270 ms Event Timing figure
  is the wait for the frame behind it (the idle loops, L138), not the handler.

The budgets sit above those with room for a loaded CI box. Skipped without node and a Playwright browser.
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
def cost(tmp_path_factory: pytest.TempPathFactory) -> dict:
    data = tmp_path_factory.mktemp("atlas-cost-data")
    port = _free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TESSELLATE_NO_AUTO_INSTALL": "1", "TESSELLATE_DATA_DIR": str(data)}
    log = (data / "server.log").open("w")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "tessellate.api.app:create_app", "--factory", "--port", str(port)], env=env, stdout=log, stderr=log, cwd=ROOT)
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
        run = subprocess.run(["node", str(ROOT / "tests" / "_atlas_cost_live.js")], capture_output=True, text=True, env=node_env, timeout=240)
        if "Executable doesn't exist" in run.stderr or "Cannot find module" in run.stderr:
            pytest.skip("needs playwright and its browser")
        assert run.returncode == 0, run.stderr[-2000:]
        return json.loads(run.stdout.strip().splitlines()[-1])
    finally:
        server.terminate()
        server.wait(timeout=20)


def test_a_class_change_on_the_buddy_restyles_a_few_hundred_elements_not_1244(cost: dict) -> None:
    """L233: 113 to 166 measured; the row's 1,244 is gone."""
    assert 0 < cost["elems"] <= 400, cost


def test_a_mood_change_is_a_handful_of_restyles(cost: dict) -> None:
    """L232: 3 to 5 recalcs and 3 to 4 layouts a mood change, never one per part."""
    assert 0 < cost["moodStyles"] <= 10 and cost["moodLayouts"] <= 10, cost


def test_a_click_on_the_face_runs_its_handlers_in_under_30ms_at_4x(cost: dict) -> None:
    """L238: the handlers are 0.1 to 7.6 ms; the 200 ms Event Timing is the frame behind them."""
    assert cost["pointerupMs"] <= 30 and cost["clickMs"] <= 30, cost
