"""WORLD_CLASS_PLAN 424 (n): one noun per thing.

The audit of 2026-09-24 found one thing under several names: Skills in
Settings and "AI skills" in the Library, and the Notes sub-tab called "Write
with Atlas" beside the Settings group called Atlas. The names are settled
(docs/DESIGN.md, Voice): the Library's sub-tab, its heading and the feature
list say "Skills", as the Settings pane does, and the Notes sub-tab for long
writing is "Writing room". A label that names a place is checked here so a
second noun cannot creep back in.
"""

from __future__ import annotations

import re
from pathlib import Path

HTML = Path("frontend/index.html").read_text(encoding="utf-8")
FEATURES = Path("frontend/js/app-features.js").read_text(encoding="utf-8")


def _label(pattern: str) -> str:
    found = re.search(pattern, HTML)
    assert found, pattern
    return found.group(1)


def test_the_library_and_settings_name_skills_the_same():
    library = _label(r'data-target="library-view-skills">([^<]+)</button>')
    settings = _label(r'<button data-section="skills">([^<]+)</button>')
    assert library == settings == "Skills"


def test_the_librarys_skills_heading_and_feature_row_use_the_same_noun():
    assert "<h2>Skills</h2>" in HTML.split('id="library-view-skills"')[1][:1500]
    assert '{ name: "Skills", desc: "The skills you can run' in FEATURES


def test_no_tab_or_sub_tab_is_called_write_with_atlas_or_ai_skills():
    tabs = re.findall(r'role="tab"[^>]*>([^<]+)</button>', HTML)
    assert "AI skills" not in tabs
    assert not [t for t in tabs if "Write with Atlas" in t]


LIBRARY = Path("frontend/js/library.js").read_text(encoding="utf-8")


def test_the_all_view_does_not_offer_a_kind_chip_a_sub_tab_already_is():
    """WORLD_CLASS_PLAN 424 (o): Documents, Boards & maps and Files were each
    a sub-tab and a chip in All (measured at 1440: Files 6 and Boards 1 chips
    beside the Files and Boards & maps sub-tabs). The sub-tab is the one
    filter; the chip stays in the row only while it is the selected kind, so
    a deep link to a kind still shows where it is."""
    kinds = set(re.findall(r'\{ key: "(\w+)", icon: "[^"]+", label: "[^"]+", subtab: true \}', LIBRARY))
    assert kinds == {"document", "file", "board", "map"}
    assert "(count === 0 || kind.subtab)" in LIBRARY
