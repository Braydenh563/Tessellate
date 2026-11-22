"""A hover ground is a shape: the element that gains one has rounded corners
(INBOX 856: "the very subtle hover highlight over this question doesnt have
rounded corners").

The browser is the real measure (`scratchpad/ui-sweeps/hoverradius.js` hovers
every link-like element, its four ancestors and its pseudo-elements on each
surface and reports a gained ground with four square corners: 0 on the
dashboard, notes (Your notes, Ask with an answer, Questions), chat, timeline,
reminders, library, graph, the palette, the guide and Settings, with data).
This is the cheap half the suite can run: every stylesheet rule that gives a
`:hover` ground to a row-like class must find a `border-radius` somewhere for
that class (or its tag), or sit on the reviewed list below with its reason. A
new hover ground on a new class with no corner fails here.
"""

from __future__ import annotations

import re

from tests._css_paths import css_text

#: Buttons, chips, toasts and icon controls take their corner from the shared
#: button and chip rules, so a scan by class cannot judge them.
SKIP = re.compile(
    r"input|button|icon|toggle|opener|chip|toast|-btn|sort|scrollbar|unlink|select-option|\.modal|:not\(:hover\)|"
    r"\.tool|\.seg|\.tab|menu|\.dock|kebab|ghost|\.small"
)

#: Reviewed: each has its corner from an element or an ancestor rule the class
#: scan cannot see, or is not a surface a person points at.
REVIEWED = {
    "#conversation-list li.active-conv:hover": "the li's own `border-radius: var(--radius-md)` (02-chat-graph.css)",
    ".entry-list li.clickable-result:hover": "`.entry-list li` sets the radius (04-chat-dock-appearance.css)",
    ".conv-divider:hover": "a 1px splitter, not a surface",
    ".md-grip:hover": "a drag handle, drawn in the accent",
    ".library-activity:hover": "a spine rule with no ground of its own",
    ".ocr-region-text-empty:hover": "ground is `none`",
    "#conversation-list li.conv-group:hover": "ground is `none`: a folder heading in the chat list is not a row",
    ".library-file-rows .library-image-tile .library-read-open:hover": "ground is `none`",
    ".doc-prop-btn:hover": "ground is `none`",
    ".timeline-table tbody tr:hover td": "a collapsed-border table row: radius does not apply to cells there",
}


def _rules() -> list[tuple[str, str]]:
    css = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}@]+)\{([^{}]*)\}", css)]


def _last_compound(selector: str) -> str:
    parts = re.sub(r"\s*[>+~]\s*", " ", selector.strip()).split()
    return parts[-1] if parts else selector


def _classes(compound: str) -> set[str]:
    return set(re.findall(r"\.([A-Za-z_][\w-]*)", re.sub(r":(not|is|where|has)\([^)]*\)", "", compound)))


def test_every_row_like_hover_ground_has_a_radius_or_a_reason():
    rules = _rules()
    rounded: set[str] = set()
    for selector, body in rules:
        if "radius" in body:
            for one in selector.split(","):
                rounded |= _classes(_last_compound(one))
    missing: dict[str, str] = {}
    for selector, body in rules:
        if not re.search(r"(^|;|\s)background(-color)?\s*:\s*(?!none|transparent)", body):
            continue
        for one in (s.strip() for s in selector.split(",")):
            if ":hover" not in one or SKIP.search(one) or one in REVIEWED:
                continue
            compound = _last_compound(re.sub(r":(hover|focus-visible|focus-within)(\([^)]*\))?", "", one))
            classes = _classes(compound)
            if classes and not classes & rounded:
                missing[one] = body.strip().replace("\n", " ")[:70]
    assert not missing, (
        "a hover ground with no corner anywhere for its class (INBOX 856): give the class "
        f"`border-radius: var(--radius-sm)` or more, or review it into REVIEWED: {missing}"
    )
