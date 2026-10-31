"""The Appearance quick panel (INBOX 1435, the owner, 2026-10-29).

Settings, Appearance was "very large, and hard to navigate", and each change
meant closing Settings to see it. The panel is the page's own controls, moved
(not copied) into a non-modal panel on `panelMovable`, with a section strip,
Peek and a per-control reset. The browser half is driven by
a Playwright sweep (numbers in the commit; the scratchpad is at its file cap, so it is not
committed); here are the contracts a source check can hold.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"
PANEL = (JS / "appearance-panel.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY = (JS / "lazy-entries.js").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _own_css() -> str:
    text = (CSS / "appearance-panel-own-lazy.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _section_html() -> str:
    start = INDEX.index('<section class="settings-section hidden" id="settings-appearance">')
    return INDEX[start : INDEX.index("</section>", start)]


def test_the_copied_settings_rules_are_current():
    """One source: the panel's row styles are the Settings rules, renamed."""
    spec = importlib.util.spec_from_file_location("appearance_panel_css", ROOT / "scripts" / "appearance_panel_css.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (CSS / "appearance-panel-lazy.css").read_text(encoding="utf-8") == module.build(), (
        "run: PYTHONPATH=src .venv/bin/python scripts/appearance_panel_css.py"
    )


def test_the_panel_is_a_lazy_module_with_a_stand_in():
    assert 'appearancePanel: ["/css/appearance-panel-lazy.css", "/css/appearance-panel-own-lazy.css", "/js/appearance-panel.js"]' in LAZY
    assert 'appearancePanel: ["openAppearancePanel"]' in LAZY
    for name in ("appearance-panel-lazy.css", "appearance-panel-own-lazy.css"):
        assert (CSS / name).is_file()
    assert "appearance-panel.js" not in INDEX


def test_every_look_row_lives_in_the_page_the_panel_moves():
    """Moved, not copied: each LOOK_ROWS control is inside the one section the
    panel takes its children from, so none is left behind in Settings."""
    rows = (JS / "settings-rows.js").read_text(encoding="utf-8")
    block = rows[rows.index("const LOOK_ROWS") : rows.index("];", rows.index("const LOOK_ROWS"))]
    section = _section_html()
    ids = re.findall(r'id:\s*"([^"]+)"', block)
    assert len(ids) >= 29
    assert [i for i in ids if f'id="{i}"' not in section] == []


def test_the_controls_are_moved_and_put_back_never_cloned():
    assert "cloneNode" not in PANEL and "innerHTML" not in PANEL
    host = PANEL[PANEL.index("function appearanceHost") : PANEL.index("function appearanceUnhost")]
    assert "APPEARANCE_PANEL.body.appendChild(node)" in host
    unhost = PANEL[PANEL.index("function appearanceUnhost") : PANEL.index("async function openAppearancePanel")]
    assert "pane.appendChild(node)" in unhost and ".appearance-popped" in unhost
    # The title bar stays in Settings: its Pop out button and reset live there.
    assert '".settings-pane-title, .dock"' in host


def test_the_strip_names_the_six_sections_and_each_target_exists():
    strip = re.search(r"const APPEARANCE_STRIP = \[(.*?)\n\];", PANEL, re.S).group(1)
    labels = re.findall(r'\["(\w+)", "([^"]+)", ', strip)
    assert [label for _, label in labels] == ["Theme", "Colour", "Text", "Layout", "Background art", "Motion"]
    section = _section_html()
    for target in re.findall(r"""'\[data-fold-key="([^"]+)"\]'|"#([\w-]+)\"""", strip):
        fold, ident = target
        assert (f'data-fold-key="{fold}"' in section) if fold else (f'id="{ident}"' in section), target
    assert "prefs.set(APPEARANCE_KEY" in PANEL and "prefs.get(APPEARANCE_KEY" in PANEL


