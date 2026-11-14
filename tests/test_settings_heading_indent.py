"""Settings has one heading indent (L-world-class-84).

Measured 2026-11-14 at 1440px over every pane (Playwright, getBoundingClientRect):
a pane's title in its dock sat 11px in from the pane edge (9.6px padding and a
1px border) while every group heading under it sat 17px in (1rem padding and
the group's 1px border). The title now takes the group's own 1rem inset.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def _padding(selector: str) -> str:
    body = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert body, selector
    found = re.search(r"padding(?:-inline)?:\s*([^;]+);", body.group(1))
    assert found, selector
    return found.group(1).split()[-1] if "padding-inline" in body.group(1) else found.group(1).split()[1]


def test_a_pane_title_is_inset_as_far_as_the_groups_under_it():
    group = _padding(".settings-group")
    title = _padding(".settings-section > .dock")
    assert group == title == "1rem"


# L-world-class-260. Measured 2026-11-14 at 1440px (getBoundingClientRect, the
# title's left edge from the pane's left edge). Every visible pane title is at
# 17px. The three that were not are intended, each for a stated reason:
#   - Models -1px: its dock holds only the title, so the dock and title are
#     clipped to 1px with margin -1px (the jump list names the pane); nothing
#     visible to align.
#   - Help 0px: the topic group heads sit above the accordion card and share
#     the card's outer edge (the card text starts at 12.8px inside it).
#   - Preferences "Your profile" 68.8px: it is the name beside the avatar
#     (`.profile-head`), not a pane title; the pane's own title "Profile" is 17px.
ROOT = Path(__file__).resolve().parent.parent / "frontend" / "css"


def _all_css() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(ROOT.glob("*.css")))


def test_models_title_is_clipped_not_indented():
    css = (ROOT / "settings-controls-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"h3\.jump-echo:only-child\):not\(:has\(> :not\(\.dock-identity\)\)\)\s*\{([^}]*)\}", css)
    assert rule, "the title-only dock is no longer clipped"
    assert "clip-path: inset(50%)" in rule.group(1) and "margin: -1px" in rule.group(1)


def test_help_topic_heads_share_the_card_edge():
    css = _all_css()
    for body in re.findall(r"#help-topics(?:\s*>\s*|\s+)h3[^{]*\{([^}]*)\}", css):
        assert not re.search(r"(margin|padding)-(left|inline-start):\s*[^0;]", body)


def test_profile_name_sits_beside_the_avatar_by_a_token_gap():
    css = _all_css()
    head = re.search(r"\.profile-head\s*\{([^}]*)\}", css)
    assert head and "display: flex" in head.group(1) and "gap: var(--space-5)" in head.group(1)
