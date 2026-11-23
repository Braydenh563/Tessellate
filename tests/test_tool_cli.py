"""`python -m tessellate tool NAME --json` runs one offered tool from a shell.

The same list and the same gates as the stdio MCP server (`offered_tools`):
a destructive tool, or one turned off in Settings, is not runnable here
(L-general-8). The cli takes its output stream so no process is spawned.
"""

from __future__ import annotations

import io
import json

from tessellate import mcp_server
from tessellate.core import deps


def _run(argv):
    out = io.StringIO()
    code = mcp_server.cli(argv, out)
    return code, json.loads(out.getvalue())


def test_no_name_lists_the_offered_tools(app_state):
    code, body = _run(["--json"])
    assert code == 0
    names = {t["name"] for t in body["tools"]}
    assert names == {spec.name for spec in mcp_server.offered_tools()}
    assert all("description" in t and "inputSchema" in t for t in body["tools"])


def test_a_tool_runs_and_prints_its_result_as_json(app_state):
    code, body = _run(["count_notes", "--json"])
    assert code == 0
    assert body["tool"] == "count_notes" and "error" not in body["result"]


def test_arguments_are_a_json_object(app_state):
    code, body = _run(["count_notes", "--args", "[1]", "--json"])
    assert code == 2 and "object" in body["error"]
    code, body = _run(["count_notes", "--args", "{nope", "--json"])
    assert code == 2


def test_an_unknown_or_turned_off_tool_is_refused(app_state):
    code, body = _run(["delete_note", "--json"])
    assert code == 1 and "unavailable" in body["error"]
    deps.get_config().set_preference("disabled_tools", ["count_notes"])
    code, body = _run(["count_notes", "--json"])
    assert code == 1


def test_main_routes_the_tool_word_before_argparse():
    import inspect

    from tessellate import __main__

    assert 'sys.argv[1:2] == ["tool"]' in inspect.getsource(__main__.main)
