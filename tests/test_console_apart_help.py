"""LEDGER L752 (owner decided 2026-11-12): the Console keeps its own worker,
and the panel help and the Guide say it runs apart from the page."""
from pathlib import Path
from tessellate.ai.help_topics_more import TOPIC_META as T


def test_panel_help_says_console_runs_apart():
    src = (Path(__file__).parent.parent / "frontend/js/documents-code.js").read_text(encoding="utf-8")
    assert "in its own worker apart from any page the file shows" in src


def test_guide_says_console_runs_apart():
    steps = " ".join(T["code-run"]["steps"])
    assert "apart from any page the file shows" in steps
