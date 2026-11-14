"""I9 (WORLD_CLASS_PLAN): every invention's own surface carries a small
"Learned: manage" link into Settings, What it learned, so a wrong fact is
fixed where it is met. One helper builds the link; the surfaces call it."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def test_the_helper_opens_the_existing_learned_pane_filtered_to_a_kind():
    body = _read("settings.js")
    start = body.index("openSettingsModal.learnedLink = function")
    helper = body[start : start + 1200]
    assert 'openSettingsModal("learned")' in helper
    assert '$("learned-kind")' in helper
    assert "Learned: manage" in helper


def test_every_invention_surface_carries_the_link():
    assert 'openSettingsModal.learnedLink("")' in _read("dash-night.js"), "morning card"
    assert 'openSettingsModal.learnedLink("question")' in _read("dash-night.js"), "open questions line"
    assert "openSettingsModal.learnedLink(" in _read("margin-reader.js"), "margin card"
    assert "openSettingsModal.learnedLink(" in _read("questions-view.js"), "question list"
    assert "openSettingsModal.learnedLink(" in _read("dashboard.js"), "resurfacing card"


def test_the_help_names_the_link():
    from tessellate.ai import help_chat

    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "learned")
    assert "Learned: manage" in topic["body"]
