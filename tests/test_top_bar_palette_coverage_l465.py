"""Source text: L465, "Add a lint measuring every rail and top-bar control has
a data-help-for popover and palette row". Every button the top bar shows
(the notification panel's own buttons aside) has a name a tooltip can show and
a Find anything row that does the same thing, so a control added to the bar
without one fails here. The top bar's icons are named by `title` and
`aria-label`; the '?' popover recipe is for help longer than a line, which no
bar control carries (docs/DESIGN.md, "Help longer than one line")."""
import re
from pathlib import Path

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]

#: Each top-bar control and the palette row's tell: a `tab:`, a `reveal:`, a
#: `chord:` or the call its `act` makes.
ROW = {
    "space-switcher-btn": '$("space-switcher-btn")?.click()',
    "privacy-chip": 'reveal: "settings:privacy"',
    "notif-btn": "act: () => openNotifications()",
    "theme-btn": 'chord: "toggleTheme"',
    "settings-btn": "act: () => openSettingsModal()",
    "lock-btn": "act: lockNow",
    "quit-btn": "act: () => quitApp()",
}


def _bar_buttons():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    start = html.index('<header id="top-bar"')
    bar = html[start : html.index("</header>", start)]
    return [(m.group(1), m.group(0)) for m in re.finditer(r'<button[^>]*\bid="([^"]+)"[^>]*>', bar) if not m.group(1).startswith("notif-") or m.group(1) == "notif-btn"]


def test_every_top_bar_control_is_named():
    for ident, tag in _bar_buttons():
        assert re.search(r'\b(title|aria-label)="[^"]+"', tag), ident


def test_every_top_bar_control_has_a_palette_row():
    src = app_js_text()
    missing = []
    for ident, _tag in _bar_buttons():
        if ident.startswith("tab-btn-"):
            tell = f'tab: "{ident.removeprefix("tab-btn-")}"'
        else:
            tell = ROW.get(ident)
        if not tell or tell not in src:
            missing.append(ident)
    assert not missing, missing
