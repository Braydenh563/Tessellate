"""A focus ring is never cut off by the container it sits in (INBOX 685).

The owner, with a screenshot of the Dashboard constellation's Regenerate
button whose focus ring was cut along its left edge: "a lot of borders get cut
off on an edge."

A ring is an outline outside the control's box (2px line, 2px offset, so
`--ring-room`: 4px). An ancestor with `overflow` other than visible, `contain:
paint` or a `clip-path` paints nothing outside its padding box, so a control
flush against that edge loses the side of its ring, and nothing reports it:
the declaration applies, the element is focused, and a piece of the ring is
simply not painted. Only a measurement sees it, which is what
`scratchpad/ui-sweeps/clip685.js` does (every focusable on every surface, its
ring's outer box against every clipping ancestor, 1440 and 390, both themes).

The fix is by container, in one place (08-consistency.css, "Ring room"), in
one of two recipes, never by hiding the ring:

- **room**: the container leaves `--ring-room` for the ring, as padding with
  the same negative margin (it scrolls) or `overflow-clip-margin` (it clips);
- **inset**: its children fill it edge to edge, so the ring is drawn inside
  the control with `outline-offset: -2px`.

This lint holds the list of containers the sweep found, so a later edit that
drops the room (a cleanup of "redundant" padding, a rewrite of the strip)
fails here rather than being found by the next screenshot. A container the
sweep finds later is added to `RING_ROOM` in the same commit as its fix: the
sweep is the proof, this is the ratchet.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR, css_text

#: (what it is, a fragment of the selector, the recipe).
RING_ROOM: list[tuple[str, str, str]] = [
    ("dashboard widget body and its rows", ".dash-body .row", "room"),
    ("dashboard widget body that scrolls", ".dash-body", "room"),
    ("sub-tab strips", ".tabs-line > button", "inset"),
    ("document breadcrumbs", ".doc-crumbs .doc-crumb", "inset"),
    ("graph legend toggle", "#graph-legend .legend-toggle", "inset"),
    ("sidebar resize handle", ".sidebar-resize", "inset"),
    ("notes category list rows", "#category-list li", "inset"),
    ("document list rows", ".doc-item-button", "inset"),
    ("document outline links", ".outline-link", "inset"),
    ("document outline twists", ".outline-twist", "inset"),
    ("template choices", ".doc-template-choice", "inset"),
    ("a sheet's rows", ".sheet-row", "inset"),
    ("graph zoom group", ".graph-zoom-btn", "inset"),
    ("chat mode switch", ".chat-dock-controls .seg > button", "inset"),
    ("document sidebar sections", ".doc-sidebar-section", "room"),
    ("library sections", ".library-view-section", "room"),
    ("document and library lists", ".doc-list", "room"),
    ("Settings nav", ".modal-nav", "room"),
    ("a sheet's scrolling body (New meeting)", ".inbox-body", "room"),
    ("chip, tile and filter strips", ".launch-row", "room"),
    ("the Settings pane", ".modal-content", "room"),
    ("menu rows", ".menu-item", "inset"),
    ("timeline sort buttons", ".timeline-sort", "inset"),
    # The 2026-10-11 sweep (focus ring probe, 1440 and 390).
    ("a page that scrolls, a stop flush with its bottom edge", ".tab-page", "room"),
    ("Settings, Background jobs: Run now fills its row on a phone", ".job-run-now", "inset"),
]

#: A pill track with an edge: its segments fill its inside, never the
#: control height of the track's outside (INBOX 694).
PILL_TRACKS = [".chat-dock-controls .seg > button"]

#: Text that ellipsises sits in a line box of at least 1.25, or keeps its
#: descender by a clip margin (INBOX 685: "Categories", "Skill logs").
TEXT_ROOM = [(".sidebar-head h2", r"line-height:\s*1\.25"), (".tab-label", r"overflow-clip-margin")]

SECTION_HEAD = "Ring room (INBOX 685"


def _section() -> str:
    text = (CSS_DIR / "08-consistency.css").read_text(encoding="utf-8")
    start = text.index(SECTION_HEAD)
    return text[start:]


def _rules(section: str) -> list[tuple[str, str]]:
    """(selector text, declaration text) for every top-level rule."""
    section = re.sub(r"/\*.*?\*/", "", section, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", section)]


def test_the_token_exists_and_matches_the_base_ring():
    css = css_text()
    assert re.search(r"--ring-room:\s*4px;", css), "--ring-room (outline 2px + offset 2px) is the one token"
    assert re.search(r":focus-visible\s*\{[^}]*outline:\s*2px solid var\(--accent\);[^}]*outline-offset:\s*2px;", css), (
        "the base ring moved: --ring-room must change with it"
    )


def test_every_listed_container_carries_its_recipe():
    rules = _rules(_section())
    missing = []
    for what, fragment, recipe in RING_ROOM:
        want = (
            re.compile(r"--ring-room")
            if recipe == "room"
            else re.compile(r"outline-offset:\s*(?:-2px|calc\(-1 \* var\(--ring-room\) \/ 2\))")
        )
        if not any(fragment in sel and want.search(body) for sel, body in rules):
            missing.append(f"{what} ({fragment}, {recipe})")
    assert not missing, "containers that lost their ring room: " + "; ".join(missing)


def test_no_ring_is_hidden_to_make_it_fit():
    """The fix is room or an inset ring, never removing the outline."""
    section = _section()
    assert not re.search(r"outline:\s*(?:none|0)\b", section)
    assert not re.search(r"outline-width:\s*0\b", section)


def test_a_pill_track_with_an_edge_hands_its_inside_to_the_segments():
    rules = _rules(_section())
    for fragment in PILL_TRACKS:
        assert any(
            fragment in sel and re.search(r"height:\s*auto", body) and re.search(r"align-self:\s*stretch", body)
            for sel, body in rules
        ), f"{fragment} lost its fill-the-track rule"


def test_clipped_single_lines_keep_their_descenders():
    css = css_text()
    for selector, want in TEXT_ROOM:
        assert any(
            re.search(want, body)
            for sel, body in _rules(css)
            if sel.split(",")[-1].strip().endswith(selector) or sel.strip().endswith(selector)
        ), f"{selector} lost its descender room ({want})"
    # no rule that ellipsises sets a line box shorter than the font
    tight = []
    for sel, body in _rules(css):
        if re.search(r"text-overflow:\s*ellipsis", body):
            lh = re.search(r"line-height:\s*([0-9.]+)\s*;", body)
            if lh and float(lh.group(1)) < 1.2:
                tight.append(sel)
    assert tight in ([], [".tab-label"]) or all(".tab-label" in t for t in tight), tight


# Library sections keep the focus ring room when scrolled to (OPEN ledger 1423).


def test_1423_library_sections_keep_the_focus_ring_room():
    assert re.search(r"\.dash-body,\s*\.library-view-section \{\s*scroll-padding-block: var\(--ring-room\);", (CSS_DIR / "08-consistency.css").read_text(encoding="utf-8"))


def test_a_focusable_chart_mark_carries_its_own_ring():
    """UX audit 2026-10-19: a focusable SVG `g` (`.ask-chart-pt`, Statistics)
    showed no outline, only the hit rect's stroke inside it. Measured after:
    solid 2px, offset -2px (inside its slot, so the chart's clip cannot cut
    it)."""
    css = (CSS_DIR / "utilities-lazy.css").read_text(encoding="utf-8")
    block = css[css.index(".ask-chart-pt:focus-visible {"):].split("}", 1)[0]
    assert "outline: 2px solid var(--accent-text);" in block
    assert "outline-offset: -2px;" in block


def _block(name: str, selector: str) -> str:
    text = (CSS_DIR / name).read_text(encoding="utf-8")
    return text[text.index(selector + " {"):].split("}", 1)[0]


def test_the_2026_10_19_audit_containers_keep_their_ring_room():
    """Clipped rings the audit measured (outline 2px + offset 2px against an
    overflow container with no padding, 4px cut), each 0 cut after, by
    `scratchpad/ui-sweeps`-style probe: the Statistics body (ask field,
    buttons, link tiles), the manual's contents jumps and topic links, the
    Settings nav's last button (focus scrolled it flush: 4.1px) and the phone
    More button (cut by the viewport at x 390 and y 900)."""
    stats = _block("utilities-lazy.css", ".stats-body")
    assert "padding: var(--ring-room);" in stats and "margin: calc(-1 * var(--ring-room));" in stats
    assert ".manual-jump:focus-visible {\n  outline-offset: -2px;" in (CSS_DIR / "manual-lazy.css").read_text(encoding="utf-8")
    topics = _block("manual-lazy.css", ".manual-topics")
    for line in ("padding-left: var(--ring-room);", "margin-left: calc(-1 * var(--ring-room));", "scroll-padding-block: var(--ring-room);"):
        assert line in topics
    rules = _rules(_section())
    assert any(sel == ".modal-nav" and "scroll-padding-block: var(--ring-room)" in body for sel, body in rules)
    assert any(".phone-tab-more" in sel and "outline-offset: -2px" in body for sel, body in rules)
