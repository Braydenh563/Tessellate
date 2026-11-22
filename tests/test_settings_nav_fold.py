"""Each Settings page's "On this page" list folds away (the owner: "I cant
collapse the sections below each settings page in the settings sidebar").

The list under the open page's link could only shrink to the link being read
(INBOX 698), never fold away. Its head is now a disclosure (DESIGN.md "A
disclosure that opens a list under it": `button.ghost.disclosure-row` with the
one caret), `aria-expanded` and `aria-controls` on a native button, so Enter
and Space work, and which pages are folded is remembered per page on this
device under one key. Measured by `scratchpad/ui-sweeps/settingsnavfold.js`.
"""

from __future__ import annotations

from pathlib import Path

from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
FIND = unwrapped((ROOT / "frontend" / "js" / "settings-find.js").read_text(encoding="utf-8"))
CSS = (ROOT / "frontend" / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")


def _build() -> str:
    start = FIND.index("function settingsIndexBuild(name)")
    return FIND[start : FIND.index("function settingsIndexWatchSection", start)]


def test_the_head_is_a_disclosure_button_with_the_one_caret():
    body = _build()
    assert '"ghost disclosure-row settings-nav-fold"' in body
    assert "ph ph-caret-down contents-caret" in body
    assert 'fold.setAttribute("aria-expanded"' in body and 'fold.setAttribute("aria-controls"' in body
    assert 'fold.type = "button"' in body


def test_folded_pages_are_remembered_per_page():
    body = _build()
    assert 'prefs.get("settings-nav-folded"' in body and 'prefs.set("settings-nav-folded"' in body
    assert "folded.includes(name)" in body


def test_a_folded_list_hides_every_link_and_its_show_all_toggle():
    assert (
        "#settings-nav .settings-nav-groups.is-folded .settings-nav-group,\n"
        "#settings-nav .settings-nav-groups.is-folded .settings-nav-groups-head .linklike {"
    ) in CSS


def test_the_hide_rules_outrank_the_links_own_display():
    """`#settings-nav .settings-nav-group { display: block }` (the one-line ellipsis)
    outranked the class-only hide, so the short list showed every link (measured:
    8 of 8 shown with the list short). Every rule that hides a link carries the id."""
    forms = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    assert "#settings-nav .settings-nav-group {" in forms
    assert '#settings-nav .settings-nav-groups:not(.is-open) .settings-nav-group:not([aria-current="location"]) {' in CSS
    assert '.settings-nav-fold[aria-expanded="false"] .contents-caret' in CSS


def test_the_guide_says_the_list_folds():
    from tessellate.ai.help_topics_more import MORE_TOPICS as TOPICS

    body = next(t["body"] for t in TOPICS if t["id"] == "settings-overview")
    assert "press On this page above them to fold that list away" in body
