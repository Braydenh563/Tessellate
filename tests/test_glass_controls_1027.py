"""Glass controls (INBOX 1409, the owner, 2026-10-27: "those glass styles were
pretty cool, can they be applied as a glass aesthetic globally in the
appearances? also they should only be glass if the glass aesthetic is
enabled").

A switch in Settings, Appearance, off by default, dresses the app's icon
buttons in the image chip's glass (80% panel, the clear glass filter, a
hairline, ink). The rules live in a lazy sheet, fetched only when the switch
is on (the boot CSS is held by tests/test_boot_budget.py), and every one of
them needs the glass look on: with glass off, or Performance mode, nothing
changes.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "glass-controls-lazy.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
GUARD = ':root:not([data-glass="off"])[data-glass-controls="on"] '


def _rules():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css)]


def test_every_rule_is_glass_only_while_the_glass_look_and_the_switch_are_on():
    rules = _rules()
    assert rules
    for selector, _body in rules:
        #: One selector per rule: the glass lint splits on commas, so a list
        #: (or a comma inside :not()) would be read as several.
        assert "," not in selector, selector
        assert selector.startswith(GUARD), selector
    blurred = [body for _s, body in rules if "backdrop-filter" in body]
    assert blurred and all("backdrop-filter: var(--glass-filter-clear);" in b and "-webkit-backdrop-filter: var(--glass-filter-clear);" in b for b in blurred)
    assert any("color-mix(in srgb, var(--panel) 80%, transparent)" in b for b in blurred)


def test_a_chip_leaves_menu_openers_and_chosen_buttons_alone():
    selectors = " ".join(s for s, _b in _rules())
    #: Kebab openers are dressed once, in 08-consistency.css (test_ui_recipes).
    assert ".kebab-opener" not in selectors
    assert ':not([aria-haspopup="menu"])' in selectors
    for state in (".active", '[aria-pressed="true"]', '[aria-expanded="true"]'):
        assert f":not({state})" in selectors


def test_the_sheet_is_lazy_not_a_boot_link():
    assert "glass-controls-lazy.css" not in INDEX
    entries = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'glassControls: ["/css/glass-controls-lazy.css"]' in entries


def test_the_switch_has_a_row_a_default_a_reset_and_a_help_line():
    row = INDEX[INDEX.index('id="glass-controls-row"') :]
    row = row[: row.index("</label>")]
    assert 'id="glass-controls-toggle"' in row and "Glass controls" in row
    settings = frontend_text("settings.js")
    assert '"glass-controls": "off",' in settings
    assert "root.dataset.glassControls = appearancePref(\"glass-controls\");" in settings
    assert 'ensureModule("glassControls")' in settings
    assert '$("glass-controls-toggle").addEventListener("change"' in settings
    reset = settings[settings.index("function resetAppearance()") :]
    assert '"glass-controls"' in reset[: reset.index("prefs.remove(key)")]
    rows = (ROOT / "frontend" / "js" / "settings-rows.js").read_text(encoding="utf-8")
    assert '{ key: "glass-controls", id: "glass-controls-toggle", on: "on", off: "off" },' in rows
    #: Without glass there is nothing to dress: the row dims, as the sheen's does.
    assert '$("glass-controls-row").classList.toggle("disabled-row", appearancePref("glass") !== "on" || perfModeOn());' in settings


def test_the_guide_knows_the_switch():
    from tessellate.ai import help_chat

    body = " ".join(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "themes" or t.get("badge", {}).get("section") == "appearance")
    assert "Glass controls" in body
