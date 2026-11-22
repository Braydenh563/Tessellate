"""Brief 101b: Stop ends a run before its next write, not only between steps.

The agent loop is a synchronous generator in a worker thread; Stop could only
land when the generator next yielded. A step whose model call was already on
its way back when Stop was pressed still ran its write (OPEN.md, agent87).
The run's budget now carries the stop signal, and a write tool is refused
once it is set.
"""

from __future__ import annotations

import threading

from tessellate.ai import budget
from tessellate.core import activity, deps
from tessellate.core.database import Entry
from tests._skill_run import run_for_test
from tests.fakes import FakeOllama

WRITER = {
    "name": "Write two notes",
    "prompt": "Write two notes.",
    "steps": [
        {"text": "Write the first note.", "expects": "tool_called", "tools": ["create_note"]},
        {"text": "Write the second note.", "expects": "tool_called", "tools": ["create_note"]},
    ],
    "tools": ["create_note"],
}


class StopsDuringTheCall(FakeOllama):
    """Stop is pressed while the first model call is in flight."""

    def __init__(self, stop: threading.Event) -> None:
        super().__init__(running=True)
        self.stop = stop

    def chat_tools(self, model, messages, tools, *a, **k):  # noqa: ANN001, ANN002, ANN003
        reply = super().chat_tools(model, messages, tools, *a, **k)
        self.stop.set()
        return reply


def _texts() -> list[str]:
    with deps.get_db().session() as session:
        return [e.content for e in session.query(Entry).all()]


def test_a_write_the_model_asked_for_during_stop_does_not_run(app_state, fake_embeddings):
    deps.get_config().set_preference("skills", [WRITER])
    stop = threading.Event()
    fake = StopsDuringTheCall(stop)
    fake.tool_script = [[{"name": "create_note", "arguments": {"content": "written after stop"}}], []] * 2
    deps.override_ai(ollama=fake)
    run = run_for_test(fake, skill="write_two_notes", budget={"tokens": 0, "stop_event": stop})
    assert "written after stop" not in _texts(), "the write ran after Stop"
    assert run.stopped_by == "budget"
    assert "Stop" in run.verification.reason


def test_without_stop_the_same_run_writes(app_state, fake_embeddings):
    deps.get_config().set_preference("skills", [WRITER])
    fake = FakeOllama(running=True)
    fake.tool_script = [[{"name": "create_note", "arguments": {"content": "written normally"}}], []] * 2
    deps.override_ai(ollama=fake)
    run_for_test(fake, skill="write_two_notes", budget={"tokens": 0, "stop_event": threading.Event()})
    assert "written normally" in _texts()


def test_the_budget_says_so_once_the_signal_is_set():
    stop = threading.Event()
    spend = budget.RunBudget(tokens=0, stop_event=stop)
    assert spend.exceeded() == "" and not spend.stop_requested()
    stop.set()
    assert spend.stop_requested()
    assert "Stop" in spend.exceeded()


def test_a_job_can_share_the_runs_signal():
    stop = threading.Event()
    with activity.track("generation", "Running a skill", stop_event=stop) as job:
        assert not job.stopped
        job.request_stop()
        assert stop.is_set() and job.stopped


def test_a_read_the_model_asked_for_during_stop_does_not_run_either(app_state, fake_embeddings, monkeypatch):
    """L66: Stop covers a read-only call too, so a long read is not started after it."""
    from tessellate.ai import tools

    reader = {**WRITER, "name": "Read twice", "tools": ["search_notes"], "steps": [
        {"text": "Search once.", "expects": "tool_called", "tools": ["search_notes"]},
    ]}
    deps.get_config().set_preference("skills", [reader])
    stop = threading.Event()
    fake = StopsDuringTheCall(stop)
    fake.tool_script = [[{"name": "search_notes", "arguments": {"query": "anything"}}], []] * 2
    deps.override_ai(ollama=fake)
    ran: list[str] = []
    real = tools.execute_tool

    def spy(session, name, arguments, **kw):  # noqa: ANN001, ANN003
        ran.append(name)
        return real(session, name, arguments, **kw)

    monkeypatch.setattr(tools, "execute_tool", spy)
    run_for_test(fake, skill="read_twice", budget={"tokens": 0, "stop_event": stop})
    assert "search_notes" not in ran, "a read started after Stop"
