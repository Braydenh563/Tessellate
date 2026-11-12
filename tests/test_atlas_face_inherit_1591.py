"""The face's numbers do not inherit (INBOX 1591, the owner's lag log).

A mood, an act or a pose writes custom properties on each Atlas drawing's root.
As inherited properties every one restyled the whole subtree (600 to 1,244
elements, 450 to 630ms on a slow machine), the body's 400 paths that read none
of them. They are registered not to inherit and pass down by `inherit` through
the groups and the named readers (atlas-lazy.css, "The face's numbers").

What goes wrong when this drifts is silent: a rule that reads one of them and is
not in the readers list gets the initial value, so a part simply stops
following the mood. These tests keep the three lists one list.
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR

ANCHOR = r"(?:(?<=[{}])|\A)"
RULE = re.compile(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}")
PROP = re.compile(r"(--atl-[\w-]+)\s*:")
READ = re.compile(r"var\(\s*(--atl-[\w-]+)")
#: Registered before this change, each with its own `inherit` path (07-whiteboard-misc.css, "The
#: pose's four numbers"); the arms' two numbers are written on the arm itself.
OWN_PATH = {"--atl-lean", "--atl-sx", "--atl-sy", "--atl-tail", "--atl-lean-dir", "--atl-v1", "--atl-v2", "--atl-chin"}
#: Theme, not state: written once per theme, read by the drawing's fills, so it stays inherited.
THEME = {"--atl-aura-a"}


def _css() -> str:
    text = "\n".join(re.sub(r"/\*.*?\*/", "", (CSS_DIR / name).read_text(encoding="utf-8"), flags=re.S) for name in ("07-whiteboard-misc.css", "atlas-lazy.css"))
    return text


def _split(selectors: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in selectors:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and not depth:
            parts.append(" ".join(cur.split()))
            cur = ""
        else:
            cur += ch
    parts.append(" ".join(cur.split()))
    return [p for p in parts if p]


def _inherit_rule() -> tuple[list[str], set[str]]:
    for selector, body in RULE.findall(_css()):
        if selector.strip().startswith(":where(.nm-atlas :not(:empty),"):
            inner = selector.strip()[len(":where(") :].rstrip()
            assert inner.endswith(")"), "the readers list closes with the :where"
            return _split(inner[:-1]), set(re.findall(r"(--atl-[\w-]+)\s*:\s*inherit\s*;", body))
    raise AssertionError("the face's inherit rule is missing")


def _registered() -> set[str]:
    return set(re.findall(ANCHOR + r"\s*@property\s+(--atl-[\w-]+)\s*\{\s*syntax:\s*\"\*\";\s*inherits:\s*false;\s*\}", _css()))


def test_every_passed_property_is_registered_not_to_inherit():
    _, passed = _inherit_rule()
    assert len(passed) >= 40, "the face's numbers are passed down"
    assert passed <= _registered(), f"not registered with inherits: false: {sorted(passed - _registered())}"


def test_every_state_property_the_drawing_reads_is_passed():
    """A new mood number is registered and passed, or a part would not follow the mood."""
    _, passed = _inherit_rule()
    written, read = set(), set()
    for selector, body in RULE.findall(_css()):
        read.update(READ.findall(body))
        if re.search(r"data-atlas-mood|nmb-act-|nmb-sleep|nmb-attend|nmb-watch|data-pose", selector):
            written.update(PROP.findall(body))
    missing = sorted(p for p in written & read if p not in passed and p not in OWN_PATH and p not in THEME)
    assert not missing, f"written by a mood, act or pose and read, but not registered and passed: {missing}"


def test_every_rule_that_reads_a_passed_property_is_a_named_reader():
    """The readers list is the rules that read the numbers, or the part reads the initial value."""
    readers, passed = _inherit_rule()
    named = set(readers)
    unnamed = []
    for selector, body in RULE.findall(_css()):
        if selector.strip().startswith(":where(.nm-atlas :not(:empty),"):
            continue
        if not any(p in passed for p in READ.findall(body)):
            continue
        for one in _split(selector):
            if one not in named:
                unnamed.append(one)
    assert not unnamed, f"read a face number and not in the readers list (atlas-lazy.css): {sorted(set(unnamed))}"


def test_the_readers_rule_has_no_weight():
    """`:where`, so a part that writes a number itself (a pupil's look) still wins."""
    for selector, _body in RULE.findall(_css()):
        if selector.strip().startswith(":where(.nm-atlas :not(:empty),"):
            return
    raise AssertionError("the face's inherit rule is missing")
