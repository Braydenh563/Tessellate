"""`ai.agent` loads on first use, not when the app module is imported (L678)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_app_import_does_not_load_agent():
    code = (
        "import sys, tessellate.api.app;"
        "assert 'tessellate.ai.agent' not in sys.modules;"
        "from tessellate.ai import autonomous, skill_runner;"
        "from tessellate.api import chat_agent;"
        "autonomous.agent.run_agent;"
        "assert 'tessellate.ai.agent' in sys.modules"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""}, cwd=ROOT
    )
    assert r.returncode == 0, r.stderr