def test_it_opens_from_the_palette_the_top_bar_and_the_settings_page():
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    assert re.search(r'label: "ph:palette Appearance panel".*act: \(\) => openAppearancePanel\(\)', panes)
    settings = (JS / "settings.js").read_text(encoding="utf-8")
    assert '$("theme-btn").addEventListener("contextmenu"' in settings and "openAppearancePanel()" in settings
    controls = (JS / "settings-controls.js").read_text(encoding="utf-8")
    assert "function ensureAppearancePopOut" in controls and "Pop out" in controls
    assert 'if (box.id === "settings-appearance") ensureAppearancePopOut(box);' in controls


def test_it_is_non_modal_and_on_panel_movable():
    assert 'setAttribute("role", "dialog")' in PANEL and '"row space-between dialog-head"' in PANEL
    assert "aria-modal" not in PANEL
    assert 'ensureModule("panelMovable")' in PANEL
    css = _own_css()
    assert "position: fixed" in css
    #: Level with the top bar and over every bar the page pins below it (the
    #: notes dock at 19 drew over it at 2, INBOX 1453), under the menus (50
    #: and up), dialogs (1010) and toasts; later in the page, it wins a tie.
    boot = (ROOT / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    layer = int(re.search(r"\.chat-model-panel,\n\.appearance-panel \{\n  z-index: (\d+);", boot).group(1))
    sticky = [int(z) for sheet in (ROOT / "frontend" / "css").glob("*.css")
              for z in re.findall(r"position: sticky;[^}]*?z-index: (\d+);", sheet.read_text(encoding="utf-8"))]
    assert max(sticky) <= layer < 50, (max(sticky), layer)
    assert "scrim" not in css and "inset: 0" not in css
    # The foot of the file is the phone's sheet.
    assert "@media (max-width: 599.98px)" in css


def test_peek_fades_the_ground_with_a_token_mix_never_element_opacity():
    css = _own_css()
    peek = css[css.index(".appearance-panel.peeking {") : css.index("}", css.index(".appearance-panel.peeking {"))]
    assert "color-mix(in srgb, var(--panel)" in peek and "opacity" not in css
    assert 'setAttribute("aria-pressed"' in PANEL and 'peek.title = ' in PANEL
    # It ends with the panel, as Settings' does.
    close = PANEL[PANEL.index("function closeAppearancePanel") :]
    assert "appearanceSetPeek(false)" in close and "releaseThemeHold()" in close


def test_a_changed_control_gets_the_pages_own_reset():
    paint = PANEL[PANEL.index("function appearancePaintRows") : PANEL.index("function appearanceSchedulePaint")]
    assert "settingRowsIn(body)" in paint and "paintSettingRow(row, body)" in paint
    assert 'lazyScript("/js/settings-rows.js")' in PANEL


HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const ctx = { Math, Array, performance: { now: () => 0 } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8") + "\n;globalThis.api = { appearanceSectionAt };", ctx);
const at = ctx.api.appearanceSectionAt;
console.log(JSON.stringify({
  top: at([0, 300, 600, 900, 1400, 1100], 8),
  middle: at([0, 300, 600, 900, 1400, 1100], 650),
  motionBeforeArt: at([0, 300, 600, 900, 1400, 1100], 1150),
  last: at([0, 300, 600, 900, 1400, 1100], 5000),
  shut: at([0, 300, null, null, 1400, null], 700),
  nothingYet: at([200, 300, 600, 900, 1400, 1100], 8),
  allShut: at([null, null, null], 50),
}));
"""


@node
def test_the_section_in_view_is_the_last_one_that_has_reached_the_line(tmp_path):
    script = tmp_path / "harness.js"
    script.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(
        ["node", str(script), str(JS / "appearance-panel.js")], capture_output=True, text=True, check=True
    ).stdout
    got = json.loads(out)
    assert got == {
        "top": 0,
        "middle": 2,
        # Motion's fold sits above Background art in the page; the nearer top wins.
        "motionBeforeArt": 5,
        "last": 4,
        "shut": 1,
        "nothingYet": 0,
        "allShut": 0,
    }


def test_help_moves_with_the_panel():
    chat = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "Appearance panel" in chat
    more = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Pop out" in chat + more
    assert 'data-help-for' in PANEL or "dataset.helpFor" in PANEL
    assert 'id = "appearance-panel-help"' in PANEL
