"""`tessellate tool NAME --json ARGS` (L-general-8): one offered MCP tool run
from a shell script, behind the same token and the same offered list as the
stdio server, its result printed as JSON."""

from __future__ import annotations

import io
import json

from tessellate import mcp_server


def _run(argv, monkeypatch, token=True):
    if token:
        monkeypatch.setenv(mcp_server.TOKEN_ENV, mcp_server.token())
    else:
        monkeypatch.delenv(mcp_server.TOKEN_ENV, raising=False)
    out, err = io.StringIO(), io.StringIO()
    code = mcp_server.run_cli(argv, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_a_named_tool_runs_and_prints_its_result_as_json(app_state, monkeypatch):
    """The result is the tool's own JSON, one document, exit 0."""
    code, out, _ = _run(["count_notes", "--json", "{}"], monkeypatch)
    assert code == 0
    assert isinstance(json.loads(out), dict)


def test_no_name_lists_the_offered_tools(app_state, monkeypatch):
    """Bare `tool` prints the offered list, names and descriptions, nothing destructive."""
    code, out, _ = _run([], monkeypatch)
    listed = json.loads(out)
    assert code == 0
    assert {row["name"] for row in listed} == {spec.name for spec in mcp_server.offered_tools()}
    assert all(row["description"] for row in listed)


def test_a_tool_the_server_does_not_offer_is_refused(app_state, monkeypatch):
    """A destructive or unknown name fails with exit 1 and a reason on stderr."""
    destructive = next(spec.name for spec in mcp_server.tools.TOOLS.values() if spec.destructive)
    for name in (destructive, "no_such_tool"):
        code, out, err = _run([name], monkeypatch)
        assert code == 1 and out == "" and "unavailable" in err


def test_without_the_token_nothing_runs(app_state, monkeypatch):
    """The stdio server's token gate holds here too: any local process is not enough."""
    mcp_server.token()
    code, out, err = _run(["count_notes"], monkeypatch, token=False)
    assert code == 2 and out == "" and mcp_server.TOKEN_ENV in err


def test_arguments_that_are_not_a_json_object_are_refused(app_state, monkeypatch):
    """Bad --json is a usage error, not a traceback."""
    code, out, err = _run(["count_notes", "--json", "[1"], monkeypatch)
    assert code == 2 and out == "" and "JSON object" in err


def test_the_launcher_hands_tool_to_the_cli(monkeypatch):
    """`python -m tessellate tool ...` reaches run_cli before the app's own flags."""
    import pytest

    from tessellate import __main__ as launcher

    seen = {}
    monkeypatch.setattr(mcp_server, "run_cli", lambda argv, **_: seen.setdefault("argv", argv) and 0)
    monkeypatch.setattr(launcher.sys, "argv", ["tessellate", "tool", "count_notes"])
    with pytest.raises(SystemExit):
        launcher.main()
    assert seen["argv"] == ["count_notes"]
