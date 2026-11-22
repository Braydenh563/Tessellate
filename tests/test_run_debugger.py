"""The Python debugger (DOCUMENTS_PLAN 23, D2; Brief 70), driven in CPython.

`_mm_debug` is the same text the sandbox's Pyodide worker runs: here its
`exchange` (in the worker, a post and an `Atomics.wait` on the shared
buffer) is a script of the panel's actions, so a session's stops, steps,
watches, conditions and the exception stop are checked without a browser.
The browser half is measured by `scratchpad/ui-sweeps/code-debug.js`.
"""

from __future__ import annotations

import json
import sys

from tessellate.api import run_sandbox

PROGRAM = """def double(n):
    m = n * 2
    return m

total = 0
for i in range(3):
    total += double(i)
print(total)
"""


def _session(code, actions, *, breaks=(), watches=(), stdin=""):
    space: dict = {}
    exec(run_sandbox.PY_RUNNER, space)  # noqa: S102  # the runner is this repo's own text
    stops: list[dict] = []
    rows: list[tuple] = []
    script = list(actions)

    def exchange(message):
        stops.append(json.loads(message))
        return json.dumps(script.pop(0)) if script else json.dumps({"cmd": "stop"})

    trace = sys.gettrace()
    try:
        ended = space["_mm_debug"](
            code, lambda *row: rows.append(row), exchange, 0, stdin, json.dumps(list(breaks)), json.dumps(list(watches))
        )
    finally:
        sys.settrace(trace)
    return ended, stops, rows


def test_a_breakpoint_stops_and_steps_go_line_by_line():
    ended, stops, rows = _session(
        PROGRAM,
        [{"cmd": "over"}, {"cmd": "over"}, {"cmd": "in"}] + [{"cmd": "continue"}] * 3,
        breaks=[{"line": 6}],
    )
    assert ended == "done"
    lines = [s["line"] for s in stops if s["t"] == "stop"]
    #: Stop at 6, over to 7, over (the call runs whole) back to 6, into the
    #: loop body on 7; then continue hits the breakpoint at 6 again, and so on.
    assert lines[:4] == [6, 7, 6, 7]
    assert stops[0]["reason"] == "breakpoint"
    assert rows[-1][1] == "6"


def test_step_in_enters_a_function_and_step_out_leaves_it():
    _ended, stops, _rows = _session(PROGRAM, [{"cmd": "in"}, {"cmd": "in"}, {"cmd": "out"}], breaks=[{"line": 7}])
    seen = [(s["line"], s["stack"][0]["name"], len(s["stack"])) for s in stops]
    assert seen[0] == (7, "module", 1)
    assert seen[1] == (2, "double", 2)
    assert seen[2] == (3, "double", 2)
    assert seen[3][1] == "module"


def test_locals_globals_and_watches_are_the_stopped_frames():
    _ended, stops, _rows = _session(PROGRAM, [{"cmd": "stop"}], breaks=[{"line": 3}], watches=["m + 1", "nope"])
    stop = stops[0]
    assert {"name": "n", "value": "0", "type": "int"} in stop["locals"]
    assert any(row["name"] == "total" for row in stop["globals"])
    assert stop["watches"][0] == {"expr": "m + 1", "value": "1"}
    assert stop["watches"][1]["error"].startswith("NameError")


def test_a_condition_is_evaluated_where_the_breakpoint_is():
    _ended, stops, _rows = _session(PROGRAM, [{"cmd": "continue"}], breaks=[{"line": 2, "cond": "n == 2"}])
    assert [s["locals"] for s in stops][0][0] == {"name": "n", "value": "2", "type": "int"}
    assert len(stops) == 1


def test_eval_answers_with_a_fresh_stop_and_new_watches():
    _ended, stops, _rows = _session(PROGRAM, [{"cmd": "eval", "watches": ["n * 10"]}, {"cmd": "stop"}], breaks=[{"line": 3}])
    assert stops[1]["line"] == stops[0]["line"] == 3
    assert stops[1]["watches"] == [{"expr": "n * 10", "value": "0"}]


def test_stop_ends_the_run():
    ended, stops, rows = _session(PROGRAM, [{"cmd": "stop"}], breaks=[{"line": 6}])
    assert ended == "stopped" and len(stops) == 1
    assert not any(row[1] == "3" for row in rows)


def test_an_uncaught_exception_stops_at_the_raise_with_the_traceback():
    code = "def f(x):\n    y = x - 1\n    return 10 / y\n\nf(1)\n"
    ended, stops, rows = _session(code, [{"cmd": "eval", "watches": ["y"]}, {"cmd": "continue"}])
    assert ended == "error"
    stop = stops[0]
    assert stop["reason"] == "exception" and stop["line"] == 3
    assert stop["text"] == (
        "Traceback (most recent call last):\n  line 5, in module\n    f(1)\n"
        "  line 3, in f\n    return 10 / y\nZeroDivisionError: division by zero"
    )
    assert [row["name"] for row in stop["stack"]] == ["f", "module"]
    assert {"name": "y", "value": "0", "type": "int"} in stop["locals"]
    assert stops[1]["watches"] == [{"expr": "y", "value": "0"}]
    assert rows[-1][0] == "error" and rows[-1][2] == 3


