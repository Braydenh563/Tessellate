"""An animation may not move a layout property without saying why (INBOX 308).

The owner, verbatim: "I also think we need to make sure that all animations for
things are done the cheapest they can be to reduce cost in the browser and
devices. like using transform etc etc."

An animated `width`, `height`, `top`, `left`, `margin` or `padding` makes the
browser lay the page out again on every frame of the animation, on the frames
where it is least affordable: a boot, a scroll, a phone. `transform` and
`opacity` are handed to the compositor and cost no layout at all. The
difference is not theoretical, and this repository has the number: converting
the boot splash's progress bar from `width` to `transform: scaleX()` took one
2.4s crawl from 121 layouts to 0 (`scratchpad/ui-sweeps/animcost.js`, which
re-measures it).

So this lint fails on a `transition` or a `@keyframes` rule that names one of
those properties, and passes it when the declaration carries a stated reason in
a `/* ... */` comment ending on the line above. The escape is a comment rather
than a list of blessed selectors kept here, because the reason has to be read
where the trade is made, and a list in a test file rots the moment the
stylesheet moves. There is exactly one such reason in the app today, at
`#phone-tab-dock`'s `transition: height` in `10-responsive.css`: a bar that
recedes from 57.59px to 44px really is a box changing size with content in it,
where `translateY` would take the bottom off a 44px touch target and `scaleY`
would squash the icons.

**`box-shadow` is not on the list for the decorative surfaces**, and this is
the place that decision is written down so it is not remade. (The interface's
own transitions, the polish set, gave it up in the motion pass of
2026-10-05, "no animation on ... box-shadow size": the last test below holds
that; a shadow there changes at once while the rest eases.) Ten transitions in
`frontend/css/` animate it, mostly the hover lift on buttons and cards. It
repaints, it does not relayout, it is the app's idiomatic hover treatment, and
the cheaper form (a pseudo-element carrying the shadow, animated on `opacity`)
costs an extra box on every one of those surfaces. A rule that fires on the
ordinary, correct thing is a rule people learn to suppress rather than obey, so
this one fires only where there is a real layout to avoid. If shadow repaints
ever show up in a measurement, the answer is that measurement and a plan entry,
not a widening of this rule.

Like the other frontend lints this cannot see the DOM. What runs against a real
browser is `scratchpad/ui-sweeps/animcost.js`, which counts the layouts an
animation actually forces.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "frontend"

#: The properties whose animation costs a layout. Matched as whole property
#: names, never as substrings: `border-width` and `stroke-width` are not
#: `width`, and a lint that failed on them would be teaching the wrong rule.
#: The longhands and the logical/min/max forms are here because they are the
#: same fault written differently, which is exactly how a rule gets worked
#: around.
_BOX = ["margin", "padding"]
_SIDES = ["top", "right", "bottom", "left", "block", "inline", "block-start",
          "block-end", "inline-start", "inline-end"]
LAYOUT_PROPERTIES = frozenset(
    ["width", "height", "min-width", "max-width", "min-height", "max-height",
     "top", "right", "bottom", "left",
     "inset", "inset-block", "inset-inline",
     "block-size", "inline-size", "min-block-size", "max-block-size",
     "min-inline-size", "max-inline-size"]
    + _BOX
    + [f"{b}-{s}" for b in _BOX for s in _SIDES]
)

#: `all` is worse than naming one of them: it animates whatever happens to
#: change, layout properties included, and nobody reading the rule can tell
#: what it will move.
BANNED_SHORTHANDS = frozenset({"all"})

#: Not property names: the rest of a `transition` value. Durations and delays
#: are stripped by their units, this is for the timing-function keywords and
#: the two behaviour keywords, so that `ease` and `linear` are never read as
#: properties.
_NOT_PROPERTIES = frozenset({
    "ease", "ease-in", "ease-out", "ease-in-out", "linear", "step-start",
    "step-end", "normal", "allow-discrete", "none", "initial", "inherit",
    "unset", "revert",
})

COMMENT_END = re.compile(r"\*/\s*$")
DURATION = re.compile(r"^[\d.]+m?s$")


def _css_files() -> list[Path]:
    return [p for p in repo_files(CSS_DIR, suffixes=(".css",)) if ".min." not in p.name]


def _strip_comments(value: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", value, flags=re.S)


def _blank_comments(source: str) -> str:
    """Every `/* ... */` replaced by spaces, with its newlines kept.

    Two faults this closes, both found by running the first draft of this lint
    against the real stylesheets. A comment that *discusses* a transition
    ("No width transition: the grid track...", 07-whiteboard-misc.css:448) is
    not a declaration and must not be read as one. And a declaration's value
    does not have to sit on one line: eight of them in `frontend/css/` wrap
    onto a second or third, so a line-by-line scan reads the first property
    and walks past the rest. Blanking rather than deleting keeps every line
    number, which the failure messages and the reason-above check both need.
    """
    out, i = [], 0
    for match in re.finditer(r"/\*.*?\*/", source, flags=re.S):
        out.append(source[i:match.start()])
        out.append(re.sub(r"[^\n]", " ", match.group(0)))
        i = match.end()
    out.append(source[i:])
    return "".join(out)


def _has_reason(lines: list[str], index: int) -> bool:
    """Does a `/* ... */` comment end on the line above `index`, with words in it?

    A bare `/* */` or a comment that only repeats the property name is not a
    reason; the shortest thing that passes here is a short sentence, which is
    the point: the reader of the rule needs to know what was traded away.
    """
    if index == 0:
        return False
    if not COMMENT_END.search(lines[index - 1].strip()):
        return False
    # Walk back to the comment's opening so the whole block counts as the
    # reason, not only its last line: the reasons in this codebase are
    # paragraphs, and the one that matters most is eleven lines long.
    i = index - 1
    while i >= 0 and "/*" not in lines[i]:
        i -= 1
    if i < 0:
        return False
    body = re.sub(r"[/*]", " ", "\n".join(lines[i:index]))
    return len(body.split()) >= 5


def _transition_properties(value: str) -> set[str]:
    """The property names in a `transition` / `transition-property` value."""
    found: set[str] = set()
    for part in _strip_comments(value).split(","):
        for token in part.replace("(", " ").replace(")", " ").split():
            token = token.strip().lower()
            if not token or token in _NOT_PROPERTIES or DURATION.match(token):
                continue
            if token.startswith("cubic-bezier") or token.startswith("steps"):
                continue
            if token.startswith("var(") or token.startswith("--"):
                continue
            found.add(token)
    return found


def _blocks(source: str) -> list[tuple[int, str, str]]:
    """Every `@keyframes` block as (the line it opens on, its name, its body)."""
    out = []
    for match in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", source):
        depth, i = 1, match.end()
        while depth and i < len(source):
            if source[i] == "{":
                depth += 1
            elif source[i] == "}":
                depth -= 1
            i += 1
        out.append((source.count("\n", 0, match.start()), match.group(1),
                    source[match.end():i]))
    return out


@pytest.mark.parametrize("path", _css_files(), ids=lambda p: p.name)
def test_transitions_do_not_animate_layout(path: Path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    # The value runs to its `;`, over as many lines as it takes: the character
    # class stops at `;`, `{` and `}` and crosses newlines without being asked.
    code = _blank_comments(source)
    offenders = []
    for match in re.finditer(r"(?<![-\w])transition(?:-property)?\s*:([^;{}]*)", code):
        n = code.count("\n", 0, match.start())
        named = _transition_properties(match.group(1))
        bad = sorted((named & LAYOUT_PROPERTIES) | (named & BANNED_SHORTHANDS))
        if bad and not _has_reason(lines, n):
            offenders.append(f"{path.name}:{n + 1}: transition animates {', '.join(bad)}")
    assert not offenders, (
        "\n".join(offenders)
        + "\n\nAnimating a layout property lays the page out on every frame. "
        "Use `transform` (scaleX/translate) or `opacity`, which the compositor "
        "handles: a full-width box scaled from a left origin inside a clipping "
        "track is the recipe for a bar, and 00-tokens-shell.css's "
        "`.boot-splash-progress-fill` is the worked example. If the box really "
        "does change size with content in it, keep the transition and write the "
        "reason in a /* ... */ comment on the line above, as "
        "`#phone-tab-dock` does."
    )


@pytest.mark.parametrize("path", _css_files(), ids=lambda p: p.name)
def test_keyframes_do_not_animate_layout(path: Path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    offenders = []
    for start, name, body in _blocks(_blank_comments(source)):
        named = {
            m.group(1).lower()
            for m in re.finditer(r"(?<![-\w])([a-z-]+)\s*:", _strip_comments(body))
        }
        bad = sorted(named & LAYOUT_PROPERTIES)
        if bad and not _has_reason(lines, start):
            offenders.append(
                f"{path.name}:{start + 1}: @keyframes {name} animates {', '.join(bad)}"
            )
    assert not offenders, (
        "\n".join(offenders)
        + "\n\nA keyframe that moves a layout property lays the page out on "
        "every frame of the animation. Animate `transform` or `opacity` "
        "instead, or write the reason in a /* ... */ comment above the "
        "`@keyframes` line."
    )


#: Not layout, but a repaint of the surface and everything behind it on every
#: frame: a blur's cost is the area under it, and on this app's glass that is
#: the whole window (anim.md, OPEN.md "Carried from the agent files"). One
#: transition names `filter` today, a graph node's own hover glow, and says
#: so above it; the next one has to say why too, and the shape of the
#: measurement is `scratchpad/ui-sweeps/animcost.js`.
REPAINT_UNDER = frozenset({"filter", "backdrop-filter", "-webkit-backdrop-filter"})


@pytest.mark.parametrize("path", _css_files(), ids=lambda p: p.name)
def test_nothing_animates_a_filter_without_a_reason(path: Path):
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    code = _blank_comments(source)
    offenders = []
    for match in re.finditer(r"(?<![-\w])transition(?:-property)?\s*:([^;{}]*)", code):
        n = code.count("\n", 0, match.start())
        bad = sorted(_transition_properties(match.group(1)) & REPAINT_UNDER)
        if bad and not _has_reason(lines, n):
            offenders.append(f"{path.name}:{n + 1}: transition animates {', '.join(bad)}")
    for start, name, body in _blocks(code):
        named = {m.group(1).lower() for m in re.finditer(r"(?<![-\w])([a-z-]+)\s*:", _strip_comments(body))}
        bad = sorted(named & REPAINT_UNDER)
        if bad and not _has_reason(lines, start):
            offenders.append(f"{path.name}:{start + 1}: @keyframes {name} animates {', '.join(bad)}")
    assert not offenders, "\n".join(offenders) + (
        "\n\nAnimating a filter or a backdrop blur repaints everything under the "
        "surface on every frame. Fade the surface on `opacity` instead, or write "
        "the reason (and the animcost.js number) in a /* ... */ comment above it."
    )


def test_the_rule_is_written_where_designers_read_it():
    """DESIGN.md carries the rule, because a lint nobody has read is a trap.

    Standing order 11: new UI comes from DESIGN.md's recipe index, and a rule
    arrives with its lint. This is the other half of that, checked, so the two
    cannot drift apart the way an undocumented lint always does.
    """
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "test_cheap_animations" in design, (
        "docs/DESIGN.md does not mention this lint; the rule about animating "
        "transform rather than width/height has to be readable where the design "
        "system is, not only where it is enforced"
    )


#: The polish set (DESIGN.md, "Interface animations"): everything but the
#: decorative and progress surfaces `tests/test_motion_tokens.py` names.
from tests.test_motion_tokens import DECORATIVE  # noqa: E402


def _rules_of(text: str):
    for m in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", _blank_comments(text)):
        yield text.count("\n", 0, m.start()) + 1, " ".join(m.group(1).split()), m.group(2)


@pytest.mark.parametrize("path", _css_files(), ids=lambda p: p.name)
def test_the_polish_never_animates_a_shadow(path: Path):
    offenders = []
    for line, selector, body in _rules_of(path.read_text(encoding="utf-8")):
        if selector.startswith("@") or DECORATIVE.search(selector):
            continue
        for m in re.finditer(r"(?<![-\w])transition(?:-property)?\s*:([^;]*)", body):
            if "box-shadow" in _transition_properties(m.group(1)):
                offenders.append(f"{path.name}:{line}: {selector[:70]}")
    assert not offenders, (
        "An interface transition animates `box-shadow` (the motion pass: transform "
        "and opacity, and a colour, only). Let the shadow change at once:\n" + "\n".join(offenders)
    )


def test_the_motion_sections_hold_no_layer_and_no_loop():
    """`will-change` only while something animates (never in a stylesheet,
    where it is permanent), and no polish animation repeats."""
    offenders = []
    for path in _css_files():
        raw = path.read_text(encoding="utf-8")
        heads = [m.start() for m in re.finditer(r"/\* ---", raw)]
        for n, start in enumerate(heads):
            if not raw.startswith("/* --- motion:", start):
                continue
            end = heads[n + 1] if n + 1 < len(heads) else len(raw)
            code = _blank_comments(raw[start:end])
            if re.search(r"(?<![-\w])will-change\s*:", code):
                offenders.append(f"{path.name}: will-change in the section at line {raw.count(chr(10), 0, start) + 1}")
            if re.search(r"\binfinite\b", code):
                offenders.append(f"{path.name}: an infinite animation in the section at line {raw.count(chr(10), 0, start) + 1}")
    assert not offenders, "\n".join(offenders)
