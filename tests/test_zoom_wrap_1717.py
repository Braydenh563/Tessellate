"""INBOX 1717: at browser zoom 125 to 200 % (a 1440 window rendered as 1152,
960, 823 and 720 CSS pixels) bars wrapped onto new lines. The measured list
comes from `scratchpad/ui-sweeps/zoom1717.js`; this pins the rules that fixed
what it listed, so a later rewrite of a dock or the top bar cannot quietly
bring a wrap back. They lived at the end of 10-responsive.css until UI plan
13b (decision 19) moved each beside its component; the band rules of the
tab strip stay in 10."""

import re
from pathlib import Path

from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parent.parent
CSS = sheets(*FORMER_10)
CLEAN = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def has(selector: str, *needles: str) -> bool:
    """True if one rule whose selector is exactly `selector` holds every needle."""
    bodies = re.findall(r"(?:^|(?<=[{}]))\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", CLEAN)
    assert bodies, f"no rule for {selector!r}"
    return any(all(n in b for n in needles) for b in bodies)


def body(selector: str) -> str:
    """The declarations of the last rule, in load order, whose selector is exactly `selector`."""
    bodies = re.findall(r"(?:^|(?<=[{}]))\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", CLEAN)
    assert bodies, f"no rule for {selector!r}"
    return bodies[-1]


def test_dashboard_find_zone_may_shrink_below_its_prompt():
    assert has('.dock[data-dock-name="dashboard"] > .dock-find', "min-width: 0", "flex-basis: 12rem")


def test_search_input_does_not_set_the_find_zone_floor():
    assert re.search(
        r"@media \(max-width: 1099\.98px\)\s*\{\s*\.dock \.dock-find > \.dock-search > \.search-field-input\s*\{[^}]*width: 0",
        CLEAN,
    )
    assert has(".dock .dock-find:has(> .dock-search:only-child),\n  .dock .dock-find:has(> .dock-search):not(:has(> :not(.dock-search, .hidden, :empty)))", "flex-basis: 8rem")


def test_quick_access_label_ellipsises_through_the_density_override():
    assert has("#tab-dashboard .launch-head .launch-label", "flex-shrink: 1", "text-overflow: ellipsis", "min-width: 0")


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
    blocks = re.findall(r"@container chat-dock \(width < 47rem\)\s*\{(.*?)\n\}\n", CSS, flags=re.S)
    rules = [m.group(0) for b in blocks for m in re.finditer(r"> \.chat-tool-group-mode\s*\{[^}]*\}", re.sub(r"/\*.*?\*/", "", b, flags=re.S))]
    assert rules and all("flex: 1 1 16rem" in r and "100%" not in r for r in rules)


def test_timeline_count_chip_may_be_cut_and_says_all_of_it():
    assert has(".dock > .dock-identity:has(> .dock-chip)", "max-width: max-content", "min-width: 0")
    js = (ROOT / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    assert "chip.title = chip.textContent" in js and "pointerenter" in js


def test_day_strip_well_asks_for_less_under_1100():
    assert has(".timeline-days", "flex-basis: 19rem")


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
    #: The save state leaves the row below 820, not 600 (wrapzoom 2026-11-11: at 768 the
    #: dock is 652px and the state's 64px made a second row); test_wrapzoom_docs_1111 pins it.
    assert re.search(r"@container docdock \(max-width: 819\.98px\)\s*\{[^@]*?\.doc-dock-status\s*\{\s*display: none;", lazy)
    assert re.search(r"@container docdock \(max-width: 599\.98px\)\s*\{\s*#tab-documents \.doc-dock > \.doc-dock-identity\s*\{\s*flex-basis: 8rem;", lazy)


def test_code_document_tools_fold_into_the_kebab_by_the_docks_own_width():
    """200 % (720 wide): the dock is 544px and a code document's tools were 476px of 44px targets.
    Under 600px of dock the extras hide and their kebab rows (`.doc-phone-only`) show; the targets stay 44px."""
    lazy = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    lazy = re.sub(r"/\*.*?\*/", "", lazy, flags=re.S)
    hide = re.search(r"@container docdock \(max-width: 599\.98px\)\s*\{\s*(#tab-documents \.doc-actions > :is\([^)]*\)),\s*#tab-documents \.doc-view-menu\s*\{\s*display: none", lazy)
    assert hide, "the narrow dock must hide the extras it moved into the kebab"
    for ident in ("#doc-ai", "#doc-code-snippets-open", "#doc-code-assist-open", "#doc-code-format", "#doc-focus-toggle", ".graph-help-toggle"):
        assert ident in hide.group(1)
    assert re.search(r"@container docdock \(min-width: 600px\)\s*\{\s*#tab-documents \.doc-phone-only\s*\{\s*display: none", lazy)
    assert not re.search(r"@media \(min-width: 600px\)\s*\{\s*#tab-documents \.doc-phone-only", lazy)


def test_dock_title_shrinks_with_its_ellipsis_on_a_phone():
    """Rule 13: the 08 base is `flex: 0 0 auto`, so the title spilled 31px out of a shrunk identity zone at 390 and 480."""
    phone = "\n".join(re.findall(r"@media \(max-width: 599\.98px\)\s*\{\n(.*?)\n\}\n", CLEAN, flags=re.S))
    rules = re.findall(r"\.dock \.dock-identity > :is\(h1, h2, h3\)\s*\{([^}]*)\}", phone)
    assert rules and "flex: 0 1 auto" in rules[-1]
    band = re.search(r"\.dock \.dock-identity > :is\(h1, h2, h3, \.dock-chip\)\s*\{([^}]*)\}", phone).group(1)
    assert "text-overflow: ellipsis" in band and "min-width: 0" in band


def test_timeline_month_label_stays_on_one_line():
    assert "white-space: nowrap" in body(".timeline-daystrip-label.ghost.small")
