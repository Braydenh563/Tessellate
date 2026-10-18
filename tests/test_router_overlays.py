"""Browser Back with an overlay open (WORLD_CLASS_PLAN row 32, the audit of
2026-10-18): the palette, finder, Guide, shortcuts and quick note stayed open
while Back moved the tab history (5 of 5). Back now closes the top overlay and
puts the history back; Escape on Settings steps its entry off instead of
rewriting its address; the agent palette gives focus back to its opener.

The code is a lazy file because router.js is boot code at its gzip cap. These
are the shapes the suite can see; the behaviour is the browser sweep (7 of 7 at
1440 and at 390, Settings Escape, agent focus)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
ROUTER = (JS / "router.js").read_text(encoding="utf-8")
LAZY = (JS / "router-overlays.js").read_text(encoding="utf-8")
APP = (JS / "app.js").read_text(encoding="utf-8")


def test_the_popstate_listener_asks_the_lazy_hook_first():
    listener = ROUTER[ROUTER.index('window.addEventListener("popstate"') :]
    first = listener.splitlines()[1:4]
    assert any("routerBackHook(event)" in line for line in first), first
    assert "function routerBackHook(" in LAZY


def test_settle_lives_in_the_lazy_file_and_settings_loads_it():
    assert "function routerSettle" not in ROUTER
    assert "function routerSettle()" in LAZY
    assert 'ensureModule("quickNote").then(() => routerSettle())' in (JS / "settings.js").read_text(encoding="utf-8")
    assert 'quickNote: ["/js/quick-note.js", "/js/router-overlays.js"]' in APP


def test_every_closer_the_hook_calls_is_a_global_function():
    names = re.findall(r'\["[\w-]+", "(close\w+)"\]', LAZY)
    assert len(names) >= 6
    everything = "\n".join(p.read_text(encoding="utf-8") for p in JS.glob("*.js"))
    for name in names:
        assert re.search(rf"^(?:async )?function {name}\(", everything, re.M), name


def test_the_agent_palette_records_its_opener():
    assert "cmdPaletteOverlay.opener = document.activeElement" in (JS / "palette.js").read_text(encoding="utf-8")
    assert "overlay.opener" in LAZY


def test_hidden_sheets_do_not_count_as_open():
    """At 390 eight hidden `.sheet-overlay` elements sit in the page."""
    assert ".sheet-overlay:not(.sheet-leaving):not(.hidden)" in LAZY


def test_settings_escape_never_steps_off_the_app():
    """CI e2e on d04186d: Settings opened from its address has the browser's
    blank page under it; Escape stepped back onto it. Each entry the router
    writes carries how many of its own sit under it, and Escape steps back only
    onto one of those."""
    router = (JS / "router.js").read_text(encoding="utf-8")
    assert "history.pushState({ navId: entry.navId, depth: depth + 1 }" in router
    assert "history.replaceState({ navId: entry.navId, depth }" in router
    settle = LAZY[LAZY.index("function routerSettle"):]
    assert "history.state?.depth > 0 && routerGo(-1)" in settle.split("\n}\n")[0]
