"""Every popup tool can be a dashboard widget (INBOX 1558).

The owner: "cant add the timer, calculator, converter, stopwatch etc".
`POPUP_TOOLS` (settings-panes.js) is the one registry of the popup tools;
each entry names the dashboard widget that draws it inline (`widget`) or says
why it has none (`widgetExempt`). The Add widget list reads the registry, the
Clock and the Calculator mount into the widget body through the same build
the popup uses (no second copy), and every tool is a Quick access tile too.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _registry() -> list[dict]:
    body = _read("settings-panes.js").split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0]
    tools = []
    for block in re.split(r"\n  \},?\n", body):
        fields = dict(re.findall(r'\b(id|widget|widgetExempt): "([^"]+)"', block))
        if "id" in fields:
            tools.append(fields)
    return tools


def _widget_kinds() -> set[str]:
    dash = _read("dashboard.js")
    table = dash.split("const POPUP_WIDGETS = {", 1)[1].split("\n  };", 1)[0]
    return set(re.findall(r"^\s+(\w+): \{ title:", table, re.M))


def test_every_popup_tool_has_a_widget_or_a_stated_exemption():
    kinds = _widget_kinds()
    assert kinds >= {"clock", "calculator"}
    tools = _registry()
    assert {t["id"] for t in tools} >= {"calculator", "convert", "timer", "stopwatch", "alarm"}
    for tool in tools:
        widget, why = tool.get("widget"), tool.get("widgetExempt")
        assert bool(widget) != bool(why), f"{tool['id']}: name a widget or say why it has none, not both or neither"
        if widget:
            assert widget in kinds, f"{tool['id']}: widget {widget} has no row in POPUP_WIDGETS (dashboard.js)"
        else:
            assert len(why) > 12, f"{tool['id']}: the exemption must give a reason"


def test_the_widget_list_is_driven_from_the_registry():
    dash = _read("dashboard.js")
    assert "POPUP_TOOLS" in dash and "DASH_WIDGETS[id] =" in dash
    # A kind with no tool pointing at it adds nothing to the Add widget list.
    assert "POPUP_TOOLS.some((tool) => tool.widget === id)" in dash
    # New widgets are off until added (an existing layout does not grow two cards).
    assert "DASH_OPT_IN.push(id)" in dash


def test_the_clock_and_the_calculator_mount_through_the_popups_own_build():
    clock = _read("utility-tools.js")
    assert clock.count("function clockPanelBuild(") == 1
    assert "openClockPanel.inline = (tab, host, { only = false } = {}) =>" in clock
    assert "clockPanelBuild(host, tab, { inline: true, only })" in clock
    assert "clockPanelBuild(card, tab)" in clock
    kit = _read("reply-kit.js")
    assert kit.count("function replyCalcBuild(") == 1
    assert 'openCalculator.inline = (host, mode = "work", { only = false } = {}) => replyCalcBuild(host, "", mode, { inline: true, only })' in kit
    assert "build: (card, close) => replyCalcBuild(card, input, mode, { target, close })" in kit
    dash = _read("dashboard.js")
    assert 'openClockPanel.inline("timer", body)' in dash and "openCalculator.inline(body" in dash


def test_two_clock_views_do_not_share_ids_or_one_store():
    clock = _read("utility-tools.js")
    assert "clockMounts" in clock and "for (const view of clockMounts)" in clock
    assert "clock-tab-${n}-${key}" in clock and "clock-panel-${n}-${key}" in clock
    # The old single store is gone: replace, do not layer.
    assert "clockPanel.list" not in clock and "clockPanel.empty" not in clock


def test_every_popup_tool_is_a_quick_access_tile():
    feats = _read("app-features.js")
    row = next(line for line in feats.splitlines() if "...POPUP_TOOLS.map((t) =>" in line)
    assert "quick: `tool-${t.id}`" in row
    catalogue = feats.split("function quickCatalogue(only = null)", 1)[1].split("\n}\n", 1)[0]
    assert 'row.keys && !row.quick ? ""' in catalogue
