"""The open-work scanner the plan sessions and the closing session clear (the
owner, 2026-11-12: "after these sessions are done, I should only be left with
the backlog and nothing else")."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import open_scan  # noqa: E402


def test_backlog_and_history_are_never_scanned():
    paths = open_scan.files()
    assert "docs/roadmap/BACKLOG.md" not in paths
    assert "docs/roadmap/HISTORY.md" not in paths
    assert "docs/roadmap/LEDGER.md" in paths


def test_the_signals_catch_open_work_and_pass_history():
    for line in ("- [ ] build the thing", "Still open: the screenshot set", "# TODO wire this", "not yet built",
                 "@pytest.mark.xfail(strict=True, reason='spec')", "deferred to a later PR"):
        assert open_scan.SIGNAL.search(line), line
    for line in ("- [x] built 2026-11-01", "The day strip was approved and built.", "def todo_lines(note):"):
        assert not open_scan.SIGNAL.search(line), line


def test_every_plan_session_owns_its_plan_file():
    for plan, owned in open_scan.OWNERS.items():
        assert any(o.startswith("docs/roadmap/") and o.endswith("_PLAN.md") for o in owned), plan
        assert all((ROOT / o).exists() or any(f.startswith(o) for f in open_scan.files()) for o in owned), plan


def test_a_reminders_default_text_is_copy_not_work():
    """The graph plan session, 2026-11-12: four surfaces prefill a reminder
    with "Follow up: <note>"; that string is app copy and never a hit."""
    assert open_scan.COPY.search('textInput.value = `Follow up: ${preview}`;')
    assert not open_scan.COPY.search("follow up on the screenshot set next session")
