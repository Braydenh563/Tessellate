"""Settings panes that fetch before they can draw show skeletons, not a bare line.

DESIGN.md's list recipe: `showSkeletons(list, n)` before the fetch and
`clearSkeletons(list)` after it, only ever into an empty list, so a slow
disk reads as "on its way" and never as "nothing here" (the Models pane said
"Checking the models…" as a bare status line; What it remembers, What it
learned and the Logs list drew nothing at all until their first answer).
The frame-level proof is `scratchpad/ui-sweeps/settingsskel.js`, which holds
every API request and reads each pane at 300 ms.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _function(name: str) -> str:
    # Every file is read, in a fixed order: `glob` order differs between
    # machines, so a name defined twice gave CI a different body (4ae8312f).
    found = []
    for path in sorted(JS.glob("*.js")):
        text = unwrapped(path.read_text(encoding="utf-8"))
        found += [m.group(0) for m in re.finditer(rf"^(?:async )?function {name}\(.*?^}}$", text, re.S | re.M)]
    assert len(found) == 1, f"function {name} defined {len(found)} times"
    return found[0]


def test_what_it_remembers_shows_skeletons_while_the_memory_loads():
    body = _function("renderMemorySettings")
    assert 'showSkeletons(list' in body and "clearSkeletons(list)" in body
    assert body.index("showSkeletons(list") < body.index('apiJson("/memory")')
    assert body.index("clearSkeletons(list)") > body.index('apiJson("/memory")')


def test_what_it_learned_shows_skeletons_for_its_switches_and_its_list():
    switches = _function("renderLearnedSwitches")
    assert "showSkeletons(host" in switches and "clearSkeletons(host)" in switches
    assert switches.index("showSkeletons(host") < switches.index('apiJson("/learned/switches")')
    rows = _function("renderLearnedList")
    assert 'showSkeletons(list, 3, "li")' in rows and "clearSkeletons(list)" in rows
    assert rows.index("showSkeletons(list") < rows.index("apiJson(`/learned?")


def test_the_log_list_shows_skeletons_until_its_first_records_arrive():
    body = _function("renderLogs")
    assert 'showSkeletons($("log-list")' in body and 'clearSkeletons($("log-list"))' in body
    assert body.index("showSkeletons") < body.index('apiJson("/logs?limit=500")')


def test_the_models_pane_shows_skeletons_under_its_checking_line():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<div id="models-skeleton"[^>]*></div>', html)
    body = _function("renderSettings")
    checking = body.split("if (!status) {", 1)[1].split("\n  }\n", 1)[0]
    assert 'showSkeletons($("models-skeleton")' in checking
    # And they are taken out the moment a status exists.
    assert 'clearSkeletons($("models-skeleton"))' in body.split("if (!status) {", 1)[1].split("\n  }\n", 1)[1]
