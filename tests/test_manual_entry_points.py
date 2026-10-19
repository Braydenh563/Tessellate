"""The manual is easy to find and every way in opens it (owner, 2026-10-19).

Measured in Chromium (untracked sweep): Find anything "manual" lists "Open the
manual" first and Enter opens the manual with Settings closed; the same in the
Ctrl+K palette; Settings, Help, The manual topic now has an "Open the manual"
button that opens the manual over Settings; the dashboard quick-access catalogue
holds `reveal:manual`. The Guide's text names its More actions menu.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def test_the_palette_and_find_anything_have_an_open_the_manual_command():
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    assert '{ label: "ph:book-open-text Open the manual", reveal: "manual" }' in panes
    targets = (JS / "reveal-targets.js").read_text(encoding="utf-8")
    assert 'manual: { open: () => lazyScript("/js/manual.js")' in targets and 'built: "openManual"' in targets
    # Its description (the quick-access tile's line) comes from the features list.
    assert 'reveal: "manual" }' in (JS / "app-features.js").read_text(encoding="utf-8")


def test_the_manual_topic_in_settings_help_opens_the_manual_itself():
    find = (JS / "settings-find.js").read_text(encoding="utf-8")
    assert 'topic.id === "manual" ? { manual: true' in find
    assert "if (link.manual) button.addEventListener" in find


def test_the_guide_names_the_menu_that_holds_the_manual():
    text = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "Guide's More actions menu" in text
    assert "Guide's ... menu" not in text
