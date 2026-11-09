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
    rule = body(".dock .dock-find:has(> .dock-search:only-child)")
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


def test_the_sweep_covers_the_four_zooms_in_both_themes():
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "zoom1717.js").read_text(encoding="utf-8")
    assert "'125,150,175,200'" in sweep and "deviceScaleFactor: f" in sweep
    assert "process.env.THEME" in sweep
