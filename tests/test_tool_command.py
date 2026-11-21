"""L-general-8: `tessellate tool NAME --json ARGS` runs one offered tool from
a shell, behind the same token as the MCP server, and Settings hands an agent
a SKILL.md that routes a request to the right tool."""

from __future__ import annotations

import io
import json

from tessellate import mcp_server


def _run(monkeypatch, *argv, token=True):
    if token:
        monkeypatch.setenv(mcp_server.TOKEN_ENV, mcp_server.token())
    else:
        monkeypatch.delenv(mcp_server.TOKEN_ENV, raising=False)
    out = io.StringIO()
    code = mcp_server.run_tool_command(list(argv), stdout=out)
    return code, out.getvalue()


def test_a_tool_runs_and_prints_its_json(app_state, monkeypatch):
    code, text = _run(monkeypatch, "count_notes", "--json", "{}")
    assert code == 0
    assert isinstance(json.loads(text), dict)


def test_list_names_only_the_offered_tools(app_state, monkeypatch):
    code, text = _run(monkeypatch, "--list")
    names = {json.loads(line)["name"] for line in text.splitlines()}
    assert code == 0 and names == {spec.name for spec in mcp_server.offered_tools()}


def test_no_token_runs_nothing(app_state, monkeypatch):
    mcp_server.token()
    code, text = _run(monkeypatch, "count_notes", token=False)
    assert code == 2 and "TESSELLATE_MCP_TOKEN" in json.loads(text)["error"]


def test_an_unoffered_tool_and_bad_json_are_errors(app_state, monkeypatch):
    code, text = _run(monkeypatch, "delete_entry", "--json", '{"entry_id": 1}')
    assert code == 1 and "error" in json.loads(text)
    code, text = _run(monkeypatch, "count_notes", "--json", "[1]")
    assert code == 2 and "one JSON object" in json.loads(text)["error"]


def test_the_skill_names_the_command_and_routes_each_offered_tool(app_state):
    skill = mcp_server.skill_snippet(["/opt/py", "-m", "tessellate"], {"TESSELLATE_DATA_DIR": "/d d"})
    assert skill.startswith("---\nname: tessellate-notebook\ndescription: ")
    assert "TESSELLATE_DATA_DIR='/d d' /opt/py -m tessellate tool NAME --json" in skill
    for spec in mcp_server.offered_tools():
        assert f"\n- {spec.name}: " in skill


def test_settings_shows_the_skill_from_capabilities(client):
    mcp = client.get("/capabilities").json()["features"]["mcp"]
    assert "tool NAME --json" in mcp["skill"]


def test_the_entry_point_reads_tool_before_its_flags():
    """main() is the process entry; the subcommand's wiring is its text."""
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
    head = text[text.index("def main() -> None:"):text.index("parser = argparse.ArgumentParser(prog=\"tessellate\"")]
    assert 'sys.argv[1:2] == ["tool"]' in head and "run_tool_command(sys.argv[2:]" in head
