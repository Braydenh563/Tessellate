"""Pins for the small layout and access fixes of 2026-10-19 (OPEN 1278, 1435, 408, 1482, 1400, 587).

Each one was measured in Chromium (scratchpad/ui-sweeps/smallfix1019*.js); these keep the
rule that fixed it from being edited away.

Measured (sweeps kept untracked, scratchpad cap): 1435/1278 notes grid scrollWidth vs clientWidth
1412/1408 (1440), 1003/999 (1024), 368/364 (390) before, equal after; quick-links group 368/364
at 390 before, quick-links box 364/364 after.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR


def _rules(css: str, selector: str) -> list[str]:
    """Bodies of every top-level-or-nested rule whose selector list is exactly `selector`."""
    found = []
    for m in re.finditer(r"(?m)^\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", css):
        found.append(m.group(1))
    return found


def _consistency() -> str:
    return (CSS_DIR / "08-consistency.css").read_text(encoding="utf-8")


def test_1435_notes_column_does_not_overflow_its_grid() -> None:
    bodies = _rules(_consistency(), "#tab-notes .layout > .tab-main")
    assert any(re.search(r"margin-right:\s*0\b", b) for b in bodies)


def test_1278_quicklinks_strip_does_not_overflow_its_group_on_phones() -> None:
    css = _consistency()
    m = re.search(
        r"@media \(max-width: 599\.98px\) \{\s*#dash-quicklinks \.launch-group > \.launch-row \{([^{}]*)\}",
        css,
    )
    assert m and re.search(r"margin-right:\s*0\b", m.group(1))


def test_408_header_buttons_ring_fits_inside_the_window_top() -> None:
    """Bar 44px, controls 36px: top 3.5px. Ring 2px at offset 2 reached -0.5; offset 1 gives +0.5
    (Tab-driven sweep at 1440: ring top -0.5 before, 0.5 after; Library sub-tab rings cut 0 top and bottom)."""
    css = _consistency()
    m = re.search(
        r"header#top-bar :is\(\.header-cluster, \.notif-wrap, \.header-controls\) button:focus-visible,\s*"
        r"header#top-bar button\.space-switcher-btn:focus-visible \{([^{}]*)\}",
        css,
    )
    assert m and re.search(r"outline-offset:\s*1px", m.group(1))


def test_1400_worded_buttons_carry_their_visible_words_in_their_name() -> None:
    """WCAG 2.5.3: a static button with visible words and an aria-label has those words in the label.

    Before: eight buttons (Local, From library, Jump to latest, Dock the tools..., Add child, Add beside,
    More, Reverse) were named by their tooltip sentence. The Snippets/Sections button is renamed by
    documents.js with the file type, so it is exempt here.
    """
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r"<button\b([^>]*)>(.*?)</button>", html, re.S):
        attrs, inner = m.groups()
        label = re.search(r'aria-label="([^"]*)"', attrs)
        if not label or 'id="doc-code-snippets-open"' in attrs:
            continue
        inner = re.sub(r"<i [^>]*></i>|<svg.*?</svg>", "", inner, flags=re.S)
        words = " ".join(re.sub(r"<[^>]+>", "", inner).split())
        if len(words) >= 2 and words.lower() not in label.group(1).lower():
            bad.append((words, label.group(1)))
    assert not bad


def test_1400_the_timeline_day_strip_name_opens_with_its_face() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "timeline.js").read_text(encoding="utf-8")
    assert 'button.setAttribute("aria-label", `${face}, ${label}`)' in js


def test_1482_empty_chats_line_uses_the_empty_line_recipe() -> None:
    """Measured at 1440 (pixel-checked bg): 5.91:1 light (102,100,95 on 255), 7.96:1 dark (181,179,173 on 30,30,28), 13.6px."""
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<p id="conv-empty" class="muted empty-line">', html)
    css = (CSS_DIR / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    body = _rules(css, ".empty-line")[0]
    assert "var(--muted)" in body and "var(--text-md)" in body


def test_587_restyled_dropdown_openers_stay_tabbable_buttons() -> None:
    """Sweep at 1440 over 7 tabs: 7 openers, 0 with tabindex < 0, 5 open on Enter and move on ArrowDown
    (the two others are date and time pickers; Chat's model list had one option on a fresh install)."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert 'opener.type = "button";' in js
    assert "opener.tabIndex" not in js and "opener.setAttribute(\"tabindex\"" not in js
    assert "function focusSelect(select)" in js


def test_the_tablet_band_keeps_the_notes_sub_tabs_clear_of_the_rail_toggle() -> None:
    """At 800 the collapse toggle (x 7 to 51) sat over "Your notes" (x 9.6): the
    rail clearance lost to the notes column's id-selector ring room. Measured
    after: the sub-tab starts at x 63 to 66 from 600 to 800, and 599 is unchanged."""
    css = (CSS_DIR / "sidebar-folds-lazy.css").read_text(encoding="utf-8")
    band = css.split("@media (min-width: 600px) and (max-width: 819.98px)", 1)[1]
    body = _rules(band, "#tab-notes .sidebar-panel ~ .tab-main")
    assert body and "var(--target-min)" in body[0] and "--sidebar-toggle-inset" in body[0]
