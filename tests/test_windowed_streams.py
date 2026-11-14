"""The packaged, windowed build has no console, so `sys.stdout` and
`sys.stderr` are None; uvicorn's log formatter calls `sys.stderr.isatty()`
and the app died before binding a port ("Unable to configure formatter
'default'", INBOX 251). `_ensure_std_streams` gives both a real stream first,
and both entry points call it before anything else can write."""

import ast
import sys
from pathlib import Path

import pytest

import tessellate.__main__ as entry

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")


#: pytest re-installs its own capture streams at the start of every test
#: phase, so the streams are set to None inside the test body, never from a
#: fixture: a fixture's None was swapped back before the body ran and the
#: guard saw a real stream.
@pytest.fixture
def no_console(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    return tmp_path


def _without_console(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)


def test_streams_are_real_files_afterwards(no_console, monkeypatch):
    _without_console(monkeypatch)
    entry._ensure_std_streams()
    out, err = sys.stdout, sys.stderr
    assert out is not None and err is not None and err.isatty() is False
    print("a line that must not raise")
    out.flush()
    assert Path(out.name).name == "desktop-stdio.log"
    assert "a line that must not raise" in Path(out.name).read_text(encoding="utf-8")


def test_real_streams_are_left_alone():
    before = (sys.stdout, sys.stderr)
    entry._ensure_std_streams()
    assert (sys.stdout, sys.stderr) == before


def test_uvicorns_formatter_can_be_built_without_a_console(no_console, monkeypatch):
    _without_console(monkeypatch)
    entry._ensure_std_streams()
    from uvicorn.logging import DefaultFormatter

    DefaultFormatter(fmt="%(levelprefix)s %(message)s")


def test_both_entry_points_call_it_first():
    """Read as a syntax tree rather than as lines of text.

    The contract is "no statement runs before this one", and the line-based
    version could only check "no *line* comes before it", which is not the
    same claim: it failed the day `_run_server` grew a docstring explaining
    why its imports sit inside functions, although nothing had moved. Walking the
    function's own body is the stricter reading as well as the more robust
    one, since a docstring is not a statement and a blank line is not the end
    of a function.
    """
    tree = ast.parse(SOURCE)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    for name in ("main", "_run_server"):
        body = functions[name].body
        #: Skip the docstring, which is an expression rather than anything
        #: that can write to a stream.
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        first = body[0]
        called = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Call)
            and getattr(first.value.func, "id", None) == "_ensure_std_streams"
        )
        assert called, (
            f"{name}() must call _ensure_std_streams() before anything else, "
            f"not {ast.dump(first)[:80]}"
        )
