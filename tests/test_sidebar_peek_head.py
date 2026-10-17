"""A collapsed sidebar peeked open keeps its head's controls clear of the pin.

INBOX 495 (the owner, with a screenshot): "when the skill logs sidebar is
collapsed and temporarily expanded, the clear button and pin button clash".
Measured at 1440, the gap between Clear and the pin was 6.4px pinned open and
-5.6px peeked (an overlap), from two causes the stylesheet cannot show at a
glance: the peek moved the toggle 4px further in than the pinned position
the head's reserve is measured from, and an id rule that folds Skill logs'
children toward the right edge out-ranked the peek's `transform: none`, so
its head stayed shifted 8px under the toggle. The sweep that measures it is
`scratchpad/ui-sweeps/skillslogshead.js`; this holds the two rules.
"""

from __future__ import annotations

from tests._css_paths import CSS_DIR


def _css(name: str) -> str:
    return (CSS_DIR / name).read_text(encoding="utf-8")


def test_the_peeked_toggle_sits_where_the_pinned_one_does():
    css = _css("07-whiteboard-misc.css")
    #: The selector list, then its block, found by index: a regex over a
    #: repeated selector group backtracks exponentially (CodeQL).
    at = css.find(".layout-sidebar-collapsed>.sidebar-collapsed:hover .sidebar-collapse-toggle")
    assert at >= 0, "the hover-peek toggle rule is gone"
    start = css.index("{", at)
    body = css[start + 1:css.index("}", start)]
    assert "right: 1rem" in body, (
        "the peek moves the toggle off the pinned position the head's lane is measured from"
    )


def test_skill_logs_peeked_head_is_not_shifted():
    """The peek is a variable the aside sets (07-whiteboard-misc.css says why), so the id rule's
    own `--sb-peek-transform` must be reset by an id selector of the same rank, hover and focus."""
    css = _css("08-consistency.css")
    for state in (":hover", ":is(:focus-visible, :has(:focus-visible))"):
        at = css.find(".layout-sidebar-collapsed > #skills-sidebar[data-resizable].sidebar-collapsed" + state)
        assert at >= 0, "the id-specific fold transform on #skills-sidebar needs its own peek reset: " + state
        body = css[css.index("{", at) :]
        assert "--sb-peek-transform: none" in body[: body.index("}")]
    fold = css.index("#skills-sidebar[data-resizable].sidebar-collapsed {")
    assert "--sb-peek-transform: translateX(var(--space-3))" in css[fold : css.index("}", fold)]
