"""INBOX 1717: at browser zoom 125 to 200 % (a 1440 window rendered as 1152,
960, 823 and 720 CSS pixels) bars wrapped onto new lines. The measured list
comes from `scratchpad/ui-sweeps/zoom1717.js`; this pins the rules that fixed
what it listed, in the one place they live (the end of 10-responsive.css), so
a later rewrite of a dock or the top bar cannot quietly bring a wrap back."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
SECTION = CSS[CSS.index("INBOX 1717") :]
CLEAN = re.sub(r"/\*.*?\*/", "", SECTION, flags=re.S)


def body(selector: str) -> str:
    """The declarations of the first rule in the 1717 section whose selector is `selector`."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CLEAN)
    assert match, f"no rule for {selector!r} in the INBOX 1717 section"
    return match.group(1)


def test_dashboard_find_zone_may_shrink_below_its_prompt():
    rule = body('.dock[data-dock-name="dashboard"] > .dock-find')
    assert "min-width: 0" in rule and "flex-basis: 12rem" in rule


def test_search_input_does_not_set_the_find_zone_floor():
    assert re.search(
        r"@media \(max-width: 1099\.98px\)\s*\{\s*\.dock \.dock-find > \.dock-search > \.search-field-input\s*\{[^}]*width: 0",
        CLEAN,
    )
    rule = body(".dock .dock-find:has(> .dock-search:only-child),\n  .dock .dock-find:has(> .dock-search):not(:has(> :not(.dock-search, .hidden, :empty)))")
    assert "flex-basis: 8rem" in rule


def test_quick_access_label_ellipsises_through_the_density_override():
    rule = body("#tab-dashboard .launch-head .launch-label")
    assert "flex-shrink: 1" in rule and "text-overflow: ellipsis" in rule and "min-width: 0" in rule


def test_top_bar_keeps_one_row_at_175_percent():
    """In the existing 940 band (no new breakpoint): the switcher is its icon and the tabs take one padding step less."""
    shell = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    band = re.search(r"@media \(max-width: 940px\)\s*\{(.*?)\n\}\n", shell, flags=re.S).group(1)
    assert re.search(r"header#top-bar \.space-switcher-name\s*\{[^}]*display: none", band)
    assert re.search(r"#tab-bar button\s*\{[^}]*padding-inline: var\(--space-3\)", band)


def _between(text: str, start: str) -> str:
    """The text from `start` to the next numbered section marker (or the end)."""
    i = text.index(start)
    m = re.search(r"\n/\* \d+\. \*\*", text[i + 1 :])
    return text[i : i + 1 + m.start()] if m else text[i:]


def test_top_bar_keeps_one_row_at_200_percent():
    """720 wide (200 %): only the chosen tab keeps its caption, the wordmark is out of the row and the gaps close a step."""
    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    band = re.search(r"@media \(min-width: 600px\) and \(max-width: 819\.98px\)\s*\{(.*?)\n\}\n", css, flags=re.S).group(1)
    band = re.sub(r"/\*.*?\*/", "", band, flags=re.S)
    assert re.search(r"#tab-bar button:not\(\.active\) \.tab-label\s*\{[^}]*display: none", band)
    assert re.search(r"header#top-bar h1\s*\{[^}]*display: none", band)
    assert re.search(r"#top-bar \.header-controls,\s*#top-bar \.header-cluster\s*\{[^}]*gap: var\(--space-1\)", band)


def test_ask_mode_row_shares_the_line_when_it_fits():
    """A basis, not 100 %: Skills, Web and Plan leave 316px at 200 %, enough for the segment, the gear and a model picker."""
    css = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
    block = re.search(r"@container chat-dock \(width < 47rem\)\s*\{(.*?)\n\}\n", css, flags=re.S).group(1)
    rule = re.search(r"> \.chat-tool-group-mode\s*\{[^}]*\}", re.sub(r"/\*.*?\*/", "", block, flags=re.S)).group(0)
    assert "flex: 1 1 16rem" in rule and "100%" not in rule


