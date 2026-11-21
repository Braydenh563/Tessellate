"""A hover is declared with its keyboard twin (UI_MODERNISATION Phase 13
decision 15).

The design review measured 418 selectors with a `:hover` rule, 282 of them
with no focus rule, and a Tab walk found 110 controls whose look did not change
when focused: a keyboard user saw two thirds of the app without the feedback a
pointer gets. Brief 57 measured 462 hover selectors, 253 of them alone, and
gave each its twin in the same rule, so the two can never drift apart:

    .row:hover,
    .row:is(:focus-visible, :has(:focus-visible)) { ... }

`X:hover` matches X and every ancestor of the pointer, so the faithful twin is
X focused by the keyboard or holding such a focus (`:has(:focus-visible)`), a
row lighting when the button inside it is reached by Tab exactly as it does
when the pointer is over that button. Inside a `:has()`, which cannot nest,
the twin is `:focus-visible` alone. A separately declared focus rule for the
same selector also counts.

Exempt, by shape rather than by name: a field's `:hover:not(:focus)` (the
focused field has its own ring and edge), and a hover on a pseudo-element the
keyboard cannot reach (`::-webkit-scrollbar-thumb`, `::file-selector-button`).
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_FILES
from tests._css_unwrap import unwrap_all

NOT = re.compile(r":not\((?:[^()]|\([^()]*\))*\)")
FOCUS = re.compile(r":focus-visible|:focus-within|:focus\b")
TWIN = ":is(:focus-visible, :has(:focus-visible))"


def _split_top(text: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in text:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        cur += ch
    parts.append(cur.strip())
    return parts


def _selector_lists() -> list[list[str]]:
    from tessellate.api.asset_strip import strip_for_path

    lists = []
    for path in CSS_FILES:
        served = strip_for_path(path.name, path.read_bytes()).decode("utf-8")
        served = unwrap_all(re.sub(r"@(media|supports|container|layer)[^{]*\{", "", served))
        for m in re.finditer(r"([^{};]+)\{", served):
            lists.append(_split_top(m.group(1)))
    return lists


def _key(selector: str, pattern: re.Pattern) -> str:
    return re.sub(r"\s+", " ", pattern.sub("§", selector.replace(TWIN, ":focus-visible")))


def _exempt(selector: str) -> bool:
    return ":not(:focus)" in selector or "::-webkit-scrollbar" in selector or "::file-selector-button" in selector


def _lone_hovers() -> list[str]:
    lists = _selector_lists()
    focused = {_key(s, FOCUS) for sels in lists for s in sels if FOCUS.search(NOT.sub("", s))}
    lone = []
    for sels in lists:
        for s in sels:
            bare = NOT.sub("", s)
            if ":hover" not in bare or FOCUS.search(bare) or _exempt(s):
                continue
            if _key(s, re.compile(r":hover")) not in focused:
                lone.append(s)
    return lone


def test_every_hover_has_its_focus_visible_twin():
    lone = _lone_hovers()
    assert not lone, (
        f"{len(lone)} hover selectors with no keyboard twin (docs/DESIGN.md, 'Hover and "
        "focus are one state'). Add the twin to the same rule:\n  X:hover,\n  X" + TWIN
        + "\n\n" + "\n".join(f"  {s[:140]}" for s in lone[:40])
    )


def test_the_lint_sees_the_hovers():
    """A parser that found nothing would pass the test above vacuously."""
    hovers = sum(1 for sels in _selector_lists() for s in sels if ":hover" in NOT.sub("", s))
    assert hovers > 400, hovers


def test_the_base_button_answers_focus_with_its_hover_ground():
    """The one hover every button shares (DESIGN.md, One hover for every
    button) is the base rule's deeper ground; the keyboard gets the same."""
    forms = (CSS_FILES[0].parent / "01-forms-settings.css").read_text(encoding="utf-8")
    assert re.search(
        r"button:hover:not\(:disabled\),\s*button:is\(:focus-visible, :has\(:focus-visible\)\):not\(:disabled\) \{\s*--button-ground: var\(--accent-surface-hover\)",
        forms,
    )


# A hover rule names its keyboard twin: the count of selectors without one may only fall.
# Hover without a focus twin: a ratchet, not a fix. DESIGN.md "One hover for every button": the quiet
# fill is "the same under :focus-visible". The 2026-10-11 sweep found 216 selectors whose hover rule
# changes a fill, ink, edge or shadow with no :focus rule on the same selector (216, until Brief 57's
# grammar pass wrote the twin beside each as `:is(:focus-visible, :has(:focus-visible))`, a form the
# first normaliser could not read; it now can, and 7 remain: `:not(:hover)` rest states and the two
# native pseudo-elements). The count may only fall: a new component's hover rule names its
# :focus-visible beside it.
HOVER_WITHOUT_FOCUS_BASELINE = 7


def _strip(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _baseline_split_top(selector: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in selector:
        if ch in "([":
            depth += 1
        if ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def _hover_only_selectors() -> set[tuple[str, str]]:

    rules = []
    for path in CSS_FILES:
        text = unwrap_all(_strip(path.read_text(encoding="utf-8")))
        for m in re.finditer(r"([^{}@;]+)\{([^{}]*)\}", text):
            rules.append((path.name, m.group(1).strip(), m.group(2)))

    def norm(part: str) -> str:
        part = re.sub(r":(hover|focus-visible|focus-within|focus|active)\b", "", part)
        #: `:is(:focus-visible, :has(:focus-visible))` is the repo's focus twin (the keyboard
        #: reaching a control's child); with the pseudo-classes gone it leaves `:has()` empty.
        part = re.sub(r":has\(\s*\)", "", part)
        part = re.sub(r":is\(\s*(,\s*)*\)", "", part)
        part = re.sub(r":is\(([^(),]*)\)", r"\1", part)
        return re.sub(r"\s+", " ", part).strip()

    focus = {norm(p) for _, sel, _ in rules for p in _baseline_split_top(sel) if re.search(r":focus(-visible)?\b", p)}
    looks = re.compile(r"background|color|border|box-shadow|outline|opacity|transform|filter|text-decoration")
    found = set()
    for name, sel, body in rules:
        if not looks.search(body):
            continue
        for part in _baseline_split_top(sel):
            if not re.search(r":hover\b", part) or re.search(r":focus", part):
                continue
            # `:hover .x` reveals something inside a container; that is not a control's feedback.
            if re.search(r":hover\)?\s+[.#\[a-z>~+]", part):
                continue
            if norm(part) not in focus:
                found.add((name, part))
    return found


def test_hover_without_a_focus_twin_does_not_grow():
    found = _hover_only_selectors()
    assert len(found) <= HOVER_WITHOUT_FOCUS_BASELINE, (
        f"{len(found)} selectors have a hover rule and no :focus rule (baseline {HOVER_WITHOUT_FOCUS_BASELINE}): "
        "write the :focus-visible beside the :hover, as `:is(:hover, :focus-visible)`"
    )
