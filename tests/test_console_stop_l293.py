"""L293: a console line killed at its ten seconds says so in the console and keeps what the page holds.

A JavaScript loop cannot be interrupted inside its worker, so the worker goes and the names the last
run left go with it. Everything the page itself holds stays: the console's printed rows (a stopped run
drops only later messages), Problems (the editor's diagnostics) and the debug variables. The console
now says that plainly, as the Python interrupt already did, instead of only the status line.
"""

from __future__ import annotations

from tests.test_code_documents import JS, _fn, _node


def _overtime(lang: str, interrupted: int = 0):
    code = (JS / "documents-code.js").read_text(encoding="utf-8")
    prelude = (
        "const DOC_RUN_TIMEOUT_MS = 10000; const DOC_CONSOLE_INTERRUPT_MS = 3000;\n"
        "const out = { rows: [], stops: [], sent: [], cleared: 0 };\n"
        "const log = { replaceChildren() { out.cleared += 1; } };\n"
        f"const docRun = {{ evalId: 4, interrupted: {interrupted}, consoleLog: log, id: 2, timer: 0 }};\n"
        "const docRunStop = (why) => out.stops.push(why);\n"
        "const docRunRow = (level, text, line, into) => out.rows.push({ level, text, into: into === log });\n"
        "const docRunSend = (m) => out.sent.push(m.type);\n"
        "const setTimeout = () => 1;\n"
        + _fn(code, "docConsoleOvertime")
    )
    return _node(prelude, f'(() => {{ docConsoleOvertime(4, "{lang}"); return out; }})()')


def test_a_stopped_js_line_says_ten_seconds_and_what_is_kept_and_lost():
    got = _overtime("js")
    assert got["stops"] == ["Stopped after 10 seconds: the line was still running."]
    assert got["cleared"] == 0
    (row,) = got["rows"]
    assert row["into"] and row["level"] == "info"
    assert "Stopped after 10 seconds" in row["text"]
    assert "output above is kept" in row["text"] and "Problems" in row["text"]
    assert "Run the file again" in row["text"]


def test_a_python_line_is_interrupted_first_and_says_nothing_yet():
    got = _overtime("python")
    assert got["sent"] == ["interrupt"] and got["stops"] == [] and got["rows"] == []


def test_a_python_line_that_would_not_answer_is_stopped_with_the_same_words():
    got = _overtime("python", interrupted=4)
    assert got["stops"] == ["Stopped after 10 seconds: the line was still running."]
    assert "Stopped after 10 seconds" in got["rows"][0]["text"]
