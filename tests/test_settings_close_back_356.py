"""Back after closing Settings never reopens it (L-world-class-356, wc-109, 421 j).

Each pane visited inside Settings is a history entry of its own. The close
stepped back off one, so with panes changed Back landed on another Settings
entry and reopened Settings (the sweep `scratchpad/ui-sweeps/backtabs.js`
measured it: 4 of 4 failing before, 0 after). `routerSettle` runs here in
node with the stack, the browser's history and the two walkers stubbed."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
LAZY = (JS / "router-overlays.js").read_text(encoding="utf-8")
SETTLE = LAZY[LAZY.index("function routerSettle"):]
SETTLE = SETTLE[: SETTLE.index("\n}\n") + 3]

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def settle(stack, index, depth, edited=False):
    script = f"""
const calls = [];
const tabHistory = {{ stack: {json.dumps(stack)}, index: {index}, edited: {json.dumps(edited)} }};
const prefs = {{ get: () => "chat" }};
const location = {{ hash: "#/settings/skills", pathname: "/", search: "" }};
const history = {{ state: {{ navId: "x", depth: {depth} }}, replaceState: () => calls.push("replace") }};
const routerGo = (d) => {{ if (tabHistory.edited) return false; calls.push("go " + d); return true; }};
const goToTabHistory = (i) => calls.push("walk " + i);
const routeHash = () => "#/chat";
const routerPaintTitle = () => {{}};
{SETTLE}
routerSettle();
console.log(JSON.stringify(calls));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


PANES = [{"tab": "notes"}, {"tab": "chat"}] + [{"tab": "settings", "section": s} for s in ("models", "searchindex", "personas", "skills")]


def test_closing_after_pane_changes_steps_off_every_settings_entry():
    assert settle(PANES, 5, depth=5) == ["go -4"]


def test_closing_after_one_pane_still_steps_off_one():
    assert settle(PANES[:3], 2, depth=2) == ["go -1"]


def test_a_stack_walking_on_its_own_takes_the_same_step():
    assert settle(PANES, 5, depth=5, edited=True) == ["walk 1"]


def test_never_steps_back_past_the_apps_own_entries():
    #: Settings opened from its address: the browser's blank page is under it.
    assert settle(PANES, 5, depth=2) == ["replace"]


def test_settings_with_no_tab_under_it_corrects_the_address_in_place():
    only = [{"tab": "settings", "section": "models"}, {"tab": "settings", "section": "skills"}]
    assert settle(only, 1, depth=1) == ["replace"]
