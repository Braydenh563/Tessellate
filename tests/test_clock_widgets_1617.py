"""The Stopwatch and Alarm dashboard widgets (INBOX 1617, the owner: "additional
alarm and stopwatch widgets"). Each is one tab of the Clock drawn with no strip
through the popup's own build (`only`), over the same running clocks and the
same reminders: no second copy of either."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOCK = (ROOT / "frontend/js/utility-tools.js").read_text(encoding="utf-8")
DASH = (ROOT / "frontend/js/dashboard.js").read_text(encoding="utf-8")
PANES = (ROOT / "frontend/js/settings-panes.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/utilities-lazy.css").read_text(encoding="utf-8")


def test_stopwatch_and_alarm_are_widgets_of_their_own():
    table = DASH.split("const POPUP_WIDGETS = {", 1)[1].split("\n  };", 1)[0]
    assert 'openClockPanel.inline("stopwatch", body, { only: true })' in table
    assert 'openClockPanel.inline("alarm", body, { only: true })' in table
    for kind in ("stopwatch", "alarm"):
        assert re.search(rf'^\s+{kind}: \{{ title: "ph:[\w-]+ \w+", description: "[^"]{{20,}}"', table, re.M)


def test_the_tools_name_those_widgets_and_the_clock_keeps_the_timer():
    def widget(tool_id: str) -> str:
        block = PANES.split(f'id: "{tool_id}"', 1)[1].split("\n  },", 1)[0]
        return re.search(r'widget: "(\w+)"', block).group(1)

    assert widget("timer") == "clock"
    assert widget("stopwatch") == "stopwatch"
    assert widget("alarm") == "alarm"


def test_one_pane_no_strip_and_a_list_of_its_own_kind():
    build = CLOCK.split("function clockPanelBuild(", 1)[1].split("\n  }\n", 1)[0]
    assert "only = false" in build and ".filter(([key]) => !only || key === tab)" in build
    # No tab strip is appended for a single pane; an alarm has no running list (it is a reminder).
    assert "...(only ? [] : [strip])" in build
    assert 'only && tab === "alarm" ? [] : [running]' in build
    paint = CLOCK.split("function paintClockPanel(", 1)[1].split("\n  }\n", 1)[0]
    assert "view.kinds.includes(clock.kind)" in paint
    assert ".clock-only .clock-time {" in CSS


def test_the_alarm_is_still_an_ordinary_reminder_and_the_stopwatch_keeps_laps():
    assert "utilityOps.alarmSet(" in CLOCK and "addReminder(label" in CLOCK
    assert "row.laps.replaceChildren" in CLOCK and 'clockEl("ol", "clock-laps muted")' in CLOCK


def test_a_stopwatchs_laps_area_holds_its_height_so_lap_never_moves_1651():
    # The card is anchored to the window's foot: a laps list that grew per press lifted the Lap button 18px each time.
    assert 'row.laps.classList.toggle("clock-laps-held", isWatch)' in CLOCK
    held = CSS.split(".clock-laps-held {", 1)[1].split("}", 1)[0]
    cap = re.search(r"\.clock-laps \{[^}]*max-height: ([^;]+);", CSS).group(1)
    assert f"min-height: {cap}" in held
