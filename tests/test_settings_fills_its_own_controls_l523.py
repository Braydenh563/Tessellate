"""Every control `renderAutonomousSettings` fills that sits outside
Background tasks is filled when its own pane opens (L523): Tools opened first
showed "Let MCP clients write" unchecked over a preference that was on, as
Models once did for smart routing."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
JS = ROOT / "frontend/js"


def _pane_of(control: str) -> str:
    sections = [(m.start(), m.group(1)) for m in re.finditer(r'<section class="settings-section[^"]*" id="settings-([a-z-]+)"', HTML)]
    at = HTML.index(f'id="{control}"')
    return [name for pos, name in sections if pos < at][-1]


def test_each_control_outside_background_tasks_is_filled_when_its_pane_opens():
    prefs = (JS / "settings-prefs.js").read_text(encoding="utf-8")
    body = prefs[prefs.index("function renderAutonomousSettings()") :]
    body = body[: body.index("\n}\n")]
    show = (JS / "settings.js").read_text(encoding="utf-8")
    show = show[show.index("function showSettingsSection(") :]
    show = show[: show.index("\n}\n")]
    controls = re.findall(r'\$\("(pref-[a-z-]+)"\)', body)
    outside = {c: _pane_of(c) for c in controls if _pane_of(c) != "tasks"}
    assert outside == {"pref-mcp-writes": "tools", "pref-smart-model-routing": "models", "pref-learned-audit": "learned"}
    for control, pane in outside.items():
        branch = show[show.index(f'if (name === "{pane}")') :]
        branch = branch[: branch.index("\n  }\n")]
        assert f'$("{control}").checked' in branch, f"{pane} opens without filling {control}"