def test_no_breakpoints_runs_to_the_end_without_a_stop():
    ended, stops, rows = _session(PROGRAM, [])
    assert ended == "done" and stops == []
    assert rows == [("log", "6", 8, False)]


def test_input_asks_the_panel_mid_run_once_the_box_is_used_up():
    code = "a = input('A? ')\nb = input('B? ')\nprint(a + b)\n"
    _ended, stops, rows = _session(code, [{"line": "two"}], stdin="one\n")
    assert stops == [{"t": "input", "prompt": "B? "}]
    assert [row[1] for row in rows] == ["A? one", "B? two", "onetwo"]


def test_a_plain_run_asks_too_when_it_can_wait():
    space: dict = {}
    exec(run_sandbox.PY_RUNNER, space)  # noqa: S102
    rows: list[tuple] = []
    space["_mm_run"]("print(input('Name? '))\n", lambda *row: rows.append(row), 0, "", lambda prompt: "Ada")
    assert [row[1] for row in rows] == ["Name? Ada", "Ada"]
    #: Without a way to wait, the old answer stands.
    rows.clear()
    space["_mm_run"]("input('x')\n", lambda *row: rows.append(row), 0, "")
    assert "Input box" in rows[-1][1]


TESTS = """import unittest


class MathTest(unittest.TestCase):
    def test_adds(self):
        total = 1 + 1
        self.assertEqual(total, 2)

    def test_fails(self):
        self.assertEqual(3, 4)


def test_plain():
    value = 5
    assert value == 5
"""


def _test_session(actions, breaks):
    space: dict = {}
    exec(run_sandbox.PY_RUNNER, space)  # noqa: S102  # the runner is this repo's own text
    stops: list[dict] = []
    tests: list[tuple] = []
    script = list(actions)

    def exchange(message):
        stops.append(json.loads(message))
        return json.dumps(script.pop(0)) if script else json.dumps({"cmd": "stop"})

    trace = sys.gettrace()
    try:
        ended = space["_mm_debug"](TESTS, lambda *row: None, exchange, 0, "", json.dumps(breaks), "[]", lambda *row: tests.append(row))
    finally:
        sys.settrace(trace)
    return ended, stops, tests, space["_MM_DEBUG_TESTS"][0]


def test_debug_on_a_file_of_tests_runs_them_and_stops_in_one():
    """OPEN row 563: a breakpoint in a test stops there, every test reports, the totals come back."""
    ended, stops, tests, totals = _test_session([{"cmd": "continue"}, {"cmd": "continue"}], [{"line": 7}, {"line": 15}])
    assert ended == "done"
    assert [s["line"] for s in stops if s["t"] == "stop"] == [7, 15]
    assert {"name": "total", "value": "2", "type": "int"} in stops[0]["locals"]
    assert [(name, state) for name, state, *_ in tests] == [("MathTest.test_adds", "pass"), ("MathTest.test_fails", "fail"), ("test_plain", "pass")]
    assert totals == {"passed": 2, "failed": 1, "skipped": 0}


def test_stop_in_a_test_runs_no_more_tests():
    ended, _stops, tests, _totals = _test_session([{"cmd": "stop"}], [{"line": 7}])
    assert ended == "stopped"
    assert tests == []


def test_debug_sends_tests_for_a_python_file_of_tests():
    from pathlib import Path

    core = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "run-core.js").read_text("utf-8")
    assert 'tests: runLooksLikeTests("py", String(request.source || ""))' in core
    assert "e.data.tests ? emitTest : null" in run_sandbox._PY_WORKER


def test_a_variable_opens_into_children_of_children_and_stops_at_a_cycle():
    """L312: Variables opened one level; a nested list or dict opens down to three, a cycle ends the walk."""
    code = "data = {'a': [1, {'b': 2}], 'c': 3}\nloop = [1]\nloop.append(loop)\nx = 1\n"
    _ended, stops, _rows = _session(code, [{"cmd": "stop"}], breaks=[{"line": 4}], watches=["data['a']"])
    by = {row["name"]: row for row in stops[0]["locals"]}
    a = next(c for c in by["data"]["children"] if c["name"] == "'a'")
    assert [c["name"] for c in a["children"]] == ["[0]", "[1]"]
    assert a["children"][1]["children"] == [{"name": "'b'", "value": "2", "type": "int"}]
    loop = by["loop"]["children"]
    assert loop[1]["value"] == "[1, [...]]" and "children" not in loop[1]
    assert [c["name"] for c in stops[0]["watches"][0]["children"]] == ["[0]", "[1]"]
