"""L-world-class-780 (rule 2, three clicks): the reach.js depth-4 crawl found the
activity panel's Running and History tabs four presses deep (Chat > More actions >
Activity and past runs > tab; Library > Documents > Images > Running). Each of the
panel's three tabs gets a palette command that opens it on that tab, so each is
one chord and one pick away.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _palette_rows() -> list[str]:
    return [line for line in app_js_text().splitlines() if "openActivity(" in line and "label:" in line and "act:" in line]


def test_each_activity_tab_has_a_palette_command() -> None:
    tabs = set()
    for line in _palette_rows():
        tabs.update(re.findall(r'act: \(\) => openActivity\("(\w+)"\)', line))
    assert {"running", "runs", "history"} <= tabs, tabs


def test_the_history_command_says_history() -> None:
    rows = [r for r in _palette_rows() if 'openActivity("history")' in r]
    assert rows and all("history" in r.lower().split("act:")[0] for r in rows), rows
