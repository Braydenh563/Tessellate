"""WORLD_CLASS_PLAN decision 61 (L-world-class-124): the two long runners are
`Step` state machines with one function per state, so a stage runs alone.

Each test builds a context by hand and drives one state function, the thing
the old single loop made impossible.
"""

from __future__ import annotations

from types import SimpleNamespace

from tessellate.ai import agent, skill_runner
from tessellate.ai.steps import drive


def _run(gen):
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        return events, stop.value


def test_drive_runs_states_until_the_end_and_returns_the_result():
    from enum import Enum

    class S(Enum):
        A = 1
        B = 2
        END = 3

    def a(ctx):
        yield {"type": "a"}
        return S.B

    def b(ctx):
        ctx.result = "kept"
        yield {"type": "b"}
        return S.END

    ctx = SimpleNamespace()
    events, value = _run(drive({S.A: a, S.B: b}, S.A, S.END, ctx))
    assert [e["type"] for e in events] == ["a", "b"]
    assert value == "kept"


def test_every_agent_state_but_done_has_a_function():
    assert set(agent._TURN_STEPS) == set(agent.Step) - {agent.Step.DONE}
    assert set(skill_runner._ATTEMPT_STEPS) == set(skill_runner.Step) - {skill_runner.Step.DONE}


def _turn(**loop):
    return agent._Turn(
        session=None, ollama=None, plan=SimpleNamespace(), state=SimpleNamespace(progressed=True, messages=[]),
        loop=agent._Loop(**{"allowance": 3, "ceiling": 6, **loop}), spend=None,
        card=SimpleNamespace(start_round=lambda called: iter([{"type": "step", "called": called}])),
        question="q", mode=None, history=None, show_plan=True, exhausted_note=None,
    )


def test_a_spent_allowance_goes_to_exhaust_without_opening_a_round():
    turn = _turn(round_number=1, allowance=2)
    events, nxt = _run(agent._step_round(turn))
    assert (events, nxt) == ([], agent.Step.EXHAUST)
    assert turn.loop.round_number == 1


def test_a_round_opens_counts_and_resets_progress():
    turn = _turn()
    events, nxt = _run(agent._step_round(turn))
    assert nxt is agent.Step.STREAM
    assert turn.loop.round_number == 0
    assert turn.state.progressed is False
    assert events == [{"type": "step", "called": False}]


def test_a_round_that_got_somewhere_earns_another_up_to_the_ceiling(monkeypatch):
    def dispatch(*_args):
        yield from ()
        return False

    monkeypatch.setattr(agent, "_dispatch_round", dispatch)
    monkeypatch.setattr(agent, "_widen_focus", lambda *a: None)
    monkeypatch.setattr(agent, "_prefetch_outbound", lambda calls: None)
    monkeypatch.setattr(agent, "_replay_message", lambda reply: {"role": "assistant"})
    for allowance, ceiling, after in ((3, 6, 4), (6, 6, 6)):
        turn = _turn(allowance=allowance, ceiling=ceiling)
        turn.state.outside = False
        turn.reply = {"tool_calls": [{"function": {"name": "search"}}]}
        turn.state.progressed = True
        _events, nxt = _run(agent._step_dispatch(turn))
        assert nxt is agent.Step.ROUND
        assert turn.loop.allowance == after
        assert turn.loop.called_any is True


def _attempt(outcome):
    return skill_runner._Attempt(setup=None, run=None, index=0, st=SimpleNamespace(outcome=outcome))


def test_an_attempt_with_an_outcome_settles_without_a_turn():
    events, nxt = _run(skill_runner._attempt_open(_attempt("done")))
    assert (events, nxt) == ([], skill_runner.Step.SETTLE)


def test_an_abort_stops_the_run():
    at = _attempt("abort")
    _events, nxt = _run(skill_runner._attempt_settle(at))
    assert (nxt, at.result) == (skill_runner.Step.DONE, "stop")


def test_a_turn_that_never_opened_settles(monkeypatch):
    def opened(*_args):
        yield {"type": "thinking", "delta": ""}
        return None

    monkeypatch.setattr(skill_runner, "_open_turn", opened)
    events, nxt = _run(skill_runner._attempt_open(_attempt(None)))
    assert nxt is skill_runner.Step.SETTLE
    assert len(events) == 1
