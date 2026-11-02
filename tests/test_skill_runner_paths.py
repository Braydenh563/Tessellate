"""The exits of `skill_runner._run_skill` that nothing else reached (cc-1101).

Characterisation tests written before the function was split into named
stages: they pin what a run yields when the model cannot call tools, whether
the skill has steps or not, so the split cannot move an event.
"""

from __future__ import annotations

from tessellate.ai import agent
from tessellate.ai.skill_runner import run_skill
from tessellate.core import deps


def _run(monkeypatch, skill: dict, turn_events: list[dict]) -> list[dict]:
    monkeypatch.setattr(agent, "run_agent", lambda *a, **k: iter(turn_events))
    with deps.get_db().session() as session:
        return list(
            run_skill(session, skill, {}, [], deps.get_model_manager(), None, small_model=False)
        )


def _types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


def test_a_stepless_skill_whose_turn_says_nothing_yields_only_its_plan(app_state, monkeypatch):
    events = _run(monkeypatch, {"name": "Quiet", "instruction": "Say hi"}, [])
    assert _types(events) == ["plan"]
    assert events[0]["steps"] == [] and events[0]["skill"] == "Quiet"


def test_a_stepless_skill_on_a_model_without_tools_yields_unsupported_alone(app_state, monkeypatch):
    unsupported = {"type": "unsupported", "message": "no tools"}
    events = _run(monkeypatch, {"name": "Quiet", "instruction": "Say hi"}, [unsupported])
    assert events == [unsupported]


def test_a_stepped_skill_on_a_model_without_tools_yields_unsupported_then_a_closed_run(
    app_state, monkeypatch
):
    unsupported = {"type": "unsupported", "message": "no tools"}
    skill = {"name": "Two", "steps": ["Look at the notes", "Say what you saw"]}
    events = _run(monkeypatch, skill, [unsupported])
    assert _types(events) == ["unsupported", "plan", "verification", "result"]
    result = events[-1]
    assert result["stopped_by"] == "" and result["stopped_at"] is None
    assert result["steps"] == 2 and result["changes"] == [] and result["paused"] is False
