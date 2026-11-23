"""Source text: the Settings snippet for the MCP skill is drawn by a lazy
pane (settings-controls.js) that the suite cannot open without a browser, so
its markup and wiring are read as text. Moved from test_mcp_server.py."""


def test_settings_draws_the_skill_snippet_with_its_own_copy():
    from pathlib import Path

    from tests._app_js import frontend_text

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="mcp-skill-snippet"' in html and 'id="mcp-skill-copy"' in html
    js = frontend_text("settings-controls.js")
    body = js[js.index("async function renderMcpSnippet()"):]
    body = body[: body.index("\n}\n")]
    assert "mcp.skill" in body and "mcp-skill-copy" in body and "mcp-skill-toggle" in body
