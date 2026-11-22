"""Copy and labels the 2026-10-05 UX audit found wrong (UX-14, UX-15, UX-16).

Each is a small thing a person reads, and each had drifted from the control
it names: a tooltip reading "undefined", a Guide answer naming a Settings
section that does not exist, a word count that counted one kind of thing.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
INDEX = index_html_text()


def _settings_nav() -> dict[str, str]:
    nav = INDEX[INDEX.index('data-section="models" class="active"') - 200 :]
    nav = nav[: nav.index('data-section="about"') + 200]
    return {
        section: html.unescape(label).strip()
        for section, label in re.findall(r'<button[^>]*? data-section="([a-z]+)"[^>]*>([^<]+)</button>', nav)
    }


def test_a_help_badge_opening_a_settings_pane_names_it_as_the_nav_does():
    """UX-15: the Guide's storage answer said "Open Settings, Data"; the nav
    says "Import & export". A badge with a `target` names one control inside
    the pane and may say that control's name instead."""
    from tessellate.ai import help_chat

    nav = _settings_nav()
    assert {"models", "data", "about"} <= set(nav), nav
    wrong = []
    for topic in help_chat.HELP_TOPICS:
        badge = topic.get("badge") or {}
        section = badge.get("section")
        if not section or badge.get("target"):
            continue
        if nav.get(section) != badge["label"]:
            wrong.append((topic["id"], badge["label"], nav.get(section)))
    assert not wrong, wrong


def test_the_storage_answer_names_import_and_export():
    from tessellate.ai import help_chat

    storage = next(t for t in help_chat.HELP_TOPICS if t["id"] == "storage")
    assert "Settings -> Data" not in storage["body"]
    assert "Import & export" in storage["body"]


def test_a_menu_item_without_a_title_gets_no_tooltip():
    """UX-14: five of Chat's kebab items wore title="undefined"."""
    js = ROOT / "frontend" / "js"
    for path in sorted(js.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            if re.search(r"\bbutton\.title = item\.title;", line):
                assert "if (item.title)" in line, f"{path.name}: {line.strip()}"


def test_the_library_word_count_says_what_it_counts():
    """UX-16: "22 words written" over 29 notes and 2 documents counted the
    documents alone (`routes_library.py` sums `kind == "document"`)."""
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    assert "words written`" not in library
    assert "words in documents`" in library


def test_the_bin_is_called_the_bin():
    """UX-20 and DESIGN.md's glossary: one word for where deleted things wait.
    Comments may say "recycle bin" (it is what the code is about); a string
    the interface shows may not, except a palette row's `keywords`, which is
    what makes typing "recycle bin" still find it."""
    found = []
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.strip()
            if code.startswith(("//", "*", "/*")) or "keywords:" in code:
                continue
            if re.search(r"[\"'`][^\"'`]*recycle bin", code, re.IGNORECASE):
                found.append(f"{path.name}:{number}")
    shown = re.sub(r"<!--.*?-->", "", INDEX, flags=re.S)
    if re.search(r"recycle bin", shown, re.IGNORECASE):
        found.append("index.html")
    assert not found, found


def test_the_create_dialog_shows_browser_reserved_chords_only_in_the_desktop_window():
    """UX-21: Ctrl+Shift+N opens an incognito window in Chrome; a page never
    receives it, so the Create dialog advertised a key that did nothing."""
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    picker = library[library.index("function openLibraryCreatePicker(") :]
    picker = picker[: picker.index("\n}\n")]
    keys = next(line for line in picker.splitlines() if line.strip().startswith("keys:"))
    assert "window.pywebview" in keys

