"""Every popup tool is listed everywhere (INBOX K27).

The owner: "equations dont show in the tools and features list, or the
command palette ... alt + = ... isnt in the keyboard shortcuts, same with
other things like the calculator, unit conversion". `POPUP_TOOLS`
(settings-panes.js) is the one registry; the palette, Tools and features, the
shortcuts dialog, the "/" menus and the Guide read it. This fails for an
entry the Guide does not know, or a surface that stops reading the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai.help_topics_more import MORE_TOPICS, TOPIC_META

ROOT = Path(__file__).resolve().parents[1] / "frontend"
JS = ROOT / "js"


def _registry() -> list[dict]:
    text = (JS / "settings-panes.js").read_text()
    body = text.split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0]
    tools = []
    for block in re.split(r"\n  \},?\n", body):
        fields = dict(re.findall(r'\b(id|name|keys|where|guide|group|about|keywords): "([^"]+)"', block))
        if fields:
            tools.append(fields)
    return tools


def test_registry_has_the_known_tools():
    ids = {t["id"] for t in _registry()}
    assert {"equation", "calculator", "convert", "timer", "stopwatch"} <= ids


def test_every_entry_is_complete_and_has_a_guide_topic():
    topics = {t["id"]: t for t in MORE_TOPICS}
    for tool in _registry():
        for field in ("name", "keys", "where", "guide", "group", "about", "keywords"):
            assert tool.get(field), f"{tool['id']} lacks {field}"
        assert tool["guide"] in topics, f"{tool['id']}: no Guide topic {tool['guide']}"
        assert tool["guide"] in TOPIC_META, f"{tool['id']}: Guide topic has no path"
        assert "Ctrl+K" in topics[tool["guide"]]["body"], f"{tool['id']}: the Guide does not say how to find it in the palette"


def test_every_surface_reads_the_registry():
    reads = {
        "settings-panes.js": ["...POPUP_TOOLS.map"],
        "app-features.js": ["of POPUP_TOOLS", "function renderToolShortcutList"],
        "reveal-targets.js": ['renderToolShortcutList($("shortcut-list-tools"))'],
        "editor.js": ["POPUP_TOOLS.filter", 'keys: "Alt+="'],
    }
    for name, needles in reads.items():
        text = (JS / name).read_text()
        for needle in needles:
            assert needle in text, f"{name} no longer reads the registry ({needle})"
    assert 'id="shortcut-list-tools"' in (ROOT / "index.html").read_text()


def test_the_editor_menus_get_a_row_for_every_tool():
    text = (JS / "editor.js").read_text()
    assert text.count('POPUP_TOOLS.filter((t) => t.id !== "equation")') == 2
    assert 'id: "chat-equation"' in text and 'id: "equation"' in text