def test_timeline_count_chip_may_be_cut_and_says_all_of_it():
    rule = body(".dock > .dock-identity:has(> .dock-chip)")
    assert "max-width: max-content" in rule and "min-width: 0" in rule
    js = (ROOT / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    assert "chip.title = chip.textContent" in js and "pointerenter" in js


def test_day_strip_well_asks_for_less_under_1100():
    assert "flex-basis: 19rem" in body(".timeline-days")


def test_document_tools_lose_their_words_under_1100():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for word in ("Format", "Run", "New"):
        assert f'<span class="toolbar-word">{" " if word != "New" else ""}{word}</span></button>' in html
    for name in ("Format", "Run"):
        assert f'aria-label="{name}"><i' in html
    assert "display: none" in body(".doc-dock .doc-actions .toolbar-word,\n  #doc-sidebar-list .toolbar-word")
    assert "flex-basis: 12rem" in body(".doc-dock > .doc-dock-identity")


def test_diagram_foot_buttons_share_a_narrow_pane():
    rule = body(".dgm-foot > .small")
    assert "min-width: 0" in rule and "flex: 1 1 auto" in rule and "padding-inline: var(--space-1)" in rule


def test_the_sweep_reaches_the_companion_bubble_and_the_graph_popup():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "zoom1717.js").read_text(encoding="utf-8")
    assert "nameMarkSay(b," in sweep and "openGraphPopup({stopPropagation" in sweep and "graphNodesRef" in sweep


def test_the_sweep_covers_the_four_zooms_in_both_themes():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "zoom1717.js").read_text(encoding="utf-8")
    assert "'125,150,175,200'" in sweep and "deviceScaleFactor: f" in sweep
    assert "process.env.THEME" in sweep


def test_settings_nav_head_gives_the_toggle_the_room_to_stay_on_the_label_line():
    rule = body(".settings-nav-groups-head")
    assert "gap: var(--space-1)" in rule and "padding-inline: var(--space-5) 0" in rule


def test_recent_head_title_is_clipped_not_removed_under_1200():
    match = re.search(
        r"Browser zoom, rule 9 below[^*]*\*/\s*#doc-sidebar-list > \.sidebar-head > h2\s*\{([^}]*)\}",
        CSS,
    )
    assert match, "the Recent head's title rule is gone"
    rule = match.group(1)
    assert "width: 0" in rule and "clip-path: inset(50%)" in rule and "display: none" not in rule


def test_a_sidebar_empty_line_has_a_step_less_padding():
    rule = body("#chat-sidebar .empty-state,\n#doc-sidebar .empty-state")
    assert "padding-inline: var(--space-3)" in rule


def test_deliberate_bleeds_are_clipped_with_a_margin_not_scrolled():
    rule = body("#learned-switches,\n#learned-switches .learned-switch-stack,\n.library-controls")
    assert "overflow: clip" in rule and re.search(r"overflow-clip-margin: (\d+)px", rule)


def test_theme_cards_are_wide_enough_for_the_longest_look_name():
    assert "minmax(7.5rem, 1fr)" in body(".theme-presets")


def test_the_document_dock_gives_its_name_up_before_its_tools():
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    lazy = re.sub(r"/\*.*?\*/", "", lazy, flags=re.S)
    wide = re.search(r"@container docdock \(max-width: 819\.98px\)\s*\{\s*\.doc-back-label\s*\{\s*display: none;", lazy)
    assert wide, "Back keeps its word at 820 and under"
    assert re.search(r"#tab-documents \.doc-dock > \.doc-dock-identity\s*\{\s*flex-basis: 12rem;\s*min-width: 0;", lazy)
    assert re.search(r"\.doc-dock-identity > \.doc-title-input\s*\{[^}]*min-width: 5rem", lazy)
    assert re.search(
        r"@container docdock \(max-width: 599\.98px\)\s*\{\s*\.doc-dock-status\s*\{\s*display: none;\s*\}"
        r"\s*#tab-documents \.doc-dock > \.doc-dock-identity\s*\{\s*flex-basis: 8rem;",
        lazy,
    )
